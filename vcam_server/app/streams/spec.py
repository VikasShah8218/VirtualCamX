"""CameraState (+ faults, PTZ, passthrough cache) -> StreamSpec."""
import os
from typing import TYPE_CHECKING

from app.ptz.controller import crop_rect
from app.streams.ffmpeg_builder import InputSpec, LiveParams, OsdSpec, OutputSpec, StreamSpec
from settings.settings import settings

if TYPE_CHECKING:
    from app.runtime.camera_runtime import CameraRuntime


def live_params(rt: "CameraRuntime") -> LiveParams:
    img = rt.state.imaging
    vs = rt.state.video_source
    return LiveParams(
        brightness=round((img.brightness - 50) / 100.0, 3),  # 0..100 -> -0.5..0.5
        contrast=round(max(0.0, img.contrast / 50.0), 3),  # 50 -> 1.0
        saturation=round(max(0.0, img.color_saturation / 50.0), 3),
        gray=img.ir_cut == "OFF",
        crop=crop_rect(rt.ptz.pan, rt.ptz.tilt, rt.ptz.zoom, vs.width, vs.height) if rt.state.capabilities.has_ptz else (0, 0, 0, 0),
    )


def _input(rt: "CameraRuntime") -> tuple[InputSpec, str | None]:
    """Returns (input, banner)."""
    fault_override = rt.faults.video_override()  # None | "black" | "freeze"
    if fault_override == "black":
        return InputSpec(kind="black"), "VIDEO LOSS"
    if fault_override == "freeze":
        return InputSpec(kind="freeze"), None
    src = rt.state.source
    if src.type == "file":
        if src.path and os.path.isfile(src.path):
            return InputSpec(kind="file", path=src.path, start_offset=src.start_offset, loop=src.loop), None
        return InputSpec(kind="nosource"), "NO SOURCE"
    if src.type == "image":
        if src.path and os.path.isfile(src.path):
            return InputSpec(kind="image", path=src.path), None
        return InputSpec(kind="nosource"), "NO SOURCE"
    if src.type == "rtsp" and src.url:
        return InputSpec(kind="rtsp", url=src.url), None
    return InputSpec(kind="test", pattern=src.pattern), None


def build_spec(rt: "CameraRuntime") -> StreamSpec:
    st = rt.state
    vs = st.video_source
    inp, banner = _input(rt)
    outputs = []
    for e in st.video_encoders:
        outputs.append(
            OutputSpec(
                key=e.stream_key, encoding=e.encoding, width=e.width, height=e.height, fps=e.fps,
                bitrate_kbps=e.bitrate_kbps, rc_mode=e.rc_mode, quality=e.quality, gov=e.gov_length,
                profile=e.h264_profile,
            )
        )

    mode = "encode"
    if st.stream_mode == "passthrough" and inp.kind == "file" and inp.path:
        from app.media_library import cache

        copies = [cache.ready_variant(inp.path, o) for o in outputs]
        if all(copies):
            mode = "passthrough"
            outputs = [OutputSpec(**{**o.__dict__, "copy_from": c}) for o, c in zip(outputs, copies)]
        else:
            cache.request_variants(inp.path, [o for o, c in zip(outputs, copies) if not c])

    osd = []
    for item in st.osd:
        if item.enabled:
            osd.append(OsdSpec(item.token, rt.osd_file_rel(item.token), item.position, item.x, item.y, item.font_size))
    if st.osd_show_events:
        osd.append(OsdSpec("OSD_EVENT", rt.osd_file_rel("OSD_EVENT"), "UpperRight", 0, 0, 40, style="alert"))

    return StreamSpec(
        path_prefix=rt.path_prefix,
        mode=mode,
        input=inp,
        native_w=vs.width,
        native_h=vs.height,
        native_fps=vs.framerate,
        outputs=tuple(outputs),
        osd=tuple(osd),
        mirror=st.imaging.mirror,
        flip=st.imaging.flip,
        banner=banner,
        font=rt.manager.font_rel,
        snapshot_file=f"snapshots/{rt.path_prefix}.jpg" if mode == "encode" else None,
        zmq_port=settings.zmq_base_port + rt.number if mode == "encode" else 0,
        live=live_params(rt),
    )
