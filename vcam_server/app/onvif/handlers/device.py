"""ONVIF Device service (ver10/device/wsdl)."""
from datetime import datetime, timezone

from app.cameras import users as user_ops
from app.onvif import namespaces as NS
from app.onvif.dispatcher import Access, OnvifContext, onvif_operation
from app.onvif.faults import OnvifFault, invalid_arg
from app.onvif.handlers import service_caps
from app.onvif.xml import boolean, child, children, el, num, text

D = NS.DEVICE


def _resp(op: str, *content) -> str:
    return el(f"tds:{op}Response", *content)


# ---- identity / services ---------------------------------------------------------------------

@onvif_operation(D, "GetDeviceInformation", Access.READ_SYSTEM)
async def get_device_information(ctx: OnvifContext):
    i = ctx.state.identity
    return _resp(
        "GetDeviceInformation",
        el("tds:Manufacturer", i.manufacturer),
        el("tds:Model", i.model),
        el("tds:FirmwareVersion", i.firmware_version),
        el("tds:SerialNumber", i.serial_number),
        el("tds:HardwareId", i.hardware_id),
    )


@onvif_operation(D, "GetServices", Access.PRE_AUTH)
async def get_services(ctx: OnvifContext):
    include = boolean(ctx.body, "IncludeCapability", default=False)
    items = []
    for ns, caps in service_caps.services(ctx):
        major, minor = NS.SERVICE_VERSIONS[ns]
        items.append(
            el(
                "tds:Service",
                el("tds:Namespace", ns),
                el("tds:XAddr", ctx.xaddr(ns)),
                el("tds:Capabilities", caps(ctx)) if include else None,
                el("tds:Version", el("tt:Major", major), el("tt:Minor", minor)),
            )
        )
    return _resp("GetServices", items)


@onvif_operation(D, "GetServiceCapabilities", Access.PRE_AUTH)
async def get_service_capabilities(ctx: OnvifContext):
    return _resp("GetServiceCapabilities", service_caps.device_caps(ctx))


@onvif_operation(D, "GetCapabilities", Access.PRE_AUTH)
async def get_capabilities(ctx: OnvifContext):
    cats = {c.text.strip() for c in children(ctx.body, "Category") if c.text} or {"All"}
    st = ctx.state
    want = lambda c: "All" in cats or c in cats  # noqa: E731
    if not any(want(c) for c in ("Device", "Events", "Imaging", "Media", "PTZ")):
        raise OnvifFault("Receiver", ["ter:ActionNotSupported", "ter:NoSuchService"], "Requested capability category not supported")
    device = el(
        "tt:Device",
        el("tt:XAddr", ctx.xaddr(NS.DEVICE)),
        el("tt:Network", el("tt:IPFilter", False), el("tt:ZeroConfiguration", False), el("tt:IPVersion6", False), el("tt:DynDNS", False)),
        el(
            "tt:System",
            el("tt:DiscoveryResolve", True), el("tt:DiscoveryBye", True), el("tt:RemoteDiscovery", False),
            el("tt:SystemBackup", False), el("tt:SystemLogging", True), el("tt:FirmwareUpgrade", False),
            [el("tt:SupportedVersions", el("tt:Major", ma), el("tt:Minor", mi)) for ma, mi in ((2, 60), (2, 40), (2, 20), (2, 0))],
        ),
        el("tt:IO", el("tt:InputConnectors", len(st.io.inputs)), el("tt:RelayOutputs", len(st.io.relays))),
        el(
            "tt:Security",
            el("tt:TLS1.1", False), el("tt:TLS1.2", False), el("tt:OnboardKeyGeneration", False),
            el("tt:AccessPolicyConfig", False), el("tt:X.509Token", False), el("tt:SAMLToken", False),
            el("tt:KerberosToken", False), el("tt:RELToken", False),
        ),
    ) if want("Device") else None
    events = el(
        "tt:Events",
        el("tt:XAddr", ctx.xaddr(NS.EVENTS)),
        el("tt:WSSubscriptionPolicySupport", False),
        el("tt:WSPullPointSupport", True),
        el("tt:WSPausableSubscriptionManagerInterfaceSupport", False),
    ) if want("Events") else None
    imaging = el("tt:Imaging", el("tt:XAddr", ctx.xaddr(NS.IMAGING))) if want("Imaging") else None
    media = el(
        "tt:Media",
        el("tt:XAddr", ctx.xaddr(NS.MEDIA)),
        el("tt:StreamingCapabilities", el("tt:RTPMulticast", False), el("tt:RTP_TCP", True), el("tt:RTP_RTSP_TCP", True)),
        el("tt:Extension", el("tt:ProfileCapabilities", el("tt:MaximumNumberOfProfiles", st.capabilities.max_profiles))),
    ) if want("Media") else None
    ptz = el("tt:PTZ", el("tt:XAddr", ctx.xaddr(NS.PTZ))) if want("PTZ") and st.capabilities.has_ptz else None
    ext = el(
        "tt:Extension",
        el(
            "tt:DeviceIO",
            el("tt:XAddr", ctx.xaddr(NS.DEVICEIO)), el("tt:VideoSources", 1), el("tt:VideoOutputs", 0),
            el("tt:AudioSources", 0), el("tt:AudioOutputs", 0), el("tt:RelayOutputs", len(st.io.relays)),
        ),
    ) if "All" in cats else None
    return _resp("GetCapabilities", el("tds:Capabilities", device, events, imaging, media, ptz, ext))


@onvif_operation(D, "GetWsdlUrl", Access.PRE_AUTH)
async def get_wsdl_url(ctx: OnvifContext):
    return _resp("GetWsdlUrl", el("tds:WsdlUrl", "http://www.onvif.org/Documents/Specifications.aspx"))


@onvif_operation(D, "GetEndpointReference", Access.PRE_AUTH)
async def get_endpoint_reference(ctx: OnvifContext):
    return _resp("GetEndpointReference", el("tds:GUID", ctx.state.identity.endpoint_uuid))


# ---- date & time ---------------------------------------------------------------------------

def _dt_xml(tag: str, dt: datetime):
    return el(
        tag,
        el("tt:Time", el("tt:Hour", dt.hour), el("tt:Minute", dt.minute), el("tt:Second", dt.second)),
        el("tt:Date", el("tt:Year", dt.year), el("tt:Month", dt.month), el("tt:Day", dt.day)),
    )


@onvif_operation(D, "GetSystemDateAndTime", Access.PRE_AUTH)
async def get_system_date_and_time(ctx: OnvifContext):
    t = ctx.state.time
    rt = ctx.runtime
    return _resp(
        "GetSystemDateAndTime",
        el(
            "tds:SystemDateAndTime",
            el("tt:DateTimeType", t.date_time_type),
            el("tt:DaylightSavings", t.daylight_savings),
            el("tt:TimeZone", el("tt:TZ", t.tz)),
            _dt_xml("tt:UTCDateTime", rt.clock.now()),
            _dt_xml("tt:LocalDateTime", rt.local_time()),
        ),
    )


@onvif_operation(D, "SetSystemDateAndTime", Access.WRITE_SYSTEM)
async def set_system_date_and_time(ctx: OnvifContext):
    b = ctx.body
    dtype = text(b, "DateTimeType", default="Manual")
    if dtype not in ("Manual", "NTP"):
        raise invalid_arg("InvalidDateTime", f"Bad DateTimeType {dtype}")
    tz = text(b, "TimeZone", "TZ")
    dst = boolean(b, "DaylightSavings", default=False)
    new_offset = None
    utc = child(b, "UTCDateTime")
    if dtype == "Manual":
        if utc is None:
            raise invalid_arg("InvalidDateTime", "UTCDateTime required for Manual")
        try:
            camera_utc = datetime(
                num(utc, "Date", "Year", cast=int), num(utc, "Date", "Month", cast=int), num(utc, "Date", "Day", cast=int),
                num(utc, "Time", "Hour", cast=int), num(utc, "Time", "Minute", cast=int), num(utc, "Time", "Second", cast=int),
                tzinfo=timezone.utc,
            )
        except (TypeError, ValueError):
            raise invalid_arg("InvalidDateTime", "Invalid UTCDateTime") from None
        new_offset = ctx.runtime.clock.set_manual(camera_utc)

    def mut(st):
        st.time.date_time_type = dtype
        st.time.daylight_savings = bool(dst)
        if tz:
            st.time.tz = tz
        st.time.offset_seconds = new_offset if dtype == "Manual" else 0.0

    await ctx.runtime.update(mut, {"time"})
    ctx.runtime.log(f"date/time set ({dtype}, TZ={tz or ctx.state.time.tz})")
    return _resp("SetSystemDateAndTime")


# ---- network ---------------------------------------------------------------------------------

@onvif_operation(D, "GetHostname", Access.PRE_AUTH)
async def get_hostname(ctx: OnvifContext):
    n = ctx.state.network
    return _resp("GetHostname", el("tds:HostnameInformation", el("tt:FromDHCP", n.hostname_from_dhcp), el("tt:Name", n.hostname or ctx.runtime.name.replace(" ", "-"))))


@onvif_operation(D, "SetHostname", Access.WRITE_SYSTEM)
async def set_hostname(ctx: OnvifContext):
    name = text(ctx.body, "Name", default="")
    if not name or len(name) > 63:
        raise invalid_arg("InvalidHostname", "Invalid hostname")
    await ctx.runtime.update(lambda st: setattr(st.network, "hostname", name), {"network"})
    return _resp("SetHostname")


@onvif_operation(D, "SetHostnameFromDHCP", Access.WRITE_SYSTEM)
async def set_hostname_from_dhcp(ctx: OnvifContext):
    v = boolean(ctx.body, "FromDHCP", default=False)
    await ctx.runtime.update(lambda st: setattr(st.network, "hostname_from_dhcp", bool(v)), {"network"})
    return _resp("SetHostnameFromDHCP", el("tds:RebootNeeded", False))


@onvif_operation(D, "GetNetworkInterfaces", Access.READ_SYSTEM)
async def get_network_interfaces(ctx: OnvifContext):
    n = ctx.state.network
    ip = n.reported_ip or ctx.host
    cfg = el(
        "tt:Config",
        el("tt:Manual", el("tt:Address", ip), el("tt:PrefixLength", n.prefix_length)) if not n.dhcp else None,
        el("tt:FromDHCP", el("tt:Address", ip), el("tt:PrefixLength", n.prefix_length)) if n.dhcp else None,
        el("tt:DHCP", n.dhcp),
    )
    return _resp(
        "GetNetworkInterfaces",
        el(
            "tds:NetworkInterfaces",
            el("tt:Enabled", True),
            el("tt:Info", el("tt:Name", "eth0"), el("tt:HwAddress", ctx.state.identity.mac), el("tt:MTU", n.mtu)),
            el("tt:IPv4", el("tt:Enabled", True), cfg),
            token="eth0",
        ),
    )


@onvif_operation(D, "SetNetworkInterfaces", Access.WRITE_SYSTEM)
async def set_network_interfaces(ctx: OnvifContext):
    ni = child(ctx.body, "NetworkInterface")
    ipv4 = child(ni, "IPv4")
    dhcp = boolean(ipv4, "DHCP")
    addr = text(ipv4, "Manual", "Address")
    prefix = num(ipv4, "Manual", "PrefixLength", cast=int)
    mtu = num(ni, "MTU", cast=int)

    def mut(st):
        if dhcp is not None:
            st.network.dhcp = dhcp
        if addr:
            st.network.reported_ip = addr
        if prefix:
            st.network.prefix_length = prefix
        if mtu:
            st.network.mtu = mtu

    await ctx.runtime.update(mut, {"network"})
    ctx.runtime.log(f"network interface settings stored (reported only): ip={addr} dhcp={dhcp}")
    return _resp("SetNetworkInterfaces", el("tds:RebootNeeded", False))


@onvif_operation(D, "GetNetworkProtocols", Access.READ_SYSTEM)
async def get_network_protocols(ctx: OnvifContext):
    rt = ctx.runtime
    n = ctx.state.network
    protos = [("HTTP", n.http_enabled, rt.http_port_public()), ("HTTPS", False, 443), ("RTSP", n.rtsp_enabled, rt.rtsp_port())]
    return _resp(
        "GetNetworkProtocols",
        [el("tds:NetworkProtocols", el("tt:Name", name), el("tt:Enabled", en), el("tt:Port", port)) for name, en, port in protos],
    )


@onvif_operation(D, "SetNetworkProtocols", Access.WRITE_SYSTEM)
async def set_network_protocols(ctx: OnvifContext):
    ctx.runtime.log("SetNetworkProtocols received (stored ports are fixed by VirtualCamX; ignored)")
    return _resp("SetNetworkProtocols")


@onvif_operation(D, "GetNetworkDefaultGateway", Access.READ_SYSTEM)
async def get_network_default_gateway(ctx: OnvifContext):
    return _resp("GetNetworkDefaultGateway", el("tds:NetworkGateway", el("tt:IPv4Address", ctx.state.network.gateway)))


@onvif_operation(D, "SetNetworkDefaultGateway", Access.WRITE_SYSTEM)
async def set_network_default_gateway(ctx: OnvifContext):
    gw = text(ctx.body, "IPv4Address")
    if gw:
        await ctx.runtime.update(lambda st: setattr(st.network, "gateway", gw), {"network"})
    return _resp("SetNetworkDefaultGateway")


@onvif_operation(D, "GetDNS", Access.READ_SYSTEM)
async def get_dns(ctx: OnvifContext):
    n = ctx.state.network
    return _resp(
        "GetDNS",
        el(
            "tds:DNSInformation",
            el("tt:FromDHCP", n.dns_from_dhcp),
            [el("tt:DNSManual", el("tt:Type", "IPv4"), el("tt:IPv4Address", d)) for d in n.dns],
        ),
    )


@onvif_operation(D, "SetDNS", Access.WRITE_SYSTEM)
async def set_dns(ctx: OnvifContext):
    from_dhcp = boolean(ctx.body, "FromDHCP", default=False)
    servers = [text(d, "IPv4Address") for d in children(ctx.body, "DNSManual") if text(d, "IPv4Address")]

    def mut(st):
        st.network.dns_from_dhcp = bool(from_dhcp)
        st.network.dns = servers

    await ctx.runtime.update(mut, {"network"})
    return _resp("SetDNS")


@onvif_operation(D, "GetNTP", Access.READ_SYSTEM)
async def get_ntp(ctx: OnvifContext):
    n = ctx.state.network
    items = []
    for s in n.ntp:
        is_ip = all(p.isdigit() for p in s.split(".")) and s.count(".") == 3
        items.append(el("tt:NTPManual", el("tt:Type", "IPv4" if is_ip else "DNS"), el("tt:IPv4Address" if is_ip else "tt:DNSname", s)))
    return _resp("GetNTP", el("tds:NTPInformation", el("tt:FromDHCP", n.ntp_from_dhcp), items))


@onvif_operation(D, "SetNTP", Access.WRITE_SYSTEM)
async def set_ntp(ctx: OnvifContext):
    from_dhcp = boolean(ctx.body, "FromDHCP", default=False)
    servers = []
    for m in children(ctx.body, "NTPManual"):
        v = text(m, "IPv4Address") or text(m, "DNSname")
        if v:
            servers.append(v)

    def mut(st):
        st.network.ntp_from_dhcp = bool(from_dhcp)
        st.network.ntp = servers

    await ctx.runtime.update(mut, {"network"})
    return _resp("SetNTP")


@onvif_operation(D, "GetZeroConfiguration", Access.READ_SYSTEM)
async def get_zero_configuration(ctx: OnvifContext):
    return _resp("GetZeroConfiguration", el("tds:ZeroConfiguration", el("tt:InterfaceToken", "eth0"), el("tt:Enabled", False)))


@onvif_operation(D, "GetDiscoveryMode", Access.READ_SYSTEM)
async def get_discovery_mode(ctx: OnvifContext):
    return _resp("GetDiscoveryMode", el("tds:DiscoveryMode", ctx.state.network.discovery_mode))


@onvif_operation(D, "SetDiscoveryMode", Access.WRITE_SYSTEM)
async def set_discovery_mode(ctx: OnvifContext):
    mode = text(ctx.body, "DiscoveryMode")
    if mode not in ("Discoverable", "NonDiscoverable"):
        raise invalid_arg("InvalidArgVal", f"Bad DiscoveryMode {mode}")
    await ctx.runtime.update(lambda st: setattr(st.network, "discovery_mode", mode), {"network"})
    return _resp("SetDiscoveryMode")


# ---- scopes ----------------------------------------------------------------------------------

FIXED_SCOPE_PREFIXES = ("onvif://www.onvif.org/type/", "onvif://www.onvif.org/Profile/", "onvif://www.onvif.org/hardware/")


def _is_fixed(scope: str) -> bool:
    return scope.startswith(FIXED_SCOPE_PREFIXES)


@onvif_operation(D, "GetScopes", Access.READ_SYSTEM)
async def get_scopes(ctx: OnvifContext):
    return _resp(
        "GetScopes",
        [el("tds:Scopes", el("tt:ScopeDef", "Fixed" if _is_fixed(s) else "Configurable"), el("tt:ScopeItem", s)) for s in ctx.state.scopes],
    )


@onvif_operation(D, "SetScopes", Access.WRITE_SYSTEM)
async def set_scopes(ctx: OnvifContext):
    new = [c.text.strip() for c in children(ctx.body, "Scopes") if c.text and c.text.strip()]

    def mut(st):
        st.scopes = [s for s in st.scopes if _is_fixed(s)] + [s for s in new if not _is_fixed(s)]

    await ctx.runtime.update(mut, {"scopes"})
    return _resp("SetScopes")


@onvif_operation(D, "AddScopes", Access.WRITE_SYSTEM)
async def add_scopes(ctx: OnvifContext):
    new = [c.text.strip() for c in children(ctx.body, "ScopeItem") if c.text and c.text.strip()]

    def mut(st):
        for s in new:
            if s not in st.scopes:
                st.scopes.append(s)

    await ctx.runtime.update(mut, {"scopes"})
    return _resp("AddScopes")


@onvif_operation(D, "RemoveScopes", Access.WRITE_SYSTEM)
async def remove_scopes(ctx: OnvifContext):
    rm = [c.text.strip() for c in children(ctx.body, "ScopeItem") if c.text]
    for s in rm:
        if _is_fixed(s):
            raise OnvifFault("Sender", ["ter:OperationProhibited", "ter:FixedScope"], f"Scope {s} is fixed")
        if s not in ctx.state.scopes:
            raise invalid_arg("NoScope", f"Scope {s} does not exist")

    def mut(st):
        st.scopes = [s for s in st.scopes if s not in rm]

    await ctx.runtime.update(mut, {"scopes"})
    return _resp("RemoveScopes", [el("tds:ScopeItem", s) for s in rm])


# ---- users -----------------------------------------------------------------------------------

@onvif_operation(D, "GetUsers", Access.READ_SYSTEM_SECRET)
async def get_users(ctx: OnvifContext):
    return _resp(
        "GetUsers",
        [el("tds:User", el("tt:Username", u.username), el("tt:UserLevel", u.level)) for u in ctx.runtime.users.values()],
    )


@onvif_operation(D, "CreateUsers", Access.WRITE_SYSTEM)
async def create_users(ctx: OnvifContext):
    for u in children(ctx.body, "User"):
        await user_ops.create_user(ctx.runtime, text(u, "Username", default=""), text(u, "Password", default=""),
                                   text(u, "UserLevel", default="User"))
    return _resp("CreateUsers")


@onvif_operation(D, "SetUser", Access.WRITE_SYSTEM)
async def set_user(ctx: OnvifContext):
    for u in children(ctx.body, "User"):
        await user_ops.update_user(ctx.runtime, text(u, "Username", default=""), text(u, "Password"), text(u, "UserLevel"))
    return _resp("SetUser")


@onvif_operation(D, "DeleteUsers", Access.WRITE_SYSTEM)
async def delete_users(ctx: OnvifContext):
    for n in children(ctx.body, "Username"):
        await user_ops.delete_user(ctx.runtime, (n.text or "").strip())
    return _resp("DeleteUsers")


@onvif_operation(D, "GetRemoteUser", Access.READ_SYSTEM_SECRET)
async def get_remote_user(ctx: OnvifContext):
    return _resp("GetRemoteUser")


# ---- system ----------------------------------------------------------------------------------

@onvif_operation(D, "SystemReboot", Access.UNRECOVERABLE)
async def system_reboot(ctx: OnvifContext):
    from settings.settings import settings

    ctx.runtime.log(f"SystemReboot requested by {ctx.client_ip}")
    ctx.runtime.request_reboot()
    return _resp("SystemReboot", el("tds:Message", f"Rebooting in {settings.reboot_seconds} seconds"))


@onvif_operation(D, "SetSystemFactoryDefault", Access.UNRECOVERABLE)
async def set_system_factory_default(ctx: OnvifContext):
    from app.cameras.services import factory_default

    hard = text(ctx.body, "FactoryDefault", default="Soft") == "Hard"
    ctx.runtime.log(f"SetSystemFactoryDefault ({'Hard' if hard else 'Soft'}) by {ctx.client_ip}")
    await factory_default(ctx.runtime, hard)
    ctx.runtime.request_reboot()
    return _resp("SetSystemFactoryDefault")


@onvif_operation(D, "GetSystemLog", Access.READ_SYSTEM_SECRET)
async def get_system_log(ctx: OnvifContext):
    return _resp("GetSystemLog", el("tds:SystemLog", el("tt:String", "\n".join(ctx.runtime.logs))))


@onvif_operation(D, "GetSystemUris", Access.READ_SYSTEM_SECRET)
async def get_system_uris(ctx: OnvifContext):
    return _resp("GetSystemUris")


# ---- relay outputs ---------------------------------------------------------------------------

def relay_xml(tag: str, r):
    return el(
        tag,
        el("tt:Properties", el("tt:Mode", r.mode), el("tt:DelayTime", f"PT{r.delay_time_s}S"), el("tt:IdleState", r.idle_state)),
        token=r.token,
    )


@onvif_operation(D, "GetRelayOutputs", Access.READ_MEDIA)
async def get_relay_outputs(ctx: OnvifContext):
    return _resp("GetRelayOutputs", [relay_xml("tds:RelayOutputs", r) for r in ctx.state.io.relays])


async def apply_relay_settings(ctx: OnvifContext, token: str | None, props) -> None:
    from utilities.common import parse_iso_duration

    if not any(r.token == token for r in ctx.state.io.relays):
        raise invalid_arg("RelayToken", f"Unknown relay {token}")
    mode = text(props, "Mode")
    delay = parse_iso_duration(text(props, "DelayTime") or "")
    idle = text(props, "IdleState")

    def mut(st):
        r = next(r for r in st.io.relays if r.token == token)
        if mode in ("Bistable", "Monostable"):
            r.mode = mode
        if delay is not None:
            r.delay_time_s = int(delay)
        if idle in ("closed", "open"):
            r.idle_state = idle

    await ctx.runtime.update(mut, {"io"})


@onvif_operation(D, "SetRelayOutputSettings", Access.ACTUATE)
async def set_relay_output_settings(ctx: OnvifContext):
    await apply_relay_settings(ctx, text(ctx.body, "RelayOutputToken"), child(ctx.body, "Properties"))
    return _resp("SetRelayOutputSettings")


@onvif_operation(D, "SetRelayOutputState", Access.ACTUATE)
async def set_relay_output_state(ctx: OnvifContext):
    token = text(ctx.body, "RelayOutputToken")
    state = text(ctx.body, "LogicalState")
    try:
        ctx.runtime.set_relay(token, state == "active", origin=f"onvif:{ctx.client_ip}")
    except ValueError as exc:
        raise invalid_arg("RelayToken", str(exc)) from None
    return _resp("SetRelayOutputState")
