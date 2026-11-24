from app.streams.ffmpeg_builder import (InputSpec, LiveParams, OsdSpec, OutputSpec, StreamSpec, build_argv,
                                        quality_to_crf, quality_to_mjpeg_q)


def spec(**kw):
    base = dict(
        path_prefix="cam007", mode="encode", input=InputSpec(kind="test"), native_w=1920, native_h=1080, native_fps=25,
        outputs=(
            OutputSpec("main", "H264", 1920, 1080, 25, 4096, "CBR", 6, 50, "Main"),
            OutputSpec("sub", "H265", 704, 576, 15, 512, "VBR", 6, 30, "Main"),
        ),
        osd=(OsdSpec("OSD_1", "osd/cam007_OSD_1.txt", "UpperLeft", -1, 1, 32),),
        snapshot_file="snapshots/cam007.jpg", zmq_port=21007,
    )
    base.update(kw)
    return StreamSpec(**base)


def test_encode_argv_has_all_outputs():
    argv = build_argv(spec(), "ffmpeg", "rtsp://u:p@127.0.0.1:8554")
    assert "rtsp://u:p@127.0.0.1:8554/cam007/main" in argv
    assert "rtsp://u:p@127.0.0.1:8554/cam007/sub" in argv
    assert "snapshots/cam007.jpg" in argv
    assert "libx264" in argv and "libx265" in argv
    graph = argv[argv.index("-filter_complex") + 1]
    assert "split=3" in graph
    assert "zmq=bind_address=tcp\\\\://127.0.0.1\\\\:21007" in graph  # double-escaped, verified against ffmpeg
    assert "crop@ptz" in graph and "eq@img" in graph and "hue@ir" in graph
    assert "drawtext@OSD_1" in graph and "reload=5" in graph


def test_cbr_vs_vbr():
    argv = build_argv(spec(), "ffmpeg", "rtsp://x")
    main_part = argv[argv.index("[o0]"): argv.index("[o1]")]
    assert "-b:v" in main_part and "4096k" in main_part
    sub_part = argv[argv.index("[o1]"):]
    assert "-crf" in sub_part


def test_live_params_do_not_change_restart_key():
    a, b = spec(), spec(live=LiveParams(brightness=0.3, gray=True, crop=(960, 540, 10, 10)))
    assert a.restart_key() == b.restart_key()


def test_encoder_change_changes_restart_key():
    other = spec(outputs=(OutputSpec("main", "H264", 1280, 720, 25, 2048, "CBR", 6, 50, "Main"),))
    assert spec().restart_key() != other.restart_key()


def test_passthrough_uses_copy():
    outs = (OutputSpec("main", "H264", 1920, 1080, 25, 4096, "CBR", 6, 50, "Main", copy_from="D:/a b/main.mp4"),)
    argv = build_argv(spec(mode="passthrough", outputs=outs, snapshot_file=None, zmq_port=0), "ffmpeg", "rtsp://x")
    assert "copy" in argv and "-filter_complex" not in argv and "D:/a b/main.mp4" in argv


def test_file_input_loop_and_offset():
    argv = build_argv(spec(input=InputSpec(kind="file", path=r"C:\v\x.mp4", start_offset=12.5)), "ffmpeg", "rtsp://x")
    i = argv.index("-i")
    assert argv[i + 1] == r"C:\v\x.mp4"
    assert "-stream_loop" in argv[:i] and "12.500" in argv[:i]


def test_banner_is_quoted():
    argv = build_argv(spec(input=InputSpec(kind="nosource"), banner="NO SOURCE"), "ffmpeg", "rtsp://x")
    assert "text='NO SOURCE'" in argv[argv.index("-filter_complex") + 1]


def test_quality_mapping_monotonic():
    assert quality_to_crf(10, "H264") < quality_to_crf(1, "H264")
    assert quality_to_mjpeg_q(10) < quality_to_mjpeg_q(1)
