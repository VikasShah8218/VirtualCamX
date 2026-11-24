"""POST /onvif/* on a camera listener. See plan section 6.1 for the request flow."""
import asyncio
import logging
import time

from fastapi import Request, Response

from app.inspector import buffer as inspector
from app.onvif import dispatcher, soap
from app.onvif.dispatcher import Access, OnvifContext
from app.onvif.faults import OnvifFault, action_failed, action_not_supported, not_authorized
from app.onvif.security import AuthResult, digest_challenge, verify_http_auth, verify_wsse

logger = logging.getLogger("vcam.onvif")

SHORT_NS = {
    "http://www.onvif.org/ver10/device/wsdl": "device",
    "http://www.onvif.org/ver10/media/wsdl": "media",
    "http://www.onvif.org/ver20/media/wsdl": "media2",
    "http://www.onvif.org/ver10/events/wsdl": "events",
    "http://docs.oasis-open.org/wsn/b-2": "events",
    "http://www.onvif.org/ver20/imaging/wsdl": "imaging",
    "http://www.onvif.org/ver20/ptz/wsdl": "ptz",
    "http://www.onvif.org/ver10/deviceIO/wsdl": "deviceio",
}


def authenticate(request: Request, req: soap.SoapRequest, rt) -> AuthResult:
    if rt.faults.auth_broken():
        return AuthResult(False, method="wsse" if req.username_token else "digest", reason="password changed (fault)")
    sec = rt.state.security
    if req.username_token and sec.auth_mode in ("both", "wsse"):
        return verify_wsse(req.username_token, rt.users, rt.clock.now(), rt.nonces, sec.allow_password_text)
    header = request.headers.get("authorization")
    if header and sec.auth_mode in ("both", "digest"):
        return verify_http_auth(header, request.method, rt.users, sec.allow_basic)
    return AuthResult(False, method="none", reason="no credentials")


def local_host(request: Request, rt) -> str:
    """The camera IP as the client sees it (the local address the client connected to)."""
    server = request.scope.get("server")
    host = server[0] if server else None
    if not host or host in ("0.0.0.0", "::"):
        return rt.advertised_ip()
    return host


async def handle_onvif(request: Request, rt) -> Response:
    t0 = time.perf_counter()
    raw = await request.body()
    client_ip = request.client.host if request.client else "?"
    version = "1.2"
    op_name, service = "?", "?"
    auth_state, auth_method, user = "none", "none", None
    extra_http_headers: dict[str, str] = {}
    status = 200
    fault_txt = None
    try:
        delay = rt.faults.onvif_delay_ms()
        if delay:
            await asyncio.sleep(delay / 1000)
        req = soap.parse_request(raw)
        version = req.version
        op_name, service = req.op, SHORT_NS.get(req.ns, req.ns)
        op = dispatcher.find(req.ns, req.op)
        if op is None:
            raise action_not_supported(req.op)

        ctx = OnvifContext(runtime=rt, req=req, host=local_host(request, rt), port=rt.http_port_public(),
                           path=request.url.path, client_ip=client_ip)
        if op.access == Access.PRE_AUTH:
            auth_state = "pre_auth"
        else:
            result = authenticate(request, req, rt)
            auth_method = result.method
            if not result.ok:
                auth_state = "failed"
                if result.method in ("none", "digest", "basic") and rt.state.security.auth_mode in ("both", "digest"):
                    extra_http_headers["WWW-Authenticate"] = digest_challenge(stale=result.reason == "stale nonce")
                    f = not_authorized()
                    f.http_status = 401
                    raise f
                raise not_authorized()
            auth_state, user = "ok", result.user
            ctx.user = user
            if not dispatcher.is_allowed(user.level, op.access):
                raise not_authorized(f"User level {user.level} may not call {req.op}")
        if rt.faults.onvif_error_for(req.op):
            raise action_failed("Failed", f"{req.op} failed (injected fault)")

        body = await op.func(ctx)
        header = soap.wsa_header(req) + "".join(ctx.extra_headers)
        payload = soap.envelope(body, version, header)
    except OnvifFault as f:
        status = f.http_status
        fault_txt = f"{f.code}/{'/'.join(f.subcodes)}: {f.reason}"
        payload = soap.envelope(soap.fault_body(f, version), version)
    except Exception as exc:
        logger.exception("[%s] ONVIF %s crashed", rt.name, op_name)
        f = action_failed("Failed", f"Internal error: {exc}")
        status = 500
        fault_txt = f"Receiver/ter:Action: {exc}"
        payload = soap.envelope(soap.fault_body(f, version), version)

    inspector.record(
        rt.camera_id,
        client_ip=client_ip,
        path=request.url.path,
        service=service,
        operation=op_name,
        user=user.username if user else None,
        auth=auth_state,
        auth_method=auth_method,
        status=status,
        duration_ms=round((time.perf_counter() - t0) * 1000, 2),
        fault=fault_txt,
        request_xml=raw,
        response_xml=payload,
    )
    return Response(payload, status_code=status, media_type=soap.content_type(version), headers=extra_http_headers)
