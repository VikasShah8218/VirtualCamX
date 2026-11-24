"""ONVIF DeviceIO service (ver10/deviceIO/wsdl): virtual digital inputs and relay outputs."""
from app.onvif import namespaces as NS
from app.onvif.dispatcher import Access, OnvifContext, onvif_operation
from app.onvif.faults import invalid_arg
from app.onvif.handlers import service_caps
from app.onvif.handlers.device import apply_relay_settings, relay_xml
from app.onvif.xml import child, el, text

IO = NS.DEVICEIO


def _resp(op: str, *content):
    return el(f"tmd:{op}Response", *content)


@onvif_operation(IO, "GetServiceCapabilities", Access.PRE_AUTH)
async def get_service_capabilities(ctx: OnvifContext):
    return _resp("GetServiceCapabilities", service_caps.deviceio_caps(ctx))


@onvif_operation(IO, "GetVideoSources", Access.READ_MEDIA)
async def get_video_sources(ctx: OnvifContext):
    return _resp("GetVideoSources", el("tmd:Token", ctx.state.video_source.token))


@onvif_operation(IO, "GetRelayOutputs", Access.READ_MEDIA)
async def get_relay_outputs(ctx: OnvifContext):
    return _resp("GetRelayOutputs", [relay_xml("tmd:RelayOutputs", r) for r in ctx.state.io.relays])


@onvif_operation(IO, "GetRelayOutputOptions", Access.READ_MEDIA)
async def get_relay_output_options(ctx: OnvifContext):
    return _resp(
        "GetRelayOutputOptions",
        [
            el("tmd:RelayOutputOptions", el("tmd:Mode", "Bistable"), el("tmd:Mode", "Monostable"), el("tmd:DelayTimes", "1 120"), token=r.token)
            for r in ctx.state.io.relays
        ],
    )


@onvif_operation(IO, "SetRelayOutputSettings", Access.ACTUATE)
async def set_relay_output_settings(ctx: OnvifContext):
    ro = child(ctx.body, "RelayOutput")
    token = ro.get("token") if ro is not None else text(ctx.body, "RelayOutputToken")
    await apply_relay_settings(ctx, token, child(ro, "Properties") if ro is not None else child(ctx.body, "Properties"))
    return _resp("SetRelayOutputSettings")


@onvif_operation(IO, "SetRelayOutputState", Access.ACTUATE)
async def set_relay_output_state(ctx: OnvifContext):
    token = text(ctx.body, "RelayOutputToken")
    try:
        ctx.runtime.set_relay(token, text(ctx.body, "LogicalState") == "active", origin=f"onvif:{ctx.client_ip}")
    except ValueError as exc:
        raise invalid_arg("RelayToken", str(exc)) from None
    return _resp("SetRelayOutputState")


@onvif_operation(IO, "GetDigitalInputs", Access.READ_MEDIA)
async def get_digital_inputs(ctx: OnvifContext):
    return _resp("GetDigitalInputs", [el("tmd:DigitalInputs", token=d.token, IdleState=d.idle_state) for d in ctx.state.io.inputs])


@onvif_operation(IO, "GetDigitalInputConfigurationOptions", Access.READ_MEDIA)
async def get_digital_input_options(ctx: OnvifContext):
    return _resp("GetDigitalInputConfigurationOptions", el("tmd:DigitalInputOptions", el("tmd:IdleState", "closed"), el("tmd:IdleState", "open")))


for _op in ("GetAudioSources", "GetAudioOutputs", "GetVideoOutputs", "GetSerialPorts"):
    def _make_empty(op=_op):
        @onvif_operation(IO, op, Access.READ_MEDIA)
        async def empty(ctx: OnvifContext):
            return _resp(op)

    _make_empty()
