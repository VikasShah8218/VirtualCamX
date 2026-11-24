"""XML fragments shared by several ONVIF services (tt: schema types)."""
from app.cameras.state import CameraState, MediaProfile, OsdItem, PtzConfigModel, VideoEncoderConfig, VideoSourceConfig
from app.onvif.xml import Xml, el

PT_POS = "http://www.onvif.org/ver10/tptz/PanTiltSpaces/PositionGenericSpace"
Z_POS = "http://www.onvif.org/ver10/tptz/ZoomSpaces/PositionGenericSpace"
PT_TRANS = "http://www.onvif.org/ver10/tptz/PanTiltSpaces/TranslationGenericSpace"
Z_TRANS = "http://www.onvif.org/ver10/tptz/ZoomSpaces/TranslationGenericSpace"
PT_VEL = "http://www.onvif.org/ver10/tptz/PanTiltSpaces/VelocityGenericSpace"
Z_VEL = "http://www.onvif.org/ver10/tptz/ZoomSpaces/VelocityGenericSpace"
PT_SPEED = "http://www.onvif.org/ver10/tptz/PanTiltSpaces/GenericSpeedSpace"
Z_SPEED = "http://www.onvif.org/ver10/tptz/ZoomSpaces/ZoomGenericSpeedSpace"


def float_range(tag: str, lo: float, hi: float) -> Xml:
    return el(tag, el("tt:Min", lo), el("tt:Max", hi))


def int_range(tag: str, lo: int, hi: int) -> Xml:
    return el(tag, el("tt:Min", int(lo)), el("tt:Max", int(hi)))


def resolution(tag: str, w: int, h: int) -> Xml:
    return el(tag, el("tt:Width", w), el("tt:Height", h))


def vsc_xml(tag: str, st: CameraState, c: VideoSourceConfig) -> Xml:
    return el(
        tag,
        el("tt:Name", c.name),
        el("tt:UseCount", st.use_count("vsc", c.token)),
        el("tt:SourceToken", c.source_token),
        el("tt:Bounds", x=c.x, y=c.y, width=c.width, height=c.height),
        token=c.token,
    )


def _multicast(e: VideoEncoderConfig) -> Xml:
    return el(
        "tt:Multicast",
        el("tt:Address", el("tt:Type", "IPv4"), el("tt:IPv4Address", e.multicast_address)),
        el("tt:Port", e.multicast_port),
        el("tt:TTL", e.multicast_ttl),
        el("tt:AutoStart", False),
    )


def vec1_xml(tag: str, st: CameraState, e: VideoEncoderConfig) -> Xml:
    """Media1 tt:VideoEncoderConfiguration. Media1 has no H265: report H264 (what real cameras do)."""
    enc = "JPEG" if e.encoding == "JPEG" else "H264"
    return el(
        tag,
        el("tt:Name", e.name),
        el("tt:UseCount", st.use_count("vec", e.token)),
        el("tt:Encoding", enc),
        resolution("tt:Resolution", e.width, e.height),
        el("tt:Quality", e.quality),
        el(
            "tt:RateControl",
            el("tt:FrameRateLimit", e.fps),
            el("tt:EncodingInterval", 1),
            el("tt:BitrateLimit", e.bitrate_kbps),
        ),
        el("tt:H264", el("tt:GovLength", e.gov_length), el("tt:H264Profile", e.h264_profile)) if enc == "H264" else None,
        _multicast(e),
        el("tt:SessionTimeout", f"PT{e.session_timeout_s}S"),
        token=e.token,
    )


def vec2_xml(tag: str, st: CameraState, e: VideoEncoderConfig) -> Xml:
    """Media2 tt:VideoEncoder2Configuration."""
    attrs = {"token": e.token, "GovLength": e.gov_length}
    if e.encoding in ("H264", "H265"):
        attrs["Profile"] = e.h264_profile if e.encoding == "H264" else "Main"
    return el(
        tag,
        el("tt:Name", e.name),
        el("tt:UseCount", st.use_count("vec", e.token)),
        el("tt:Encoding", e.encoding),
        resolution("tt:Resolution", e.width, e.height),
        el(
            "tt:RateControl",
            el("tt:FrameRateLimit", e.fps),
            el("tt:BitrateLimit", e.bitrate_kbps),
            ConstantBitRate=e.rc_mode == "CBR",
        ),
        _multicast(e),
        el("tt:Quality", e.quality),
        **attrs,
    )


def ptz_spaces_xml(tag: str) -> Xml:
    return el(
        tag,
        el("tt:AbsolutePanTiltPositionSpace", el("tt:URI", PT_POS), float_range("tt:XRange", -1, 1), float_range("tt:YRange", -1, 1)),
        el("tt:AbsoluteZoomPositionSpace", el("tt:URI", Z_POS), float_range("tt:XRange", 0, 1)),
        el("tt:RelativePanTiltTranslationSpace", el("tt:URI", PT_TRANS), float_range("tt:XRange", -1, 1), float_range("tt:YRange", -1, 1)),
        el("tt:RelativeZoomTranslationSpace", el("tt:URI", Z_TRANS), float_range("tt:XRange", -1, 1)),
        el("tt:ContinuousPanTiltVelocitySpace", el("tt:URI", PT_VEL), float_range("tt:XRange", -1, 1), float_range("tt:YRange", -1, 1)),
        el("tt:ContinuousZoomVelocitySpace", el("tt:URI", Z_VEL), float_range("tt:XRange", -1, 1)),
        el("tt:PanTiltSpeedSpace", el("tt:URI", PT_SPEED), float_range("tt:XRange", 0, 1)),
        el("tt:ZoomSpeedSpace", el("tt:URI", Z_SPEED), float_range("tt:XRange", 0, 1)),
    )


def ptz_config_xml(tag: str, st: CameraState, c: PtzConfigModel) -> Xml:
    return el(
        tag,
        el("tt:Name", c.name),
        el("tt:UseCount", st.use_count("ptz", c.token)),
        el("tt:NodeToken", c.node_token),
        el("tt:DefaultAbsolutePantTiltPositionSpace", PT_POS),
        el("tt:DefaultAbsoluteZoomPositionSpace", Z_POS),
        el("tt:DefaultRelativePanTiltTranslationSpace", PT_TRANS),
        el("tt:DefaultRelativeZoomTranslationSpace", Z_TRANS),
        el("tt:DefaultContinuousPanTiltVelocitySpace", PT_VEL),
        el("tt:DefaultContinuousZoomVelocitySpace", Z_VEL),
        el(
            "tt:DefaultPTZSpeed",
            el("tt:PanTilt", x=c.default_pan_tilt_speed, y=c.default_pan_tilt_speed, space=PT_SPEED),
            el("tt:Zoom", x=c.default_zoom_speed, space=Z_SPEED),
        ),
        el("tt:DefaultPTZTimeout", f"PT{c.default_timeout_s}S"),
        el("tt:PanTiltLimits", el("tt:Range", el("tt:URI", PT_POS), float_range("tt:XRange", -1, 1), float_range("tt:YRange", -1, 1))),
        el("tt:ZoomLimits", el("tt:Range", el("tt:URI", Z_POS), float_range("tt:XRange", 0, 1))),
        token=c.token,
    )


def profile1_xml(tag: str, st: CameraState, p: MediaProfile) -> Xml:
    vsc = st.vsc(p.vsc_token) if p.vsc_token else None
    vec = st.encoder(p.vec_token) if p.vec_token else None
    ptz = st.ptz_config(p.ptz_token) if p.ptz_token else None
    return el(
        tag,
        el("tt:Name", p.name),
        vsc_xml("tt:VideoSourceConfiguration", st, vsc) if vsc else None,
        vec1_xml("tt:VideoEncoderConfiguration", st, vec) if vec else None,
        ptz_config_xml("tt:PTZConfiguration", st, ptz) if ptz else None,
        token=p.token,
        fixed=p.fixed,
    )


def osd_xml(tag: str, st: CameraState, o: OsdItem) -> Xml:
    vsc = st.video_source_configs[0].token if st.video_source_configs else "VideoSourceConfig_1"
    pos = el("tt:Position", el("tt:Type", o.position), el("tt:Pos", x=o.x, y=o.y) if o.position == "Custom" else None)
    text_type = o.kind
    ts = el(
        "tt:TextString",
        el("tt:Type", text_type),
        el("tt:DateFormat", o.date_format) if text_type in ("Date", "DateAndTime") else None,
        el("tt:TimeFormat", o.time_format) if text_type in ("Time", "DateAndTime") else None,
        el("tt:FontSize", o.font_size),
        el("tt:PlainText", o.plain_text) if text_type == "Plain" else None,
    )
    return el(tag, el("tt:VideoSourceConfigurationToken", vsc), el("tt:Type", "Text"), pos, ts, token=o.token)
