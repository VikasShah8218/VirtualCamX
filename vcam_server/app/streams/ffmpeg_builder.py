"""StreamSpec -> FFmpeg argv. Pure functions, no I/O (easy to unit test).

One FFmpeg process per camera: decode the source once, apply ePTZ / imaging / OSD, then
`split` into main / sub / third / snapshot outputs that are published to MediaMTX.
Paths inside the filtergraph (fonts, OSD text files) are relative to the data dir, which is
FFmpeg's working directory, so Windows drive colons never need filtergraph escaping.
"""
from dataclasses import dataclass, field

BS = "\\"


@dataclass(frozen=True)
class OutputSpec:
    key: str  # main | sub | third
    encoding: str  # H264 | H265 | JPEG
    width: int
    height: int
    fps: int
    bitrate_kbps: int
    rc_mode: str  # CBR | VBR
    quality: float  # 1..10
    gov: int
    profile: str  # Baseline | Main | High
    copy_from: str | None = None  # passthrough: pre-encoded file to stream as-is


@dataclass(frozen=True)
class OsdSpec:
    token: str
    textfile: str  # relative to data dir
    position: str
    x: float
    y: float
    font_size: int
    style: str = "box"  # box (white on translucent box) | alert (red outlined text, nothing drawn when empty)


@dataclass(frozen=True)
class InputSpec:
    kind: str  # file | image | rtsp | test | black | nosource | freeze
    path: str | None = None
    url: str | None = None
    pattern: str = "testsrc2"
    start_offset: float = 0.0
    loop: bool = True


@dataclass
class LiveParams:
    """Values that can change without restarting FFmpeg (sent over ZMQ)."""

    brightness: float = 0.0  # eq -1..1
    contrast: float = 1.0  # eq 0..2
    saturation: float = 1.0  # eq 0..3
    gray: bool = False  # IR-cut OFF => night mode
    crop: tuple[int, int, int, int] = (0, 0, 0, 0)  # w, h, x, y


@dataclass
class StreamSpec:
    path_prefix: str  # cam001
    mode: str  # encode | passthrough
    input: InputSpec
    native_w: int
    native_h: int
    native_fps: float
    outputs: tuple[OutputSpec, ...]
    osd: tuple[OsdSpec, ...] = ()
    mirror: bool = False
    flip: bool = False
    banner: str | None = None  # big centered text (NO SOURCE / VIDEO LOSS)
    font: str | None = "fonts/osd.ttf"
    snapshot_file: str | None = None  # relative to data dir
    zmq_port: int = 0
    live: LiveParams = field(default_factory=LiveParams)

    def restart_key(self) -> tuple:
        """Everything that needs an FFmpeg restart when it changes (live params excluded)."""
        return (
            self.mode, self.input, self.native_w, self.native_h, self.native_fps, self.outputs,
            self.osd, self.mirror, self.flip, self.banner, self.font, self.snapshot_file, self.zmq_port,
        )


def quality_to_crf(quality: float, encoding: str) -> int:
    q = max(1.0, min(10.0, quality))
    base = 40 if encoding == "H264" else 42
    return int(round(base - q * 2.0))  # q10 -> 20/22, q1 -> 38/40


def quality_to_mjpeg_q(quality: float) -> int:
    q = max(1.0, min(10.0, quality))
    return int(round(31 - (q - 1) * (29 / 9)))  # q1 -> 31 (worst), q10 -> 2 (best)


def _input_args(inp: InputSpec, w: int, h: int, fps: float, freeze_file: str | None) -> list[str]:
    rate = f"{fps:g}"
    if inp.kind == "file":
        args = ["-re"]
        if inp.loop:
            args += ["-stream_loop", "-1"]
        if inp.start_offset > 0:
            args += ["-ss", f"{inp.start_offset:.3f}"]
        return args + ["-fflags", "+genpts", "-i", inp.path or ""]
    if inp.kind == "image":
        return ["-re", "-loop", "1", "-framerate", rate, "-i", inp.path or ""]
    if inp.kind == "rtsp":
        return ["-rtsp_transport", "tcp", "-i", inp.url or ""]
    if inp.kind == "freeze" and freeze_file:
        return ["-re", "-loop", "1", "-framerate", rate, "-i", freeze_file]
    if inp.kind in ("black", "nosource", "freeze"):
        color = "black" if inp.kind == "black" else "0x202830"
        return ["-re", "-f", "lavfi", "-i", f"color=c={color}:size={w}x{h}:rate={rate}"]
    return ["-re", "-f", "lavfi", "-i", f"{inp.pattern}=size={w}x{h}:rate={rate}"]


def _osd_xy(o: OsdSpec, margin: int) -> tuple[str, str]:
    m = margin
    if o.position == "UpperLeft":
        return str(m), str(m)
    if o.position == "UpperRight":
        return f"w-tw-{m}", str(m)
    if o.position == "LowerLeft":
        return str(m), f"h-th-{m}"
    if o.position == "LowerRight":
        return f"w-tw-{m}", f"h-th-{m}"
    # Custom: ONVIF normalized coordinates, -1..1 with +y up
    x = int((o.x + 1) / 2 * 10000)
    y = int((1 - o.y) / 2 * 10000)
    return f"w*{x}/10000", f"h*{y}/10000"


def _font_opt(font: str | None) -> str:
    return f"fontfile={font}:" if font else ""


def build_filtergraph(spec: StreamSpec) -> tuple[str, list[str]]:
    """Returns (filter_complex, output labels in order: outputs..., [snap])."""
    W, H = spec.native_w, spec.native_h
    lv = spec.live
    cw, ch, cx, cy = lv.crop if lv.crop[0] else (W, H, 0, 0)
    chain = [
        f"scale={W}:{H}:force_original_aspect_ratio=decrease",
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2",
        "setsar=1",
    ]
    if spec.zmq_port:
        chain.append(f"zmq=bind_address=tcp{BS}{BS}://127.0.0.1{BS}{BS}:{spec.zmq_port}")
    chain.append(f"crop@ptz=w={cw}:h={ch}:x={cx}:y={cy}")
    chain.append(f"scale={W}:{H}")
    if spec.mirror:
        chain.append("hflip")
    if spec.flip:
        chain.append("vflip")
    chain.append(f"eq@img=brightness={lv.brightness:.3f}:contrast={lv.contrast:.3f}:saturation={lv.saturation:.3f}")
    chain.append(f"hue@ir=s={0 if lv.gray else 1}")

    scale_ref = H / 1080.0
    margin = max(8, int(20 * scale_ref))
    font = _font_opt(spec.font)
    reload_every = max(1, int(spec.native_fps // 5))
    for o in spec.osd:
        x, y = _osd_xy(o, margin)
        size = max(10, int(o.font_size * scale_ref))
        look = (":fontcolor=red:borderw=3:bordercolor=black" if o.style == "alert"
                else ":fontcolor=white:box=1:boxcolor=black@0.35:boxborderw=6")
        # reload every ~1/5 s (not every frame): fewer file reads, same visible 1 s clock
        chain.append(f"drawtext@{o.token}={font}textfile={o.textfile}:reload={reload_every}:x={x}:y={y}:fontsize={size}{look}")
    if spec.banner:
        size = max(16, int(96 * scale_ref))
        chain.append(
            f"drawtext@banner={font}text='{spec.banner}':x=(w-tw)/2:y=(h-th)/2:fontsize={size}"
            ":fontcolor=white:box=1:boxcolor=red@0.6:boxborderw=20"
        )

    n = len(spec.outputs) + (1 if spec.snapshot_file else 0)
    labels_in = [f"[s{i}]" for i in range(n)]
    graph = "[0:v]" + ",".join(chain) + f",split={n}" + "".join(labels_in) if n > 1 else "[0:v]" + ",".join(chain) + "[s0]"
    parts = [graph]
    out_labels = []
    for i, o in enumerate(spec.outputs):
        fmt = ",format=yuvj420p" if o.encoding == "JPEG" else ",format=yuv420p"
        parts.append(f"[s{i}]scale={o.width}:{o.height},fps={o.fps}{fmt}[o{i}]")
        out_labels.append(f"[o{i}]")
    if spec.snapshot_file:
        i = len(spec.outputs)
        snap_w = min(W, 1920)
        parts.append(f"[s{i}]fps=1,scale={snap_w}:-2,format=yuvj420p[snap]")
        out_labels.append("[snap]")
    return ";".join(parts), out_labels


def _encoder_args(o: OutputSpec, x264_preset: str) -> list[str]:
    kb = max(32, o.bitrate_kbps)
    if o.encoding == "JPEG":
        return ["-c:v", "mjpeg", "-q:v", str(quality_to_mjpeg_q(o.quality))]
    rate = (
        ["-b:v", f"{kb}k", "-maxrate", f"{kb}k", "-bufsize", f"{kb * 2}k"]
        if o.rc_mode == "CBR"
        else ["-crf", str(quality_to_crf(o.quality, o.encoding)), "-maxrate", f"{kb}k", "-bufsize", f"{kb * 2}k"]
    )
    gov = max(1, o.gov)
    if o.encoding == "H265":
        preset = "ultrafast" if x264_preset in ("ultrafast", "superfast", "veryfast") else x264_preset
        return [
            "-c:v", "libx265", "-preset", preset, "-tune", "zerolatency",
            "-x265-params", f"keyint={gov}:min-keyint={gov}:scenecut=0:bframes=0:repeat-headers=1:log-level=error",
            *rate,
        ]
    return [
        "-c:v", "libx264", "-preset", x264_preset, "-tune", "zerolatency",
        "-profile:v", o.profile.lower(), "-g", str(gov), "-keyint_min", str(gov), "-sc_threshold", "0", "-bf", "0",
        *rate,
    ]


def build_argv(spec: StreamSpec, ffmpeg: str, publish_base: str, x264_preset: str = "veryfast",
               freeze_file: str | None = None) -> list[str]:
    """publish_base = rtsp://user:pass@127.0.0.1:8554 ; each output goes to {base}/{prefix}/{key}."""
    argv = [ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostats", "-y"]
    if spec.mode == "passthrough" and all(o.copy_from for o in spec.outputs):
        for o in spec.outputs:
            argv += ["-re", "-stream_loop", "-1"]
            if spec.input.start_offset > 0:
                argv += ["-ss", f"{spec.input.start_offset:.3f}"]
            argv += ["-fflags", "+genpts", "-i", o.copy_from or ""]
        for i, o in enumerate(spec.outputs):
            argv += ["-map", f"{i}:v:0", "-c:v", "copy", "-an",
                     "-f", "rtsp", "-rtsp_transport", "tcp", f"{publish_base}/{spec.path_prefix}/{o.key}"]
        return argv

    argv += _input_args(spec.input, spec.native_w, spec.native_h, spec.native_fps, freeze_file)
    graph, labels = build_filtergraph(spec)
    argv += ["-filter_complex", graph]
    for o, label in zip(spec.outputs, labels):
        argv += ["-map", label, *_encoder_args(o, x264_preset), "-an",
                 "-f", "rtsp", "-rtsp_transport", "tcp", f"{publish_base}/{spec.path_prefix}/{o.key}"]
    if spec.snapshot_file:
        argv += ["-map", "[snap]", "-c:v", "mjpeg", "-q:v", "5", "-f", "image2", "-update", "1",
                 "-atomic_writing", "1", spec.snapshot_file]
    return argv
