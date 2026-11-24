"""ONVIF Events service: PullPoint (tev) + Base Notification (wsnt)."""
from datetime import timedelta

from app.events.messages import notification_message_xml
from app.events.subscriptions import PullPointSubscription, PushSubscription, termination_from
from app.events.topics import TOPIC_DIALECTS, TOPICS, parse_filter
from app.onvif import namespaces as NS
from app.onvif.dispatcher import Access, OnvifContext, onvif_operation
from app.onvif.faults import OnvifFault, invalid_arg
from app.onvif.handlers import service_caps
from app.onvif.xml import Xml, el, num, text
from settings.settings import settings
from utilities.common import iso_z, parse_iso_duration, parse_xs_datetime

EV = NS.EVENTS
WSNT = NS.WSNT
DEFAULT_TTL_S = 60.0


def _resp(op: str, *content):
    return el(f"tev:{op}Response", *content)


def _sub_id(ctx: OnvifContext) -> str:
    if "/subscription/" in ctx.path:
        return ctx.path.rstrip("/").rsplit("/", 1)[-1]
    if ctx.req.wsa_to and "/subscription/" in ctx.req.wsa_to:
        return ctx.req.wsa_to.rstrip("/").rsplit("/", 1)[-1]
    raise invalid_arg("ResourceUnknown", "No subscription reference in request")


def _subscription(ctx: OnvifContext):
    sub = ctx.runtime.broker.get(_sub_id(ctx))
    if sub is None:
        raise OnvifFault("Sender", ["ter:InvalidArgVal", "ter:ResourceUnknown"], "Subscription does not exist or has expired")
    return sub


def _check_capacity(ctx: OnvifContext) -> None:
    if ctx.runtime.broker.count() >= settings.max_subscriptions_per_camera:
        raise OnvifFault("Receiver", ["ter:Action", "ter:TooManySubscriptions"], "Maximum number of subscriptions reached")


def _filter(ctx: OnvifContext):
    return parse_filter(text(ctx.body, "Filter", "TopicExpression"))


def _sub_address(ctx: OnvifContext, sub_id: str) -> str:
    return f"{ctx.base_url()}/onvif/subscription/{sub_id}"


@onvif_operation(EV, "GetServiceCapabilities", Access.PRE_AUTH)
async def get_service_capabilities(ctx: OnvifContext):
    return _resp("GetServiceCapabilities", service_caps.events_caps(ctx))


# ---- topic set -----------------------------------------------------------------------------

def _topic_set_xml(keys: list[str]) -> Xml:
    tree: dict = {}
    for key in keys:
        node = tree
        for seg in TOPICS[key].path.split("/"):
            node = node.setdefault(seg, {})
        node["__def__"] = TOPICS[key]

    def render(name: str, node: dict, root: bool) -> Xml:
        tag = f"tns1:{name}" if root else name
        d = node.get("__def__")
        desc = None
        if d:
            desc = el(
                "tt:MessageDescription",
                el("tt:Source", [el("tt:SimpleItemDescription", Name=n, Type=t) for n, t in d.source]),
                el("tt:Data", [el("tt:SimpleItemDescription", Name=n, Type=t) for n, t in d.data]),
                IsProperty=d.is_property,
            )
        kids = [render(k, v, False) for k, v in node.items() if k != "__def__"]
        attrs = {"wstop__topic": True} if d else {}
        return el(tag, desc, kids, **attrs)

    return el("wstop:TopicSet", [render(k, v, True) for k, v in tree.items()])


@onvif_operation(EV, "GetEventProperties", Access.READ_MEDIA)
async def get_event_properties(ctx: OnvifContext):
    return _resp(
        "GetEventProperties",
        el("tev:TopicNamespaceLocation", "http://www.onvif.org/onvif/ver10/topics/topicns.xml"),
        el("wsnt:FixedTopicSet", True),
        _topic_set_xml(ctx.runtime.broker.topic_keys()),
        [el("wsnt:TopicExpressionDialect", d) for d in TOPIC_DIALECTS],
        el("tev:MessageContentFilterDialect", "http://www.onvif.org/ver10/tev/messageContentFilter/ItemFilter"),
        el("tev:MessageContentSchemaLocation", "http://www.onvif.org/onvif/ver10/schema/onvif.xsd"),
    )


# ---- PullPoint -----------------------------------------------------------------------------

@onvif_operation(EV, "CreatePullPointSubscription", Access.READ_MEDIA)
async def create_pull_point_subscription(ctx: OnvifContext):
    _check_capacity(ctx)
    now = ctx.runtime.clock.now()
    term, ttl = termination_from(now, text(ctx.body, "InitialTerminationTime"), DEFAULT_TTL_S, parse_iso_duration, parse_xs_datetime)
    sub = PullPointSubscription(_filter(ctx), term, "", ttl)
    sub.address = _sub_address(ctx, sub.id)
    ctx.runtime.broker.add(sub)
    ctx.runtime.log(f"PullPoint subscription {sub.id} created by {ctx.client_ip} (ttl {ttl:g}s)")
    return _resp(
        "CreatePullPointSubscription",
        el("tev:SubscriptionReference", el("wsa:Address", sub.address)),
        el("wsnt:CurrentTime", iso_z(now)),
        el("wsnt:TerminationTime", iso_z(term)),
    )


@onvif_operation(EV, "PullMessages", Access.READ_MEDIA)
async def pull_messages(ctx: OnvifContext):
    sub = _subscription(ctx)
    if not isinstance(sub, PullPointSubscription):
        raise invalid_arg("ResourceUnknown", "Not a PullPoint subscription")
    timeout = parse_iso_duration(text(ctx.body, "Timeout", default="PT10S") or "PT10S") or 10.0
    limit = num(ctx.body, "MessageLimit", default=100, cast=int)
    # Keep-alive: an NVR that keeps pulling should not lose its subscription
    now = ctx.runtime.clock.now()
    min_term = now + timedelta(seconds=timeout + 10)
    if sub.termination < min_term:
        sub.termination = now + timedelta(seconds=max(sub.initial_ttl, timeout + 10))
    msgs = await sub.pull(timeout, limit)
    now = ctx.runtime.clock.now()
    return _resp(
        "PullMessages",
        el("tev:CurrentTime", iso_z(now)),
        el("tev:TerminationTime", iso_z(sub.termination)),
        [notification_message_xml(m) for m in msgs],
    )


@onvif_operation(EV, "SetSynchronizationPoint", Access.READ_MEDIA)
async def set_synchronization_point(ctx: OnvifContext):
    broker = ctx.runtime.broker
    try:
        targets = [_subscription(ctx)]
    except OnvifFault:
        targets = [s for s in broker.subscriptions.values() if not s.closed]
    for sub in targets:
        for m in broker.initial_messages(sub):
            sub.deliver(m)
    return _resp("SetSynchronizationPoint")


@onvif_operation(EV, "Seek", Access.READ_MEDIA)
async def seek(ctx: OnvifContext):
    raise OnvifFault("Receiver", ["ter:ActionNotSupported", "ter:SeekNotSupported"], "Seek is not supported")


# ---- Base Notification (push) + subscription manager ---------------------------------------

@onvif_operation(WSNT, "Subscribe", Access.READ_MEDIA)
async def subscribe(ctx: OnvifContext):
    _check_capacity(ctx)
    consumer = text(ctx.body, "ConsumerReference", "Address")
    if not consumer or not consumer.startswith(("http://", "https://")):
        raise invalid_arg("InvalidArgVal", "ConsumerReference/Address must be an http(s) URL")
    now = ctx.runtime.clock.now()
    term, _ = termination_from(now, text(ctx.body, "InitialTerminationTime"), DEFAULT_TTL_S, parse_iso_duration, parse_xs_datetime)
    sub = PushSubscription(_filter(ctx), term, "", consumer, ctx.runtime.name)
    sub.address = _sub_address(ctx, sub.id)
    ctx.runtime.broker.add(sub)
    ctx.runtime.log(f"push subscription {sub.id} -> {consumer}")
    return el(
        "wsnt:SubscribeResponse",
        el("wsnt:SubscriptionReference", el("wsa:Address", sub.address)),
        el("wsnt:CurrentTime", iso_z(now)),
        el("wsnt:TerminationTime", iso_z(term)),
    )


@onvif_operation(WSNT, "Renew", Access.READ_MEDIA)
async def renew(ctx: OnvifContext):
    sub = _subscription(ctx)
    now = ctx.runtime.clock.now()
    term, _ = termination_from(now, text(ctx.body, "TerminationTime"), DEFAULT_TTL_S, parse_iso_duration, parse_xs_datetime)
    sub.termination = term
    return el("wsnt:RenewResponse", el("wsnt:TerminationTime", iso_z(term)), el("wsnt:CurrentTime", iso_z(now)))


@onvif_operation(WSNT, "Unsubscribe", Access.READ_MEDIA)
async def unsubscribe(ctx: OnvifContext):
    sub = _subscription(ctx)
    ctx.runtime.broker.remove(sub.id)
    ctx.runtime.log(f"subscription {sub.id} unsubscribed")
    return el("wsnt:UnsubscribeResponse")


@onvif_operation(WSNT, "GetCurrentMessage", Access.READ_MEDIA)
async def get_current_message(ctx: OnvifContext):
    raise OnvifFault("Receiver", ["ter:ActionNotSupported"], "GetCurrentMessage is not supported")

