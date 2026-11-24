"""Per-service <Capabilities> elements (used by GetServiceCapabilities and GetServices)."""
from app.onvif import namespaces as NS
from app.onvif.dispatcher import OnvifContext
from app.onvif.xml import Xml, el
from settings.settings import settings


def device_caps(ctx: OnvifContext) -> Xml:
    return el(
        "tds:Capabilities",
        el("tds:Network", IPFilter=False, ZeroConfiguration=False, IPVersion6=False, DynDNS=False,
           Dot11Configuration=False, HostnameFromDHCP=False, NTP=1),
        el("tds:Security", UsernameToken=True, HttpDigest=True, OnboardKeyGeneration=False,
           AccessPolicyConfig=False, DefaultAccessPolicy=True, Dot1X=False, RemoteUserHandling=False,
           SAMLToken=False, KerberosToken=False, RELToken=False, MaxUsers=16,
           MaxUserNameLength=32, MaxPasswordLength=64),
        el("tds:System", DiscoveryResolve=True, DiscoveryBye=True, RemoteDiscovery=False, SystemBackup=False,
           SystemLogging=True, FirmwareUpgrade=False, HttpFirmwareUpgrade=False, HttpSystemBackup=False,
           HttpSystemLogging=False, HttpSupportInformation=False),
    )


def media_caps(ctx: OnvifContext) -> Xml:
    st = ctx.state
    return el(
        "trt:Capabilities",
        el("trt:ProfileCapabilities", MaximumNumberOfProfiles=st.capabilities.max_profiles),
        el("trt:StreamingCapabilities", RTPMulticast=False, RTP_TCP=True, RTP_RTSP_TCP=True, NonAggregateControl=False,
           NoRTSPStreaming=False),
        SnapshotUri=True, Rotation=False, VideoSourceMode=False, OSD=True, EXICompression=False,
    )


def media2_caps(ctx: OnvifContext) -> Xml:
    st = ctx.state
    configs = "VideoSource VideoEncoder" + (" PTZ" if st.capabilities.has_ptz else "")
    return el(
        "tr2:Capabilities",
        el("tr2:ProfileCapabilities", MaximumNumberOfProfiles=st.capabilities.max_profiles, ConfigurationsSupported=configs),
        el("tr2:StreamingCapabilities", RTSPStreaming=True, RTPMulticast=False, RTP_RTSP_TCP=True,
           NonAggregateControl=False, AutoStartMulticast=False),
        SnapshotUri=True, Rotation=False, VideoSourceMode=False, OSD=True, TemporaryOSDText=False, Mask=False,
        SourceMask=False,
    )


def events_caps(ctx: OnvifContext) -> Xml:
    return el(
        "tev:Capabilities",
        WSSubscriptionPolicySupport=False, WSPullPointSupport=True, WSPausableSubscriptionManagerInterfaceSupport=False,
        MaxNotificationProducers=settings.max_subscriptions_per_camera, MaxPullPoints=settings.max_subscriptions_per_camera,
        PersistentNotificationStorage=False,
    )


def imaging_caps(ctx: OnvifContext) -> Xml:
    return el("timg:Capabilities", ImageStabilization=False, Presets=False)


def ptz_caps(ctx: OnvifContext) -> Xml:
    return el("tptz:Capabilities", EFlip=False, Reverse=False, GetCompatibleConfigurations=False, MoveStatus=True,
              StatusPosition=True)


def deviceio_caps(ctx: OnvifContext) -> Xml:
    io = ctx.state.io
    return el("tmd:Capabilities", VideoSources=1, VideoOutputs=0, AudioSources=0, AudioOutputs=0,
              RelayOutputs=len(io.relays), DigitalInputs=len(io.inputs), SerialPorts=0)


def services(ctx: OnvifContext) -> list[tuple[str, callable]]:
    out = [
        (NS.DEVICE, device_caps),
        (NS.MEDIA, media_caps),
        (NS.MEDIA2, media2_caps),
        (NS.EVENTS, events_caps),
        (NS.IMAGING, imaging_caps),
    ]
    if ctx.state.capabilities.has_ptz:
        out.append((NS.PTZ, ptz_caps))
    out.append((NS.DEVICEIO, deviceio_caps))
    return out
