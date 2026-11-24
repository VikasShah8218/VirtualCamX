"""ONVIF Media service, Profile S (ver10/media/wsdl)."""
from app.cameras import operations as ops
from app.onvif import namespaces as NS
from app.onvif.dispatcher import Access, OnvifContext, onvif_operation
from app.onvif.faults import OnvifFault, no_config, no_profile
from app.onvif.handlers import service_caps
from app.onvif.handlers.common import int_range, osd_xml, profile1_xml, resolution, vec1_xml, vsc_xml
from app.onvif.xml import child, el, num, text

M = NS.MEDIA


def _resp(op: str, *content):
    return el(f"trt:{op}Response", *content)


def _profile(ctx: OnvifContext, token: str | None):
    p = ctx.state.profile(token or "")
    if p is None:
        raise no_profile(token)
    return p


@onvif_operation(M, "GetServiceCapabilities", Access.PRE_AUTH)
async def get_service_capabilities(ctx: OnvifContext):
    return _resp("GetServiceCapabilities", service_caps.media_caps(ctx))


# ---- profiles --------------------------------------------------------------------------------

@onvif_operation(M, "GetProfiles", Access.READ_MEDIA)
async def get_profiles(ctx: OnvifContext):
    st = ctx.state
    return _resp("GetProfiles", [profile1_xml("trt:Profiles", st, p) for p in st.profiles])


@onvif_operation(M, "GetProfile", Access.READ_MEDIA)
async def get_profile(ctx: OnvifContext):
    p = _profile(ctx, text(ctx.body, "ProfileToken"))
    return _resp("GetProfile", profile1_xml("trt:Profile", ctx.state, p))


@onvif_operation(M, "CreateProfile", Access.ACTUATE)
async def create_profile(ctx: OnvifContext):
    p = await ops.create_profile(ctx.runtime, text(ctx.body, "Name", default=""), text(ctx.body, "Token"))
    return _resp("CreateProfile", profile1_xml("trt:Profile", ctx.state, p))


@onvif_operation(M, "DeleteProfile", Access.ACTUATE)
async def delete_profile(ctx: OnvifContext):
    await ops.delete_profile(ctx.runtime, text(ctx.body, "ProfileToken", default=""))
    return _resp("DeleteProfile")


for _kind, _op in (("vsc", "VideoSourceConfiguration"), ("vec", "VideoEncoderConfiguration"), ("ptz", "PTZConfiguration")):
    def _make(kind=_kind, op=_op):
        @onvif_operation(M, f"Add{op}", Access.ACTUATE)
        async def add(ctx: OnvifContext):
            await ops.set_profile_ref(ctx.runtime, text(ctx.body, "ProfileToken", default=""), kind, text(ctx.body, "ConfigurationToken", default=""))
            return _resp(f"Add{op}")

        @onvif_operation(M, f"Remove{op}", Access.ACTUATE)
        async def remove(ctx: OnvifContext):
            await ops.set_profile_ref(ctx.runtime, text(ctx.body, "ProfileToken", default=""), kind, None)
            return _resp(f"Remove{op}")

    _make()


# ---- video sources ---------------------------------------------------------------------------

@onvif_operation(M, "GetVideoSources", Access.READ_MEDIA)
async def get_video_sources(ctx: OnvifContext):
    vs = ctx.state.video_source
    return _resp(
        "GetVideoSources",
        el("trt:VideoSources", el("tt:Framerate", vs.framerate), resolution("tt:Resolution", vs.width, vs.height), token=vs.token),
    )


@onvif_operation(M, "GetVideoSourceConfigurations", Access.READ_MEDIA)
async def get_vscs(ctx: OnvifContext):
    st = ctx.state
    return _resp("GetVideoSourceConfigurations", [vsc_xml("trt:Configurations", st, c) for c in st.video_source_configs])


@onvif_operation(M, "GetVideoSourceConfiguration", Access.READ_MEDIA)
async def get_vsc(ctx: OnvifContext):
    token = text(ctx.body, "ConfigurationToken")
    c = ctx.state.vsc(token or "")
    if c is None:
        raise no_config(token)
    return _resp("GetVideoSourceConfiguration", vsc_xml("trt:Configuration", ctx.state, c))


@onvif_operation(M, "GetCompatibleVideoSourceConfigurations", Access.READ_MEDIA)
async def get_compatible_vscs(ctx: OnvifContext):
    _profile(ctx, text(ctx.body, "ProfileToken"))
    st = ctx.state
    return _resp("GetCompatibleVideoSourceConfigurations", [vsc_xml("trt:Configurations", st, c) for c in st.video_source_configs])


@onvif_operation(M, "GetVideoSourceConfigurationOptions", Access.READ_MEDIA)
async def get_vsc_options(ctx: OnvifContext):
    vs = ctx.state.video_source
    return _resp(
        "GetVideoSourceConfigurationOptions",
        el(
            "trt:Options",
            el(
                "tt:BoundsRange",
                int_range("tt:XRange", 0, 0), int_range("tt:YRange", 0, 0),
                int_range("tt:WidthRange", vs.width, vs.width), int_range("tt:HeightRange", vs.height, vs.height),
            ),
            el("tt:VideoSourceTokensAvailable", vs.token),
        ),
    )


@onvif_operation(M, "SetVideoSourceConfiguration", Access.ACTUATE)
async def set_vsc(ctx: OnvifContext):
    cfg = child(ctx.body, "Configuration")
    token = cfg.get("token") if cfg is not None else None
    if not ctx.state.vsc(token or ""):
        raise no_config(token)
    name = text(cfg, "Name")
    if name:
        await ctx.runtime.update(lambda st: setattr(st.vsc(token), "name", name), {"video_source"})
    return _resp("SetVideoSourceConfiguration")


# ---- video encoders --------------------------------------------------------------------------

@onvif_operation(M, "GetVideoEncoderConfigurations", Access.READ_MEDIA)
async def get_vecs(ctx: OnvifContext):
    st = ctx.state
    return _resp("GetVideoEncoderConfigurations", [vec1_xml("trt:Configurations", st, e) for e in st.video_encoders])


@onvif_operation(M, "GetVideoEncoderConfiguration", Access.READ_MEDIA)
async def get_vec(ctx: OnvifContext):
    token = text(ctx.body, "ConfigurationToken")
    e = ctx.state.encoder(token or "")
    if e is None:
        raise no_config(token)
    return _resp("GetVideoEncoderConfiguration", vec1_xml("trt:Configuration", ctx.state, e))


@onvif_operation(M, "GetCompatibleVideoEncoderConfigurations", Access.READ_MEDIA)
async def get_compatible_vecs(ctx: OnvifContext):
    _profile(ctx, text(ctx.body, "ProfileToken"))
    st = ctx.state
    return _resp("GetCompatibleVideoEncoderConfigurations", [vec1_xml("trt:Configurations", st, e) for e in st.video_encoders])


def parse_media1_encoder(cfg) -> dict:
    enc = text(cfg, "Encoding")
    changes = {
        "name": text(cfg, "Name"),
        "width": num(cfg, "Resolution", "Width", cast=int),
        "height": num(cfg, "Resolution", "Height", cast=int),
        "quality": num(cfg, "Quality", cast=float),
        "fps": num(cfg, "RateControl", "FrameRateLimit", cast=int),
        "bitrate_kbps": num(cfg, "RateControl", "BitrateLimit", cast=int),
        "gov_length": num(cfg, "H264", "GovLength", cast=int),
        "h264_profile": text(cfg, "H264", "H264Profile"),
    }
    if enc in ("H264", "JPEG"):
        changes["encoding"] = enc
    if changes["h264_profile"] not in (None, "Baseline", "Main", "High"):
        changes["h264_profile"] = None
    return changes


@onvif_operation(M, "SetVideoEncoderConfiguration", Access.ACTUATE)
async def set_vec(ctx: OnvifContext):
    cfg = child(ctx.body, "Configuration")
    token = cfg.get("token") if cfg is not None else None
    e = ctx.state.encoder(token or "")
    if e is None:
        raise no_config(token)
    changes = parse_media1_encoder(cfg)
    if changes.get("encoding") == "H264" and e.encoding == "H265":
        changes.pop("encoding")  # Media1 cannot express H265; keep it unless the client asks for JPEG
    await ops.set_video_encoder(ctx.runtime, token, changes)
    return _resp("SetVideoEncoderConfiguration")


def _encoder_options_xml(tag: str, st, e) -> str:
    opts = st.capabilities.stream_options.get(e.stream_key) if e else None
    resolutions = [tuple(r) for r in opts.resolutions] if opts else [(e.width, e.height)]
    max_fps = opts.max_fps if opts else 30
    br = (opts.bitrate_min_kbps, opts.bitrate_max_kbps) if opts else (64, 16384)
    encodings = opts.encodings if opts else ["H264"]
    jpeg_res = [r for r in resolutions if r[0] % 8 == 0 and r[1] % 8 == 0 and r[0] <= 2040 and r[1] <= 2040]
    h264 = (
        el(
            "tt:H264",
            [resolution("tt:ResolutionsAvailable", w, h) for w, h in resolutions],
            int_range("tt:GovLengthRange", 1, 400),
            int_range("tt:FrameRateRange", 1, max_fps),
            int_range("tt:EncodingIntervalRange", 1, 1),
            [el("tt:H264ProfilesSupported", p) for p in ("Baseline", "Main", "High")],
        )
        if "H264" in encodings or "H265" in encodings
        else None
    )
    jpeg = (
        el(
            "tt:JPEG",
            [resolution("tt:ResolutionsAvailable", w, h) for w, h in jpeg_res],
            int_range("tt:FrameRateRange", 1, max_fps),
            int_range("tt:EncodingIntervalRange", 1, 1),
        )
        if "JPEG" in encodings and jpeg_res
        else None
    )
    ext = el(
        "tt:Extension",
        el("tt:JPEG", [resolution("tt:ResolutionsAvailable", w, h) for w, h in jpeg_res], int_range("tt:FrameRateRange", 1, max_fps),
           int_range("tt:EncodingIntervalRange", 1, 1), int_range("tt:BitrateRange", *br)) if jpeg else None,
        el("tt:H264", [resolution("tt:ResolutionsAvailable", w, h) for w, h in resolutions], int_range("tt:GovLengthRange", 1, 400),
           int_range("tt:FrameRateRange", 1, max_fps), int_range("tt:EncodingIntervalRange", 1, 1),
           [el("tt:H264ProfilesSupported", p) for p in ("Baseline", "Main", "High")], int_range("tt:BitrateRange", *br)) if h264 else None,
    )
    return el(tag, int_range("tt:QualityRange", 0, 10), jpeg, h264, ext)


@onvif_operation(M, "GetVideoEncoderConfigurationOptions", Access.READ_MEDIA)
async def get_vec_options(ctx: OnvifContext):
    st = ctx.state
    token = text(ctx.body, "ConfigurationToken")
    ptoken = text(ctx.body, "ProfileToken")
    e = None
    if token:
        e = st.encoder(token)
        if e is None:
            raise no_config(token)
    elif ptoken:
        p = _profile(ctx, ptoken)
        e = st.encoder(p.vec_token) if p.vec_token else None
    e = e or (st.video_encoders[0] if st.video_encoders else None)
    return _resp("GetVideoEncoderConfigurationOptions", _encoder_options_xml("trt:Options", st, e))


@onvif_operation(M, "GetGuaranteedNumberOfVideoEncoderInstances", Access.READ_MEDIA)
async def get_guaranteed_instances(ctx: OnvifContext):
    n = len(ctx.state.video_encoders)
    return _resp("GetGuaranteedNumberOfVideoEncoderInstances", el("trt:TotalNumber", n), el("trt:JPEG", 1), el("trt:H264", n))


# ---- audio / metadata / analytics (not supported in v1: empty lists) --------------------------

for _op, _tag in (
    ("GetAudioSources", None), ("GetAudioSourceConfigurations", None), ("GetAudioEncoderConfigurations", None),
    ("GetAudioOutputs", None), ("GetAudioOutputConfigurations", None), ("GetAudioDecoderConfigurations", None),
    ("GetMetadataConfigurations", None), ("GetVideoAnalyticsConfigurations", None), ("GetVideoOutputs", None),
    ("GetCompatibleAudioSourceConfigurations", None), ("GetCompatibleAudioEncoderConfigurations", None),
    ("GetCompatibleMetadataConfigurations", None), ("GetCompatibleVideoAnalyticsConfigurations", None),
):
    def _make_empty(op=_op):
        @onvif_operation(M, op, Access.READ_MEDIA)
        async def empty(ctx: OnvifContext):
            return _resp(op)

    _make_empty()


@onvif_operation(M, "GetMetadataConfigurationOptions", Access.READ_MEDIA)
async def get_metadata_options(ctx: OnvifContext):
    return _resp("GetMetadataConfigurationOptions", el("trt:Options", el("tt:PTZStatusFilterOptions", el("tt:PanTiltStatusSupported", False), el("tt:ZoomStatusSupported", False))))


# ---- streaming -------------------------------------------------------------------------------

def stream_key_for_profile(ctx: OnvifContext, token: str | None) -> str:
    p = _profile(ctx, token)
    e = ctx.state.encoder(p.vec_token) if p.vec_token else None
    if e is None:
        raise OnvifFault("Sender", ["ter:InvalidArgVal", "ter:IncompleteConfiguration"], "Profile has no video encoder configuration")
    return e.stream_key


@onvif_operation(M, "GetStreamUri", Access.READ_MEDIA)
async def get_stream_uri(ctx: OnvifContext):
    key = stream_key_for_profile(ctx, text(ctx.body, "ProfileToken"))
    stream = text(ctx.body, "StreamSetup", "Stream", default="RTP-Unicast")
    if stream == "RTP-Multicast":
        raise OnvifFault("Sender", ["ter:InvalidArgVal", "ter:InvalidStreamSetup"], "Multicast is not supported yet")
    return _resp(
        "GetStreamUri",
        el(
            "trt:MediaUri",
            el("tt:Uri", ctx.rtsp_url(key)),
            el("tt:InvalidAfterConnect", False),
            el("tt:InvalidAfterReboot", False),
            el("tt:Timeout", "PT0S"),
        ),
    )


@onvif_operation(M, "GetSnapshotUri", Access.READ_MEDIA)
async def get_snapshot_uri(ctx: OnvifContext):
    p = _profile(ctx, text(ctx.body, "ProfileToken"))
    return _resp(
        "GetSnapshotUri",
        el(
            "trt:MediaUri",
            el("tt:Uri", ctx.snapshot_url(p.token)),
            el("tt:InvalidAfterConnect", False),
            el("tt:InvalidAfterReboot", False),
            el("tt:Timeout", "PT0S"),
        ),
    )


@onvif_operation(M, "SetSynchronizationPoint", Access.ACTUATE)
async def set_synchronization_point(ctx: OnvifContext):
    _profile(ctx, text(ctx.body, "ProfileToken"))
    ctx.runtime.log("SetSynchronizationPoint (I-frame request)")
    return _resp("SetSynchronizationPoint")


@onvif_operation(M, "StartMulticastStreaming", Access.ACTUATE)
async def start_multicast(ctx: OnvifContext):
    raise OnvifFault("Receiver", ["ter:ActionNotSupported"], "Multicast is not supported yet")


@onvif_operation(M, "GetOSDs", Access.READ_MEDIA)
async def get_osds(ctx: OnvifContext):
    st = ctx.state
    return _resp("GetOSDs", [osd_xml("trt:OSDs", st, o) for o in st.osd])
