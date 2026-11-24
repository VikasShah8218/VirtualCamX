"""ONVIF smoke test: acts like an NVR against one virtual camera.

    py tools/onvif_smoke.py <host> <port> [user] [password] [--manager http://127.0.0.1:9000 --token <jwt> --camera-id N]

Uses onvif-zeep (Profile S services, PTZ, Imaging, Events, DeviceIO) and hand-built
WS-Security SOAP for Media2 (onvif-zeep ships no Media2 WSDL). Exits 1 if any check fails.
"""
import argparse
import base64
import datetime as dt
import hashlib
import os
import sys
import time
import traceback

import httpx
from onvif import ONVIFCamera
from lxml import etree

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def deco(fn):
        def run(*a, **kw):
            try:
                detail = fn(*a, **kw)
                RESULTS.append((name, True, str(detail or "")))
                print(f"  PASS  {name}  {detail or ''}")
            except Exception as exc:
                RESULTS.append((name, False, repr(exc)))
                print(f"  FAIL  {name}  {exc!r}")
                if os.environ.get("SMOKE_TRACE"):
                    traceback.print_exc()
        return run
    return deco


def wsse_header(user: str, password: str) -> str:
    nonce = os.urandom(16)
    created = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    digest = base64.b64encode(hashlib.sha1(nonce + created.encode() + password.encode()).digest()).decode()
    return (
        '<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" '
        'xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"><wsse:UsernameToken>'
        f"<wsse:Username>{user}</wsse:Username>"
        '<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">'
        f"{digest}</wsse:Password>"
        f'<wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-soap-message-security-1.0#Base64Binary">{base64.b64encode(nonce).decode()}</wsse:Nonce>'
        f"<wsu:Created>{created}</wsu:Created></wsse:UsernameToken></wsse:Security>"
    )


def raw_soap(url: str, body: str, user: str, password: str) -> etree._Element:
    env = (
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:tr2="http://www.onvif.org/ver20/media/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">'
        f"<s:Header>{wsse_header(user, password)}</s:Header><s:Body>{body}</s:Body></s:Envelope>"
    )
    r = httpx.post(url, content=env, headers={"Content-Type": "application/soap+xml; charset=utf-8"}, timeout=10)
    root = etree.fromstring(r.content)
    if r.status_code != 200:
        reason = root.findtext(".//{*}Reason/{*}Text")
        raise RuntimeError(f"HTTP {r.status_code}: {reason}")
    return root


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("port", type=int)
    ap.add_argument("user", nargs="?", default="admin")
    ap.add_argument("password", nargs="?", default="admin123")
    ap.add_argument("--manager", default=None)
    ap.add_argument("--token", default=None)
    ap.add_argument("--camera-id", type=int, default=None)
    a = ap.parse_args()

    print(f"ONVIF smoke test against {a.host}:{a.port} as {a.user}")
    cam = ONVIFCamera(a.host, a.port, a.user, a.password)
    dev = cam.devicemgmt
    media = cam.create_media_service()
    m2url = f"http://{a.host}:{a.port}/onvif/media2_service"

    @check("Device.GetDeviceInformation")
    def _():
        i = dev.GetDeviceInformation()
        return f"{i.Manufacturer} {i.Model} fw={i.FirmwareVersion} sn={i.SerialNumber}"
    _()

    @check("Device.GetSystemDateAndTime")
    def _():
        t = dev.GetSystemDateAndTime()
        return f"{t.DateTimeType} TZ={t.TimeZone.TZ} UTC={t.UTCDateTime.Time.Hour:02d}:{t.UTCDateTime.Time.Minute:02d}"
    _()

    @check("Device.GetCapabilities")
    def _():
        c = dev.GetCapabilities({"Category": "All"})
        return f"media={c.Media.XAddr} events={c.Events.XAddr} ptz={'yes' if c.PTZ else 'no'}"
    _()

    @check("Device.GetServices")
    def _():
        s = dev.GetServices({"IncludeCapability": True})
        return f"{len(s)} services: " + ", ".join(x.Namespace.split('/')[-2] for x in s)
    _()

    for op in ("GetNetworkInterfaces", "GetDNS", "GetNTP", "GetHostname", "GetScopes", "GetNetworkProtocols",
               "GetDiscoveryMode", "GetUsers", "GetRelayOutputs", "GetNetworkDefaultGateway"):
        check(f"Device.{op}")(lambda op=op: f"{len(r) if isinstance(r := getattr(dev, op)(), list) else 'ok'}")()

    profiles = []

    @check("Media.GetProfiles")
    def _():
        profiles.extend(media.GetProfiles())
        return ", ".join(f"{p.token}:{p.VideoEncoderConfiguration.Encoding} {p.VideoEncoderConfiguration.Resolution.Width}x{p.VideoEncoderConfiguration.Resolution.Height}" for p in profiles)
    _()

    @check("Media.GetStreamUri (each profile)")
    def _():
        uris = []
        for p in profiles:
            req = media.create_type("GetStreamUri")
            req.ProfileToken = p.token
            req.StreamSetup = {"Stream": "RTP-Unicast", "Transport": {"Protocol": "RTSP"}}
            uris.append(media.GetStreamUri(req).Uri)
        return " | ".join(uris)
    _()

    @check("Media.GetSnapshotUri + HTTP Digest fetch")
    def _():
        uri = media.GetSnapshotUri({"ProfileToken": profiles[0].token}).Uri
        r = httpx.get(uri, auth=httpx.DigestAuth(a.user, a.password), timeout=15)
        assert r.status_code == 200 and r.content[:2] == b"\xff\xd8", f"HTTP {r.status_code}"
        return f"{uri} -> {len(r.content)} bytes JPEG"
    _()

    @check("Media.GetVideoEncoderConfigurationOptions")
    def _():
        o = media.GetVideoEncoderConfigurationOptions({"ProfileToken": profiles[0].token})
        return f"H264 res={[f'{r.Width}x{r.Height}' for r in o.H264.ResolutionsAvailable]}"
    _()

    @check("Media.SetVideoEncoderConfiguration (sub stream 640x360 @10fps)")
    def _():
        cfg = media.GetVideoEncoderConfiguration({"ConfigurationToken": profiles[1].VideoEncoderConfiguration.token})
        cfg.Resolution.Width, cfg.Resolution.Height = 640, 360
        cfg.RateControl.FrameRateLimit = 10
        media.SetVideoEncoderConfiguration({"Configuration": cfg, "ForcePersistence": True})
        back = media.GetVideoEncoderConfiguration({"ConfigurationToken": cfg.token})
        assert (back.Resolution.Width, back.Resolution.Height, back.RateControl.FrameRateLimit) == (640, 360, 10)
        return "read back OK"
    _()

    @check("Media.SetVideoEncoderConfiguration rejects bad resolution")
    def _():
        cfg = media.GetVideoEncoderConfiguration({"ConfigurationToken": profiles[1].VideoEncoderConfiguration.token})
        cfg.Resolution.Width, cfg.Resolution.Height = 1234, 567
        try:
            media.SetVideoEncoderConfiguration({"Configuration": cfg, "ForcePersistence": True})
        except Exception as exc:
            return f"fault as expected: {str(exc)[:60]}"
        raise AssertionError("no fault")
    _()

    # ---- Media2 (raw SOAP) -----------------------------------------------------------------
    @check("Media2.GetProfiles(Type=All)")
    def _():
        root = raw_soap(m2url, "<tr2:GetProfiles><tr2:Type>All</tr2:Type></tr2:GetProfiles>", a.user, a.password)
        encs = [e.text for e in root.iter("{http://www.onvif.org/ver10/schema}Encoding")]
        return f"{len(root.findall('.//{*}Profiles'))} profiles, encodings={encs}"
    _()

    @check("Media2.GetStreamUri")
    def _():
        root = raw_soap(m2url, f"<tr2:GetStreamUri><tr2:Protocol>RTSP</tr2:Protocol><tr2:ProfileToken>{profiles[0].token}</tr2:ProfileToken></tr2:GetStreamUri>", a.user, a.password)
        return root.findtext(".//{*}Uri")
    _()

    @check("Media2.GetVideoEncoderConfigurationOptions")
    def _():
        root = raw_soap(m2url, "<tr2:GetVideoEncoderConfigurationOptions/>", a.user, a.password)
        return "encodings=" + ",".join(e.text for e in root.iter("{http://www.onvif.org/ver10/schema}Encoding"))
    _()

    @check("Media2.GetOSDs")
    def _():
        root = raw_soap(m2url, "<tr2:GetOSDs/>", a.user, a.password)
        return f"{len(root.findall('.//{*}OSDs'))} OSDs"
    _()

    # ---- Imaging -----------------------------------------------------------------------------
    imaging = cam.create_imaging_service()
    vs_token = media.GetVideoSources()[0].token

    @check("Imaging.Get/SetImagingSettings (brightness 70, IR cut OFF)")
    def _():
        s = imaging.GetImagingSettings({"VideoSourceToken": vs_token})
        s.Brightness = 70
        s.IrCutFilter = "OFF"
        imaging.SetImagingSettings({"VideoSourceToken": vs_token, "ImagingSettings": s, "ForcePersistence": True})
        back = imaging.GetImagingSettings({"VideoSourceToken": vs_token})
        assert back.Brightness == 70 and back.IrCutFilter == "OFF"
        s.Brightness = 50
        s.IrCutFilter = "AUTO"
        imaging.SetImagingSettings({"VideoSourceToken": vs_token, "ImagingSettings": s, "ForcePersistence": True})
        return "set + restore OK"
    _()

    @check("Imaging.GetOptions")
    def _():
        o = imaging.GetOptions({"VideoSourceToken": vs_token})
        return f"brightness {o.Brightness.Min}..{o.Brightness.Max}, IR={o.IrCutFilterModes}"
    _()

    # ---- Events ------------------------------------------------------------------------------
    events = cam.create_events_service()

    @check("Events.GetEventProperties")
    def _():
        p = events.GetEventProperties()
        return f"dialects={len(p.TopicExpressionDialect)}"
    _()

    @check("Events.PullPoint: initial state + simulated motion")
    def _():
        sub = events.CreatePullPointSubscription({"InitialTerminationTime": "PT60S"})
        pullpoint = cam.create_pullpoint_service()
        first = pullpoint.PullMessages({"Timeout": "PT2S", "MessageLimit": 50})
        initial = len(first.NotificationMessage)
        got_motion = "not triggered (no --manager)"
        if a.manager and a.camera_id:
            httpx.post(f"{a.manager}/api/v1/cameras/{a.camera_id}/events/trigger",
                       json={"kind": "motion", "duration_s": 2}, headers={"Authorization": f"Bearer {a.token}"}, timeout=10).raise_for_status()
            msgs = pullpoint.PullMessages({"Timeout": "PT5S", "MessageLimit": 50}).NotificationMessage
            # zeep cannot read the mixed-content <wsnt:Topic> text, so inspect the tt:Message element
            changed = []
            for m in msgs:
                el = m.Message._value_1
                if el.get("PropertyOperation") == "Changed":
                    items = {i.get("Name"): i.get("Value") for i in el.iter("{http://www.onvif.org/ver10/schema}SimpleItem")}
                    changed.append(items)
            assert any(c.get("State") == "true" or c.get("IsMotion") == "true" for c in changed), changed
            got_motion = f"{len(changed)} Changed messages (motion=true)"
        # Unsubscribe lives on the SubscriptionManager binding (not in onvif-zeep's pullpoint service)
        raw_soap(sub.SubscriptionReference.Address._value_1,
                 '<wsnt:Unsubscribe xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"/>', a.user, a.password)
        return f"{initial} Initialized messages; {got_motion}; sub={sub.SubscriptionReference.Address._value_1}"
    _()

    # ---- DeviceIO ----------------------------------------------------------------------------
    @check("DeviceIO.GetDigitalInputs / relay toggle")
    def _():
        # onvif-zeep only reads top-level GetCapabilities; DeviceIO lives under Extension (per the
        # ONVIF schema), so take its XAddr from GetServices like a modern NVR does
        svc = {x.Namespace: x.XAddr for x in dev.GetServices({"IncludeCapability": False})}
        cam.xaddrs["http://www.onvif.org/ver10/deviceIO/wsdl"] = svc["http://www.onvif.org/ver10/deviceIO/wsdl"]
        io = cam.create_deviceio_service()
        inputs = io.GetDigitalInputs()
        relays = io.GetRelayOutputs()
        if relays:
            io.SetRelayOutputState({"RelayOutputToken": relays[0].token, "LogicalState": "active"})
            io.SetRelayOutputState({"RelayOutputToken": relays[0].token, "LogicalState": "inactive"})
        return f"{len(inputs)} inputs, {len(relays)} relays"
    _()

    # ---- PTZ ---------------------------------------------------------------------------------
    caps = dev.GetCapabilities({"Category": "All"})
    if caps.PTZ:
        ptz = cam.create_ptz_service()
        pt = next((p.token for p in profiles if p.PTZConfiguration), None)

        @check("PTZ.GetNodes / GetConfigurations")
        def _():
            return f"nodes={len(ptz.GetNodes())} configs={len(ptz.GetConfigurations())}"
        _()

        @check("PTZ.AbsoluteMove + GetStatus")
        def _():
            ptz.AbsoluteMove({"ProfileToken": pt, "Position": {"PanTilt": {"x": 0.5, "y": 0.2}, "Zoom": {"x": 0.5}}})
            time.sleep(3)
            s = ptz.GetStatus({"ProfileToken": pt})
            pos = s.Position
            assert abs(pos.PanTilt.x - 0.5) < 0.01 and abs(pos.Zoom.x - 0.5) < 0.01, pos
            return f"pan={pos.PanTilt.x} tilt={pos.PanTilt.y} zoom={pos.Zoom.x} status={s.MoveStatus.PanTilt}"
        _()

        @check("PTZ.SetPreset / GotoPreset / RemovePreset")
        def _():
            tok = ptz.SetPreset({"ProfileToken": pt, "PresetName": "Gate"})
            ptz.GotoHomePosition({"ProfileToken": pt})
            time.sleep(2.5)
            ptz.GotoPreset({"ProfileToken": pt, "PresetToken": tok})
            time.sleep(2.5)
            s = ptz.GetStatus({"ProfileToken": pt})
            assert abs(s.Position.PanTilt.x - 0.5) < 0.01
            n = len(ptz.GetPresets({"ProfileToken": pt}))
            ptz.RemovePreset({"ProfileToken": pt, "PresetToken": tok})
            return f"preset {tok} ok ({n} presets)"
        _()

        @check("PTZ.ContinuousMove + Stop")
        def _():
            ptz.ContinuousMove({"ProfileToken": pt, "Velocity": {"PanTilt": {"x": -0.5, "y": 0}}})
            time.sleep(1)
            moving = ptz.GetStatus({"ProfileToken": pt}).MoveStatus.PanTilt
            ptz.Stop({"ProfileToken": pt, "PanTilt": True, "Zoom": True})
            time.sleep(0.3)
            idle = ptz.GetStatus({"ProfileToken": pt}).MoveStatus.PanTilt
            assert moving == "MOVING" and idle == "IDLE", (moving, idle)
            ptz.GotoHomePosition({"ProfileToken": pt})
            return f"{moving} -> {idle}"
        _()

    # ---- users + auth ------------------------------------------------------------------------
    @check("Device.CreateUsers / login as new user / DeleteUsers")
    def _():
        dev.CreateUsers({"User": [{"Username": "nvrtest", "Password": "Nvr12345", "UserLevel": "Operator"}]})
        other = ONVIFCamera(a.host, a.port, "nvrtest", "Nvr12345")
        info = other.devicemgmt.GetDeviceInformation()
        dev.DeleteUsers({"Username": ["nvrtest"]})
        return f"logged in as Operator, model={info.Model}"
    _()

    @check("Wrong password is rejected")
    def _():
        bad = ONVIFCamera(a.host, a.port, a.user, "definitely-wrong")
        try:
            bad.devicemgmt.GetDeviceInformation()
        except Exception as exc:
            return f"rejected: {str(exc)[:50]}"
        raise AssertionError("accepted a wrong password")
    _()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{passed}/{len(RESULTS)} checks passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
