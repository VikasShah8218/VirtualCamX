"""Built-in camera templates ("models").

A template = identity defaults + stream slots + capabilities. `build_state()` turns a
template into a fresh CameraState for a new camera.
"""
from app.cameras.state import (
    CameraState,
    Capabilities,
    DigitalInput,
    Identity,
    IoState,
    MediaProfile,
    OsdItem,
    PtzConfigModel,
    RelayOutput,
    StreamOptions,
    VideoEncoderConfig,
    VideoSource,
    VideoSourceConfig,
)

SUB_RES = [(704, 576), (640, 480), (640, 360), (352, 288)]
THIRD_RES = [(640, 360), (352, 288), (320, 240)]

BUILTIN_TEMPLATES: dict[str, dict] = {
    "bullet_2mp": {
        "name": "Bullet 2MP",
        "model": "VCX-B2MP",
        "native": (1920, 1080),
        "main_res": [(1920, 1080), (1280, 960), (1280, 720)],
        "main": ("H264", 1920, 1080, 25, 4096),
        "sub": ("H264", 704, 576, 15, 512),
        "third": None,
        "ptz": False,
        "inputs": 1,
        "relays": 1,
    },
    "bullet_4mp": {
        "name": "Bullet 4MP",
        "model": "VCX-B4MP",
        "native": (2560, 1440),
        "main_res": [(2560, 1440), (2304, 1296), (1920, 1080), (1280, 720)],
        "main": ("H265", 2560, 1440, 25, 6144),
        "sub": ("H264", 640, 360, 15, 512),
        "third": ("H264", 640, 360, 10, 384),
        "ptz": False,
        "inputs": 1,
        "relays": 1,
    },
    "dome_5mp": {
        "name": "Dome 5MP",
        "model": "VCX-D5MP",
        "native": (2592, 1944),
        "main_res": [(2592, 1944), (2560, 1440), (1920, 1080), (1280, 720)],
        "main": ("H265", 2592, 1944, 20, 8192),
        "sub": ("H264", 704, 576, 15, 768),
        "third": ("JPEG", 640, 360, 5, 1024),
        "ptz": False,
        "inputs": 1,
        "relays": 1,
    },
    "ptz_2mp": {
        "name": "PTZ 2MP",
        "model": "VCX-PTZ2MP",
        "native": (1920, 1080),
        "main_res": [(1920, 1080), (1280, 720)],
        "main": ("H264", 1920, 1080, 25, 4096),
        "sub": ("H264", 704, 576, 15, 512),
        "third": None,
        "ptz": True,
        "inputs": 2,
        "relays": 1,
    },
    "lowend_720p": {
        "name": "Low-end 720p",
        "model": "VCX-L720",
        "native": (1280, 720),
        "main_res": [(1280, 720), (640, 480)],
        "main": ("H264", 1280, 720, 15, 1536),
        "sub": ("H264", 352, 288, 10, 256),
        "third": None,
        "ptz": False,
        "inputs": 0,
        "relays": 0,
    },
}


def build_state(template: dict, *, name: str, serial: str, mac: str, endpoint_uuid: str) -> CameraState:
    native_w, native_h = template["native"]
    encoders: list[VideoEncoderConfig] = []
    profiles: list[MediaProfile] = []
    stream_options: dict[str, StreamOptions] = {}

    slots = [("main", template["main"], template["main_res"]), ("sub", template["sub"], SUB_RES), ("third", template.get("third"), THIRD_RES)]
    for idx, (key, spec, resolutions) in enumerate(slots, start=1):
        if not spec:
            continue
        enc, w, h, fps, kbps = spec
        token = f"VideoEncoder_{idx}"
        encoders.append(
            VideoEncoderConfig(
                token=token,
                name=f"{key.capitalize()}Stream",
                stream_key=key,  # type: ignore[arg-type]
                encoding=enc,
                width=w,
                height=h,
                fps=fps,
                bitrate_kbps=kbps,
                gov_length=fps * 2,
                h264_profile="Main" if key == "main" else "Baseline",
            )
        )
        stream_options[key] = StreamOptions(resolutions=list(resolutions))
        profiles.append(
            MediaProfile(
                token=f"Profile_{idx}",
                name=f"{key}Stream",
                vec_token=token,
                ptz_token="PTZConfig_1" if template["ptz"] else None,
            )
        )

    model = template["model"]
    scopes = [
        "onvif://www.onvif.org/type/video_encoder",
        "onvif://www.onvif.org/Profile/Streaming",
        "onvif://www.onvif.org/Profile/T",
        f"onvif://www.onvif.org/hardware/{model}",
        f"onvif://www.onvif.org/name/{name.replace(' ', '_')}",
        "onvif://www.onvif.org/location/country/virtual",
    ]
    if template["ptz"]:
        scopes.insert(1, "onvif://www.onvif.org/type/ptz")

    return CameraState(
        identity=Identity(model=model, serial_number=serial, mac=mac, endpoint_uuid=endpoint_uuid),
        scopes=scopes,
        video_source=VideoSource(width=native_w, height=native_h, framerate=float(max(s[1][3] for s in slots if s[1]))),
        video_source_configs=[VideoSourceConfig(width=native_w, height=native_h)],
        video_encoders=encoders,
        ptz_configs=[PtzConfigModel()] if template["ptz"] else [],
        profiles=profiles,
        osd=[
            OsdItem(token="OSD_1", kind="DateAndTime", position="UpperLeft"),
            OsdItem(token="OSD_2", kind="Plain", plain_text=name, position="LowerRight"),
        ],
        io=IoState(
            inputs=[DigitalInput(token=f"DigitalInput_{i + 1}") for i in range(template["inputs"])],
            relays=[RelayOutput(token=f"RelayOutput_{i + 1}") for i in range(template["relays"])],
        ),
        capabilities=Capabilities(has_ptz=template["ptz"], stream_options=stream_options),
    )
