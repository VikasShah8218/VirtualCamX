"""Camera config operations shared by ONVIF handlers, the camera web API and the Manager API.

They validate against the camera's capabilities and go through CameraRuntime.update().
Errors are raised as OnvifFault; REST routers turn them into HTTP 422.
"""
from app.cameras.state import CameraState, MediaProfile, OsdItem, PtzPreset
from app.onvif.faults import OnvifFault, config_modify, invalid_arg, no_config, no_profile


def validate_encoder(st: CameraState, token: str, changes: dict) -> None:
    enc = st.encoder(token)
    if enc is None:
        raise no_config(token)
    opts = st.capabilities.stream_options.get(enc.stream_key)
    if opts is None:
        return
    encoding = changes.get("encoding", enc.encoding)
    if encoding not in opts.encodings:
        raise config_modify(f"Encoding {encoding} not supported on {enc.stream_key} stream")
    w, h = changes.get("width", enc.width), changes.get("height", enc.height)
    if (w, h) not in [tuple(r) for r in opts.resolutions]:
        raise config_modify(f"Resolution {w}x{h} not supported on {enc.stream_key} stream")
    if encoding == "JPEG" and (w % 8 or h % 8 or w > 2040 or h > 2040):
        raise config_modify("JPEG resolution must be a multiple of 8 and at most 2040 pixels")
    fps = changes.get("fps", enc.fps)
    if not 1 <= fps <= opts.max_fps:
        raise config_modify(f"FrameRateLimit {fps} out of range 1..{opts.max_fps}")
    br = changes.get("bitrate_kbps", enc.bitrate_kbps)
    if not opts.bitrate_min_kbps <= br <= opts.bitrate_max_kbps:
        raise config_modify(f"BitrateLimit {br} out of range {opts.bitrate_min_kbps}..{opts.bitrate_max_kbps}")
    gov = changes.get("gov_length", enc.gov_length)
    if not 1 <= gov <= 400:
        raise config_modify(f"GovLength {gov} out of range 1..400")
    q = changes.get("quality", enc.quality)
    if not 0 <= q <= 10:
        raise config_modify(f"Quality {q} out of range 0..10")


async def set_video_encoder(rt, token: str, changes: dict) -> None:
    changes = {k: v for k, v in changes.items() if v is not None}
    validate_encoder(rt.state, token, changes)

    def mut(st: CameraState):
        enc = st.encoder(token)
        for k, v in changes.items():
            setattr(enc, k, v)

    await rt.update(mut, {"encoders"})
    rt.log(f"video encoder {token} changed: {changes}")


def _clamp100(v):
    return None if v is None else max(0.0, min(100.0, float(v)))


async def set_imaging(rt, changes: dict) -> None:
    changes = {k: v for k, v in changes.items() if v is not None}
    for k in ("brightness", "color_saturation", "contrast", "sharpness", "wdr_level"):
        if k in changes:
            changes[k] = _clamp100(changes[k])

    def mut(st: CameraState):
        for k, v in changes.items():
            setattr(st.imaging, k, v)

    await rt.update(mut, {"imaging"})


# ---- profiles --------------------------------------------------------------------------------

async def create_profile(rt, name: str, token: str | None = None) -> MediaProfile:
    st = rt.state
    if len(st.profiles) >= st.capabilities.max_profiles:
        raise OnvifFault("Receiver", ["ter:Action", "ter:MaxNVTProfiles"], "Maximum number of profiles reached")
    if token and st.profile(token):
        raise invalid_arg("ProfileExists", f"Profile {token} already exists")
    if not token:
        n = 1
        while st.profile(f"Profile_{n}"):
            n += 1
        token = f"Profile_{n}"
    new = MediaProfile(token=token, name=name or token, fixed=False, vsc_token=None, vec_token=None)

    def mut(s: CameraState):
        s.profiles.append(new)

    await rt.update(mut, {"profiles"})
    return new


async def delete_profile(rt, token: str) -> None:
    p = rt.state.profile(token)
    if p is None:
        raise no_profile(token)
    if p.fixed:
        raise OnvifFault("Sender", ["ter:Action", "ter:DeletionOfFixedProfile"], "Fixed profile cannot be deleted")

    def mut(s: CameraState):
        s.profiles = [x for x in s.profiles if x.token != token]

    await rt.update(mut, {"profiles"})


async def set_profile_ref(rt, profile_token: str, kind: str, config_token: str | None) -> None:
    """kind: vsc | vec | ptz. config_token None = remove."""
    st = rt.state
    p = st.profile(profile_token)
    if p is None:
        raise no_profile(profile_token)
    if config_token is not None:
        exists = {"vsc": st.vsc, "vec": st.encoder, "ptz": st.ptz_config}[kind](config_token)
        if exists is None:
            raise no_config(config_token)

    def mut(s: CameraState):
        setattr(s.profile(profile_token), f"{kind}_token", config_token)

    await rt.update(mut, {"profiles"})


# ---- OSD -------------------------------------------------------------------------------------

async def upsert_osd(rt, item: OsdItem, create: bool) -> OsdItem:
    st = rt.state
    if create:
        if len(st.osd) >= st.capabilities.max_osd:
            raise OnvifFault("Receiver", ["ter:Action", "ter:MaxOSDs"], "Maximum number of OSDs reached")
        n = 1
        while any(o.token == f"OSD_{n}" for o in st.osd):
            n += 1
        item = item.model_copy(update={"token": f"OSD_{n}"})
    elif not any(o.token == item.token for o in st.osd):
        raise no_config(item.token)

    def mut(s: CameraState):
        s.osd = [o for o in s.osd if o.token != item.token] + [item]
        s.osd.sort(key=lambda o: o.token)

    await rt.update(mut, {"osd"})
    return item


async def delete_osd(rt, token: str) -> None:
    if not any(o.token == token for o in rt.state.osd):
        raise no_config(token)

    def mut(s: CameraState):
        s.osd = [o for o in s.osd if o.token != token]

    await rt.update(mut, {"osd"})


# ---- PTZ presets -----------------------------------------------------------------------------

async def set_preset(rt, name: str | None, token: str | None) -> str:
    st = rt.state
    if token and not any(p.token == token for p in st.ptz.presets):
        raise invalid_arg("NoToken", f"Preset {token} does not exist")
    if not token:
        if len(st.ptz.presets) >= st.ptz.max_presets:
            raise OnvifFault("Receiver", ["ter:Action", "ter:TooManyPresets"], "Maximum number of presets reached")
        used = {p.token for p in st.ptz.presets}
        n = 1
        while str(n) in used:
            n += 1
        token = str(n)
    pan, tilt, zoom = rt.ptz.pan, rt.ptz.tilt, rt.ptz.zoom
    preset = PtzPreset(token=token, name=name or f"Preset {token}", pan=pan, tilt=tilt, zoom=zoom)

    def mut(s: CameraState):
        s.ptz.presets = [p for p in s.ptz.presets if p.token != token] + [preset]

    await rt.update(mut, {"ptz"})
    return token


async def remove_preset(rt, token: str) -> None:
    if not any(p.token == token for p in rt.state.ptz.presets):
        raise invalid_arg("NoToken", f"Preset {token} does not exist")

    def mut(s: CameraState):
        s.ptz.presets = [p for p in s.ptz.presets if p.token != token]

    await rt.update(mut, {"ptz"})


async def set_home(rt) -> None:
    pan, tilt, zoom = rt.ptz.pan, rt.ptz.tilt, rt.ptz.zoom

    def mut(s: CameraState):
        s.ptz.home_pan, s.ptz.home_tilt, s.ptz.home_zoom = pan, tilt, zoom

    await rt.update(mut, {"ptz"})
