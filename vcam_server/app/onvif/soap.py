"""SOAP envelope parsing and building (SOAP 1.1 and 1.2)."""
from dataclasses import dataclass, field

from lxml import etree

from app.onvif import namespaces as NS
from app.onvif.faults import OnvifFault, well_formed
from app.onvif.xml import Xml, child, el, local, ns_of, text

_parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True, huge_tree=False)


@dataclass
class SoapRequest:
    version: str  # "1.1" | "1.2"
    body_el: etree._Element
    ns: str
    op: str
    header: etree._Element | None = None
    wsa_action: str | None = None
    wsa_message_id: str | None = None
    wsa_to: str | None = None
    username_token: dict | None = None
    raw: bytes = b""
    extra: dict = field(default_factory=dict)


def parse_request(raw: bytes) -> SoapRequest:
    try:
        root = etree.fromstring(raw, _parser)
    except etree.XMLSyntaxError as exc:
        raise well_formed(f"XML is not well formed: {exc}") from exc
    if local(root.tag) != "Envelope":
        raise well_formed("Root element is not a SOAP Envelope")
    version = "1.1" if ns_of(root.tag) == NS.SOAP11 else "1.2"
    header = child(root, "Header")
    body = child(root, "Body")
    if body is None or len(body) == 0:
        raise well_formed("SOAP Body is empty")
    body_el = next((c for c in body if isinstance(c.tag, str)), None)
    if body_el is None:
        raise well_formed("SOAP Body is empty")

    req = SoapRequest(version=version, body_el=body_el, ns=ns_of(body_el.tag), op=local(body_el.tag), header=header, raw=raw)
    if header is not None:
        req.wsa_action = text(header, "Action")
        req.wsa_message_id = text(header, "MessageID")
        req.wsa_to = text(header, "To")
        ut = child(header, "Security", "UsernameToken")
        if ut is not None:
            pw = child(ut, "Password")
            req.username_token = {
                "username": text(ut, "Username") or "",
                "password": (pw.text or "").strip() if pw is not None else "",
                "password_type": (pw.get("Type") or "") if pw is not None else "",
                "nonce": text(ut, "Nonce") or "",
                "created": text(ut, "Created") or "",
            }
    return req


def _soap_ns(version: str) -> str:
    return NS.SOAP11 if version == "1.1" else NS.SOAP12


def content_type(version: str) -> str:
    return "text/xml; charset=utf-8" if version == "1.1" else "application/soap+xml; charset=utf-8"


def envelope(body_xml: str, version: str = "1.2", header_xml: str = "") -> bytes:
    decls = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.PREFIXES.items())
    env_ns = _soap_ns(version)
    header = f"<SOAP-ENV:Header>{header_xml}</SOAP-ENV:Header>" if header_xml else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<SOAP-ENV:Envelope xmlns:SOAP-ENV="{env_ns}" {decls}>'
        f"{header}<SOAP-ENV:Body>{body_xml}</SOAP-ENV:Body></SOAP-ENV:Envelope>"
    ).encode("utf-8")


def response_action(req_action: str | None) -> str | None:
    if not req_action:
        return None
    return req_action[:-7] + "Response" if req_action.endswith("Request") else req_action + "Response"


def wsa_header(req: SoapRequest) -> str:
    """WS-Addressing reply headers, only when the request used WS-Addressing."""
    if not (req.wsa_action or req.wsa_message_id):
        return ""
    parts = []
    action = response_action(req.wsa_action)
    if action:
        parts.append(el("wsa:Action", action))
    if req.wsa_message_id:
        parts.append(el("wsa:RelatesTo", req.wsa_message_id))
    return "".join(parts)


def fault_body(fault: OnvifFault, version: str) -> Xml:
    if version == "1.1":
        sub = fault.subcodes[-1] if fault.subcodes else ""
        return el(
            "SOAP-ENV:Fault",
            el("faultcode", f"SOAP-ENV:{'Client' if fault.code == 'Sender' else 'Server'}"),
            el("faultstring", fault.reason),
            el("detail", el("ter:Code", sub)) if sub else None,
        )

    def subcode(codes: list[str]) -> Xml | None:
        if not codes:
            return None
        return el("SOAP-ENV:Subcode", el("SOAP-ENV:Value", codes[0]), subcode(codes[1:]))

    return el(
        "SOAP-ENV:Fault",
        el("SOAP-ENV:Code", el("SOAP-ENV:Value", f"SOAP-ENV:{fault.code}"), subcode(fault.subcodes)),
        el("SOAP-ENV:Reason", el("SOAP-ENV:Text", fault.reason, xml__lang="en")),
    )
