"""ONVIF Imaging service (ver20/imaging/wsdl). In Encode mode settings really change the video."""
from app.cameras import operations as ops
from app.onvif import namespaces as NS
from app.onvif.dispatcher import Access, OnvifContext, onvif_operation
from app.onvif.faults import invalid_arg
from app.onvif.handlers import service_caps
from app.onvif.handlers.common import float_range
from app.onvif.xml import child, el, num, text

IM = NS.IMAGING


def _resp(op: str, *content):
    return el(f"timg:{op}Response", *content)


def _check_source(ctx: OnvifContext) -> None:
    token = text(ctx.body, "VideoSourceToken")
    if token and token != ctx.state.video_source.token:
        raise invalid_arg("NoSource", f"Video source {token} does not exist")


@onvif_operation(IM, "GetServiceCapabilities", Access.PRE_AUTH)
async def get_service_capabilities(ctx: OnvifContext):
    return _resp("GetServiceCapabilities", service_caps.imaging_caps(ctx))


@onvif_operation(IM, "GetImagingSettings", Access.READ_MEDIA)
async def get_imaging_settings(ctx: OnvifContext):
    _check_source(ctx)
    i = ctx.state.imaging
    return _resp(
        "GetImagingSettings",
        el(
            "timg:ImagingSettings",
            el("tt:BacklightCompensation", el("tt:Mode", i.backlight)),
            el("tt:Brightness", i.brightness),
            el("tt:ColorSaturation", i.color_saturation),
            el("tt:Contrast", i.contrast),
            el("tt:Exposure", el("tt:Mode", i.exposure_mode)),
            el("tt:Focus", el("tt:AutoFocusMode", i.focus_mode)),
            el("tt:IrCutFilter", i.ir_cut),
            el("tt:Sharpness", i.sharpness),
            el("tt:WideDynamicRange", el("tt:Mode", i.wdr_mode), el("tt:Level", i.wdr_level)),
            el("tt:WhiteBalance", el("tt:Mode", i.white_balance)),
        ),
    )


@onvif_operation(IM, "SetImagingSettings", Access.ACTUATE)
async def set_imaging_settings(ctx: OnvifContext):
    _check_source(ctx)
    s = child(ctx.body, "ImagingSettings")
    if s is None:
        raise invalid_arg("SettingsInvalid", "ImagingSettings missing")

    def enum(v, allowed):
        if v is None:
            return None
        if v not in allowed:
            raise invalid_arg("SettingsInvalid", f"Value {v} not supported")
        return v

    changes = {
        "brightness": num(s, "Brightness"),
        "color_saturation": num(s, "ColorSaturation"),
        "contrast": num(s, "Contrast"),
        "sharpness": num(s, "Sharpness"),
        "ir_cut": enum(text(s, "IrCutFilter"), ("ON", "OFF", "AUTO")),
        "backlight": enum(text(s, "BacklightCompensation", "Mode"), ("ON", "OFF")),
        "exposure_mode": enum(text(s, "Exposure", "Mode"), ("AUTO", "MANUAL")),
        "focus_mode": enum(text(s, "Focus", "AutoFocusMode"), ("AUTO", "MANUAL")),
        "wdr_mode": enum(text(s, "WideDynamicRange", "Mode"), ("ON", "OFF")),
        "wdr_level": num(s, "WideDynamicRange", "Level"),
        "white_balance": enum(text(s, "WhiteBalance", "Mode"), ("AUTO", "MANUAL")),
    }
    for k in ("brightness", "color_saturation", "contrast", "sharpness", "wdr_level"):
        if changes[k] is not None and not 0 <= changes[k] <= 100:
            raise invalid_arg("SettingsInvalid", f"{k} must be 0..100")
    await ops.set_imaging(ctx.runtime, changes)
    return _resp("SetImagingSettings")


@onvif_operation(IM, "GetOptions", Access.READ_MEDIA)
async def get_options(ctx: OnvifContext):
    _check_source(ctx)
    return _resp(
        "GetOptions",
        el(
            "timg:ImagingOptions",
            el("tt:BacklightCompensation", el("tt:Mode", "OFF"), el("tt:Mode", "ON")),
            float_range("tt:Brightness", 0, 100),
            float_range("tt:ColorSaturation", 0, 100),
            float_range("tt:Contrast", 0, 100),
            el("tt:Exposure", el("tt:Mode", "AUTO"), el("tt:Mode", "MANUAL")),
            el("tt:Focus", el("tt:AutoFocusModes", "AUTO"), el("tt:AutoFocusModes", "MANUAL")),
            [el("tt:IrCutFilterModes", m) for m in ("ON", "OFF", "AUTO")],
            float_range("tt:Sharpness", 0, 100),
            el("tt:WideDynamicRange", el("tt:Mode", "OFF"), el("tt:Mode", "ON"), float_range("tt:Level", 0, 100)),
            el("tt:WhiteBalance", el("tt:Mode", "AUTO"), el("tt:Mode", "MANUAL")),
        ),
    )


@onvif_operation(IM, "GetMoveOptions", Access.READ_MEDIA)
async def get_move_options(ctx: OnvifContext):
    return _resp("GetMoveOptions", el("timg:MoveOptions", el("tt:Continuous", float_range("tt:Speed", 0, 1))))


@onvif_operation(IM, "Move", Access.ACTUATE)
async def move(ctx: OnvifContext):
    ctx.runtime.log("imaging focus move (simulated)")
    return _resp("Move")


@onvif_operation(IM, "Stop", Access.ACTUATE)
async def stop(ctx: OnvifContext):
    return _resp("Stop")


@onvif_operation(IM, "GetStatus", Access.READ_MEDIA)
async def get_status(ctx: OnvifContext):
    return _resp("GetStatus", el("timg:Status", el("tt:FocusStatus20", el("tt:Position", 0), el("tt:MoveStatus", "IDLE"))))
