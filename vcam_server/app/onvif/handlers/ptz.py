"""ONVIF PTZ service (ver20/ptz/wsdl). Virtual PTZ; in Encode mode the picture really pans/zooms."""
from app.cameras import operations as ops
from app.onvif import namespaces as NS
from app.onvif.dispatcher import Access, OnvifContext, onvif_operation
from app.onvif.faults import OnvifFault, invalid_arg, no_config, no_profile
from app.onvif.handlers import service_caps
from app.onvif.handlers.common import PT_POS, Z_POS, ptz_config_xml, ptz_spaces_xml
from app.onvif.xml import boolean, child, el, text
from utilities.common import iso_z, parse_iso_duration

P = NS.PTZ


def _resp(op: str, *content):
    return el(f"tptz:{op}Response", *content)


def _need_ptz(ctx: OnvifContext) -> None:
    if not ctx.state.capabilities.has_ptz:
        raise OnvifFault("Receiver", ["ter:ActionNotSupported", "ter:PTZNotSupported"], "This camera has no PTZ")


def _ptz_profile(ctx: OnvifContext):
    _need_ptz(ctx)
    token = text(ctx.body, "ProfileToken")
    p = ctx.state.profile(token or "")
    if p is None:
        raise no_profile(token)
    if not p.ptz_token:
        raise invalid_arg("NoPTZProfile", f"Profile {token} has no PTZ configuration")
    return p


def _vec(node, name: str) -> tuple[float | None, float | None]:
    n = child(node, name)
    if n is None:
        return None, None
    x = n.get("x")
    y = n.get("y")
    return (float(x) if x is not None else None, float(y) if y is not None else None)


def _speeds(ctx: OnvifContext, node) -> tuple[float, float]:
    cfg = ctx.state.ptz_configs[0] if ctx.state.ptz_configs else None
    pt, _ = _vec(node, "PanTilt") if node is not None else (None, None)
    z, _ = _vec(node, "Zoom") if node is not None else (None, None)
    # ONVIF speed 0..1; the controller's 1.0 = full speed, so the default 0.5 maps to 1.0
    pt_speed = pt if pt is not None else (cfg.default_pan_tilt_speed if cfg else 0.5)
    z_speed = z if z is not None else (cfg.default_zoom_speed if cfg else 0.5)
    return pt_speed * 2, z_speed * 2


@onvif_operation(P, "GetServiceCapabilities", Access.PRE_AUTH)
async def get_service_capabilities(ctx: OnvifContext):
    return _resp("GetServiceCapabilities", service_caps.ptz_caps(ctx))


def _node_xml(tag: str, ctx: OnvifContext):
    return el(
        tag,
        el("tt:Name", "PTZNode_1"),
        ptz_spaces_xml("tt:SupportedPTZSpaces"),
        el("tt:MaximumNumberOfPresets", ctx.state.ptz.max_presets),
        el("tt:HomeSupported", True),
        token="PTZNode_1",
        FixedHomePosition=False,
        GeoMove=False,
    )


@onvif_operation(P, "GetNodes", Access.READ_SYSTEM)
async def get_nodes(ctx: OnvifContext):
    return _resp("GetNodes", _node_xml("tptz:PTZNode", ctx) if ctx.state.capabilities.has_ptz else None)


@onvif_operation(P, "GetNode", Access.READ_SYSTEM)
async def get_node(ctx: OnvifContext):
    _need_ptz(ctx)
    if text(ctx.body, "NodeToken") != "PTZNode_1":
        raise invalid_arg("NoEntity", "No such PTZ node")
    return _resp("GetNode", _node_xml("tptz:PTZNode", ctx))


@onvif_operation(P, "GetConfigurations", Access.READ_MEDIA)
async def get_configurations(ctx: OnvifContext):
    st = ctx.state
    return _resp("GetConfigurations", [ptz_config_xml("tptz:PTZConfiguration", st, c) for c in st.ptz_configs])


@onvif_operation(P, "GetConfiguration", Access.READ_MEDIA)
async def get_configuration(ctx: OnvifContext):
    token = text(ctx.body, "PTZConfigurationToken")
    c = ctx.state.ptz_config(token or "")
    if c is None:
        raise no_config(token)
    return _resp("GetConfiguration", ptz_config_xml("tptz:PTZConfiguration", ctx.state, c))


@onvif_operation(P, "GetConfigurationOptions", Access.READ_MEDIA)
async def get_configuration_options(ctx: OnvifContext):
    token = text(ctx.body, "ConfigurationToken")
    if not ctx.state.ptz_config(token or ""):
        raise no_config(token)
    return _resp(
        "GetConfigurationOptions",
        el(
            "tptz:PTZConfigurationOptions",
            ptz_spaces_xml("tt:Spaces"),
            el("tt:PTZTimeout", el("tt:Min", "PT1S"), el("tt:Max", "PT60S")),
        ),
    )


@onvif_operation(P, "SetConfiguration", Access.ACTUATE)
async def set_configuration(ctx: OnvifContext):
    cfg = child(ctx.body, "PTZConfiguration")
    token = cfg.get("token") if cfg is not None else None
    if not ctx.state.ptz_config(token or ""):
        raise no_config(token)
    timeout = parse_iso_duration(text(cfg, "DefaultPTZTimeout") or "")
    name = text(cfg, "Name")

    def mut(st):
        c = st.ptz_config(token)
        if timeout:
            c.default_timeout_s = int(timeout)
        if name:
            c.name = name

    await ctx.runtime.update(mut, {"ptz"})
    return _resp("SetConfiguration")


@onvif_operation(P, "GetCompatibleConfigurations", Access.READ_MEDIA)
async def get_compatible_configurations(ctx: OnvifContext):
    st = ctx.state
    return _resp("GetCompatibleConfigurations", [ptz_config_xml("tptz:PTZConfiguration", st, c) for c in st.ptz_configs])


# ---- movement --------------------------------------------------------------------------------

@onvif_operation(P, "ContinuousMove", Access.ACTUATE)
async def continuous_move(ctx: OnvifContext):
    _ptz_profile(ctx)
    vel = child(ctx.body, "Velocity")
    vx, vy = _vec(vel, "PanTilt")
    vz, _ = _vec(vel, "Zoom")
    timeout = parse_iso_duration(text(ctx.body, "Timeout") or "")
    if timeout is None:
        timeout = ctx.state.ptz_configs[0].default_timeout_s if ctx.state.ptz_configs else 5
    ctx.runtime.ptz.continuous(vx or 0.0, vy or 0.0, vz or 0.0, timeout)
    return _resp("ContinuousMove")


@onvif_operation(P, "AbsoluteMove", Access.ACTUATE)
async def absolute_move(ctx: OnvifContext):
    _ptz_profile(ctx)
    pos = child(ctx.body, "Position")
    px, py = _vec(pos, "PanTilt")
    pz, _ = _vec(pos, "Zoom")
    for v, lo in ((px, -1), (py, -1), (pz, 0)):
        if v is not None and not lo <= v <= 1:
            raise invalid_arg("InvalidPosition", "Position out of range")
    pts, zs = _speeds(ctx, child(ctx.body, "Speed"))
    ctx.runtime.ptz.absolute(px, py, pz, pts, zs)
    return _resp("AbsoluteMove")


@onvif_operation(P, "RelativeMove", Access.ACTUATE)
async def relative_move(ctx: OnvifContext):
    _ptz_profile(ctx)
    tr = child(ctx.body, "Translation")
    dx, dy = _vec(tr, "PanTilt")
    dz, _ = _vec(tr, "Zoom")
    pts, zs = _speeds(ctx, child(ctx.body, "Speed"))
    ctx.runtime.ptz.relative(dx or 0.0, dy or 0.0, dz or 0.0, pts, zs)
    return _resp("RelativeMove")


@onvif_operation(P, "Stop", Access.ACTUATE)
async def stop(ctx: OnvifContext):
    _ptz_profile(ctx)
    pt = boolean(ctx.body, "PanTilt", default=True)
    z = boolean(ctx.body, "Zoom", default=True)
    ctx.runtime.ptz.stop(pan_tilt=bool(pt), zoom=bool(z))
    return _resp("Stop")


@onvif_operation(P, "GetStatus", Access.READ_MEDIA)
async def get_status(ctx: OnvifContext):
    _ptz_profile(ctx)
    p = ctx.runtime.ptz
    return _resp(
        "GetStatus",
        el(
            "tptz:PTZStatus",
            el("tt:Position", el("tt:PanTilt", x=round(p.pan, 4), y=round(p.tilt, 4), space=PT_POS), el("tt:Zoom", x=round(p.zoom, 4), space=Z_POS)),
            el("tt:MoveStatus", el("tt:PanTilt", "MOVING" if p.pt_moving else "IDLE"), el("tt:Zoom", "MOVING" if p.zoom_moving else "IDLE")),
            el("tt:UtcTime", iso_z(ctx.runtime.clock.now())),
        ),
    )


# ---- presets / home --------------------------------------------------------------------------

@onvif_operation(P, "GetPresets", Access.READ_MEDIA)
async def get_presets(ctx: OnvifContext):
    _ptz_profile(ctx)
    return _resp(
        "GetPresets",
        [
            el(
                "tptz:Preset",
                el("tt:Name", pr.name),
                el("tt:PTZPosition", el("tt:PanTilt", x=pr.pan, y=pr.tilt, space=PT_POS), el("tt:Zoom", x=pr.zoom, space=Z_POS)),
                token=pr.token,
            )
            for pr in sorted(ctx.state.ptz.presets, key=lambda p: (len(p.token), p.token))
        ],
    )


@onvif_operation(P, "SetPreset", Access.ACTUATE)
async def set_preset(ctx: OnvifContext):
    _ptz_profile(ctx)
    token = await ops.set_preset(ctx.runtime, text(ctx.body, "PresetName"), text(ctx.body, "PresetToken"))
    return _resp("SetPreset", el("tptz:PresetToken", token))


@onvif_operation(P, "RemovePreset", Access.ACTUATE)
async def remove_preset(ctx: OnvifContext):
    _ptz_profile(ctx)
    await ops.remove_preset(ctx.runtime, text(ctx.body, "PresetToken", default=""))
    return _resp("RemovePreset")


@onvif_operation(P, "GotoPreset", Access.ACTUATE)
async def goto_preset(ctx: OnvifContext):
    _ptz_profile(ctx)
    token = text(ctx.body, "PresetToken")
    pr = next((p for p in ctx.state.ptz.presets if p.token == token), None)
    if pr is None:
        raise invalid_arg("NoToken", f"Preset {token} does not exist")
    pts, zs = _speeds(ctx, child(ctx.body, "Speed"))
    ctx.runtime.ptz.absolute(pr.pan, pr.tilt, pr.zoom, pts, zs)
    return _resp("GotoPreset")


@onvif_operation(P, "GotoHomePosition", Access.ACTUATE)
async def goto_home(ctx: OnvifContext):
    _ptz_profile(ctx)
    h = ctx.state.ptz
    pts, zs = _speeds(ctx, child(ctx.body, "Speed"))
    ctx.runtime.ptz.absolute(h.home_pan, h.home_tilt, h.home_zoom, pts, zs)
    return _resp("GotoHomePosition")


@onvif_operation(P, "SetHomePosition", Access.ACTUATE)
async def set_home(ctx: OnvifContext):
    _ptz_profile(ctx)
    await ops.set_home(ctx.runtime)
    return _resp("SetHomePosition")

