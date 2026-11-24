"""ONVIF Media2 service, Profile T (ver20/media/wsdl)."""
from app.cameras import operations as ops
from app.cameras.state import OsdItem
from app.onvif import namespaces as NS
from app.onvif.dispatcher import Access, OnvifContext, onvif_operation
from app.onvif.faults import OnvifFault, config_modify, no_config, no_profile
from app.onvif.handlers import service_caps
from app.onvif.handlers.common import int_range, osd_xml, ptz_config_xml, resolution, vec2_xml, vsc_xml
from app.onvif.xml import child, children, el, num, text

M2 = NS.MEDIA2
TYPE_TO_KIND = {"VideoSource": "vsc", "VideoEncoder": "vec", "PTZ": "ptz"}


def _resp(op: str, *content):
    return el(f"tr2:{op}Response", *content)


def _profile(ctx: OnvifContext, token: str | None):
    p = ctx.state.profile(token or "")
    if p is None:
        raise no_profile(token)
    return p


def profile2_xml(st, p, types: set[str]):
    want = lambda t: "All" in types or t in types  # noqa: E731
    vsc = st.vsc(p.vsc_token) if p.vsc_token else None
    vec = st.encoder(p.vec_token) if p.vec_token else None
    ptz = st.ptz_config(p.ptz_token) if p.ptz_token else None
    confs = [
        vsc_xml("tr2:VideoSource", st, vsc) if vsc and want("VideoSource") else None,
        vec2_xml("tr2:VideoEncoder", st, vec) if vec and want("VideoEncoder") else None,
        ptz_config_xml("tr2:PTZ", st, ptz) if ptz and want("PTZ") else None,
    ]
    confs = [c for c in confs if c]
    return el("tr2:Profiles", el("tr2:Name", p.name), el("tr2:Configurations", confs) if confs else None, token=p.token, fixed=p.fixed)


@onvif_operation(M2, "GetServiceCapabilities", Access.PRE_AUTH)
async def get_service_capabilities(ctx: OnvifContext):
    return _resp("GetServiceCapabilities", service_caps.media2_caps(ctx))


@onvif_operation(M2, "GetProfiles", Access.READ_MEDIA)
async def get_profiles(ctx: OnvifContext):
    st = ctx.state
    token = text(ctx.body, "Token")
    types = {(c.text or "").strip() for c in children(ctx.body, "Type")}
    profiles = st.profiles
    if token:
        profiles = [_profile(ctx, token)]
    return _resp("GetProfiles", [profile2_xml(st, p, types) for p in profiles])


def _configs(body) -> list[tuple[str, str | None]]:
    return [(text(c, "Type", default=""), text(c, "Token")) for c in children(body, "Configuration")]


@onvif_operation(M2, "CreateProfile", Access.ACTUATE)
async def create_profile(ctx: OnvifContext):
    p = await ops.create_profile(ctx.runtime, text(ctx.body, "Name", default=""))
    for ctype, ctoken in _configs(ctx.body):
        kind = TYPE_TO_KIND.get(ctype)
        if kind and ctoken:
            await ops.set_profile_ref(ctx.runtime, p.token, kind, ctoken)
    return _resp("CreateProfile", el("tr2:Token", p.token))


@onvif_operation(M2, "DeleteProfile", Access.ACTUATE)
async def delete_profile(ctx: OnvifContext):
    await ops.delete_profile(ctx.runtime, text(ctx.body, "Token", default=""))
    return _resp("DeleteProfile")


@onvif_operation(M2, "AddConfiguration", Access.ACTUATE)
async def add_configuration(ctx: OnvifContext):
    ptoken = text(ctx.body, "ProfileToken", default="")
    _profile(ctx, ptoken)
    name = text(ctx.body, "Name")
    if name:
        await ctx.runtime.update(lambda st: setattr(st.profile(ptoken), "name", name), {"profiles"})
    for ctype, ctoken in _configs(ctx.body):
        kind = TYPE_TO_KIND.get(ctype)
        if kind is None:
            raise OnvifFault("Sender", ["ter:InvalidArgVal", "ter:ConfigurationConflict"], f"Configuration type {ctype} not supported")
        if not ctoken:  # pick the first configuration of that type
            pool = {"vsc": ctx.state.video_source_configs, "vec": ctx.state.video_encoders, "ptz": ctx.state.ptz_configs}[kind]
            if not pool:
                raise no_config(None)
            ctoken = pool[0].token
        await ops.set_profile_ref(ctx.runtime, ptoken, kind, ctoken)
    return _resp("AddConfiguration")


@onvif_operation(M2, "RemoveConfiguration", Access.ACTUATE)
async def remove_configuration(ctx: OnvifContext):
    ptoken = text(ctx.body, "ProfileToken", default="")
    _profile(ctx, ptoken)
    for ctype, _ in _configs(ctx.body):
        kind = TYPE_TO_KIND.get(ctype)
        if kind:
            await ops.set_profile_ref(ctx.runtime, ptoken, kind, None)
    return _resp("RemoveConfiguration")


# ---- configurations ----------------------------------------------------------------------------

def _filter_configs(ctx: OnvifContext, kind: str, items: list):
    ctoken = text(ctx.body, "ConfigurationToken")
    ptoken = text(ctx.body, "ProfileToken")
    if ctoken:
        items = [i for i in items if i.token == ctoken]
        if not items:
            raise no_config(ctoken)
    elif ptoken:
        p = _profile(ctx, ptoken)
        ref = getattr(p, f"{kind}_token")
        items = [i for i in items if i.token == ref]
    return items


@onvif_operation(M2, "GetVideoSourceConfigurations", Access.READ_MEDIA)
async def get_vscs(ctx: OnvifContext):
    st = ctx.state
    return _resp("GetVideoSourceConfigurations", [vsc_xml("tr2:Configurations", st, c) for c in _filter_configs(ctx, "vsc", st.video_source_configs)])


@onvif_operation(M2, "GetVideoEncoderConfigurations", Access.READ_MEDIA)
async def get_vecs(ctx: OnvifContext):
    st = ctx.state
    return _resp("GetVideoEncoderConfigurations", [vec2_xml("tr2:Configurations", st, e) for e in _filter_configs(ctx, "vec", st.video_encoders)])


@onvif_operation(M2, "SetVideoEncoderConfiguration", Access.ACTUATE)
async def set_vec(ctx: OnvifContext):
    cfg = child(ctx.body, "Configuration")
    token = cfg.get("token") if cfg is not None else None
    if not ctx.state.encoder(token or ""):
        raise no_config(token)
    rc = child(cfg, "RateControl")
    encoding = text(cfg, "Encoding")
    if encoding is not None and encoding not in ("H264", "H265", "JPEG"):
        raise config_modify(f"Encoding {encoding} not supported")
    profile = cfg.get("Profile")
    cbr = rc.get("ConstantBitRate") if rc is not None else None
    changes = {
        "name": text(cfg, "Name"),
        "encoding": encoding,
        "width": num(cfg, "Resolution", "Width", cast=int),
        "height": num(cfg, "Resolution", "Height", cast=int),
        "quality": num(cfg, "Quality", cast=float),
        "fps": num(rc, "FrameRateLimit", cast=int),
        "bitrate_kbps": num(rc, "BitrateLimit", cast=int),
        "gov_length": int(cfg.get("GovLength")) if (cfg.get("GovLength") or "").isdigit() else None,
        "h264_profile": profile if profile in ("Baseline", "Main", "High") else None,
        "rc_mode": None if cbr is None else ("CBR" if cbr.lower() in ("true", "1") else "VBR"),
    }
    await ops.set_video_encoder(ctx.runtime, token, changes)
    return _resp("SetVideoEncoderConfiguration")


@onvif_operation(M2, "SetVideoSourceConfiguration", Access.ACTUATE)
async def set_vsc(ctx: OnvifContext):
    cfg = child(ctx.body, "Configuration")
    token = cfg.get("token") if cfg is not None else None
    if not ctx.state.vsc(token or ""):
        raise no_config(token)
    name = text(cfg, "Name")
    if name:
        await ctx.runtime.update(lambda st: setattr(st.vsc(token), "name", name), {"video_source"})
    return _resp("SetVideoSourceConfiguration")


@onvif_operation(M2, "GetVideoSourceConfigurationOptions", Access.READ_MEDIA)
async def get_vsc_options(ctx: OnvifContext):
    vs = ctx.state.video_source
    return _resp(
        "GetVideoSourceConfigurationOptions",
        el(
            "tr2:Options",
            el(
                "tt:BoundsRange",
                int_range("tt:XRange", 0, 0), int_range("tt:YRange", 0, 0),
                int_range("tt:WidthRange", vs.width, vs.width), int_range("tt:HeightRange", vs.height, vs.height),
            ),
            el("tt:VideoSourceTokensAvailable", vs.token),
            MaximumNumberOfProfiles=ctx.state.capabilities.max_profiles,
        ),
    )


@onvif_operation(M2, "GetVideoEncoderConfigurationOptions", Access.READ_MEDIA)
async def get_vec_options(ctx: OnvifContext):
    st = ctx.state
    encoders = _filter_configs(ctx, "vec", st.video_encoders) or st.video_encoders[:1]
    out = []
    for e in encoders:
        opts = st.capabilities.stream_options.get(e.stream_key)
        resolutions = [tuple(r) for r in opts.resolutions] if opts else [(e.width, e.height)]
        max_fps = opts.max_fps if opts else 30
        br = (opts.bitrate_min_kbps, opts.bitrate_max_kbps) if opts else (64, 16384)
        rates = " ".join(str(f) for f in (30, 25, 20, 15, 12, 10, 8, 5, 3, 1) if f <= max_fps)
        for enc in (opts.encodings if opts else ["H264"]):
            res = resolutions
            if enc == "JPEG":
                res = [r for r in resolutions if r[0] % 8 == 0 and r[1] % 8 == 0 and r[0] <= 2040 and r[1] <= 2040]
                if not res:
                    continue
            attrs = {"FrameRatesSupported": rates, "ConstantBitRateSupported": True}
            if enc != "JPEG":
                attrs["GovLengthRange"] = "1 400"
                attrs["ProfilesSupported"] = "Baseline Main High" if enc == "H264" else "Main"
            out.append(
                el(
                    "tr2:Options",
                    el("tt:Encoding", enc),
                    el("tt:QualityRange", el("tt:Min", 0), el("tt:Max", 10)),
                    [resolution("tt:ResolutionsAvailable", w, h) for w, h in res],
                    int_range("tt:BitrateRange", *br),
                    **attrs,
                )
            )
    return _resp("GetVideoEncoderConfigurationOptions", out)


@onvif_operation(M2, "GetVideoEncoderInstances", Access.READ_MEDIA)
async def get_video_encoder_instances(ctx: OnvifContext):
    n = len(ctx.state.video_encoders)
    return _resp(
        "GetVideoEncoderInstances",
        el("tr2:Info", [el("tr2:Codec", el("tr2:Encoding", e), el("tr2:Number", n)) for e in ("H264", "H265", "JPEG")], el("tr2:Total", n)),
    )


for _op in (
    "GetAudioSourceConfigurations", "GetAudioEncoderConfigurations", "GetMetadataConfigurations",
    "GetAudioOutputConfigurations", "GetAudioDecoderConfigurations", "GetAnalyticsConfigurations", "GetMasks",
):
    def _make_empty(op=_op):
        @onvif_operation(M2, op, Access.READ_MEDIA)
        async def empty(ctx: OnvifContext):
            return _resp(op)

    _make_empty()


# ---- streaming ---------------------------------------------------------------------------------

def _stream_key(ctx: OnvifContext, ptoken: str | None) -> str:
    p = _profile(ctx, ptoken)
    e = ctx.state.encoder(p.vec_token) if p.vec_token else None
    if e is None:
        raise OnvifFault("Sender", ["ter:InvalidArgVal", "ter:IncompleteConfiguration"], "Profile has no video encoder configuration")
    return e.stream_key


@onvif_operation(M2, "GetStreamUri", Access.READ_MEDIA)
async def get_stream_uri(ctx: OnvifContext):
    proto = text(ctx.body, "Protocol", default="RTSP")
    key = _stream_key(ctx, text(ctx.body, "ProfileToken"))
    if proto in ("RtspMulticast", "RTSPS", "RtspsUnicast", "RtspsMulticast"):
        raise OnvifFault("Sender", ["ter:InvalidArgVal", "ter:InvalidStreamSetup"], f"Protocol {proto} is not supported yet")
    return _resp("GetStreamUri", el("tr2:Uri", ctx.rtsp_url(key)))


@onvif_operation(M2, "GetSnapshotUri", Access.READ_MEDIA)
async def get_snapshot_uri(ctx: OnvifContext):
    p = _profile(ctx, text(ctx.body, "ProfileToken"))
    return _resp("GetSnapshotUri", el("tr2:Uri", ctx.snapshot_url(p.token)))


@onvif_operation(M2, "SetSynchronizationPoint", Access.ACTUATE)
async def set_synchronization_point(ctx: OnvifContext):
    _profile(ctx, text(ctx.body, "ProfileToken"))
    return _resp("SetSynchronizationPoint")


# ---- OSD ---------------------------------------------------------------------------------------

@onvif_operation(M2, "GetOSDs", Access.READ_MEDIA)
async def get_osds(ctx: OnvifContext):
    st = ctx.state
    token = text(ctx.body, "OSDToken")
    items = [o for o in st.osd if not token or o.token == token]
    if token and not items:
        raise no_config(token)
    return _resp("GetOSDs", [osd_xml("tr2:OSDs", st, o) for o in items])


@onvif_operation(M2, "GetOSDOptions", Access.READ_MEDIA)
async def get_osd_options(ctx: OnvifContext):
    st = ctx.state
    return _resp(
        "GetOSDOptions",
        el(
            "tr2:OSDOptions",
            el("tt:MaximumNumberOfOSDs", Total=st.capabilities.max_osd, PlainText=st.capabilities.max_osd, Date=1, Time=1, DateAndTime=1),
            el("tt:Type", "Text"),
            [el("tt:PositionOption", p) for p in ("UpperLeft", "UpperRight", "LowerLeft", "LowerRight", "Custom")],
            el(
                "tt:TextOption",
                [el("tt:Type", t) for t in ("Plain", "Date", "Time", "DateAndTime")],
                int_range("tt:FontSizeRange", 12, 96),
                [el("tt:DateFormat", f) for f in ("yyyy-MM-dd", "MM/dd/yyyy", "dd/MM/yyyy", "yyyy/MM/dd")],
                [el("tt:TimeFormat", f) for f in ("HH:mm:ss", "hh:mm:ss tt")],
            ),
        ),
    )


def _parse_osd(node, token: str | None) -> OsdItem:
    ts = child(node, "TextString")
    kind = text(ts, "Type", default="Plain")
    if kind not in ("Plain", "Date", "Time", "DateAndTime"):
        raise config_modify(f"OSD text type {kind} not supported")
    pos_type = text(node, "Position", "Type", default="UpperLeft")
    if pos_type not in ("UpperLeft", "UpperRight", "LowerLeft", "LowerRight", "Custom"):
        pos_type = "Custom"
    pos = child(node, "Position", "Pos")
    return OsdItem(
        token=token or "NEW",
        kind=kind,
        plain_text=text(ts, "PlainText", default="") or "",
        position=pos_type,
        x=float(pos.get("x", -1)) if pos is not None else -1.0,
        y=float(pos.get("y", 1)) if pos is not None else 1.0,
        font_size=num(ts, "FontSize", default=32, cast=int),
        date_format=text(ts, "DateFormat", default="yyyy-MM-dd"),
        time_format=text(ts, "TimeFormat", default="HH:mm:ss"),
    )


@onvif_operation(M2, "CreateOSD", Access.ACTUATE)
async def create_osd(ctx: OnvifContext):
    item = await ops.upsert_osd(ctx.runtime, _parse_osd(child(ctx.body, "OSD"), None), create=True)
    return _resp("CreateOSD", el("tr2:OSDToken", item.token))


@onvif_operation(M2, "SetOSD", Access.ACTUATE)
async def set_osd(ctx: OnvifContext):
    node = child(ctx.body, "OSD")
    token = node.get("token") if node is not None else None
    await ops.upsert_osd(ctx.runtime, _parse_osd(node, token), create=False)
    return _resp("SetOSD")


@onvif_operation(M2, "DeleteOSD", Access.ACTUATE)
async def delete_osd(ctx: OnvifContext):
    await ops.delete_osd(ctx.runtime, text(ctx.body, "OSDToken", default=""))
    return _resp("DeleteOSD")
