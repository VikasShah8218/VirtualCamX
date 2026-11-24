from dataclasses import dataclass
from datetime import datetime

from app.onvif.xml import Xml, el
from utilities.common import iso_z


@dataclass
class EventMessage:
    topic: str  # path without prefix, e.g. "VideoSource/MotionAlarm"
    utc_time: datetime
    operation: str  # Initialized | Changed | Deleted
    source: list[tuple[str, str]]
    data: list[tuple[str, str]]

    def to_json(self) -> dict:
        return {
            "topic": f"tns1:{self.topic}",
            "utc_time": iso_z(self.utc_time),
            "operation": self.operation,
            "source": dict(self.source),
            "data": dict(self.data),
        }


def notification_message_xml(msg: EventMessage, subscription_address: str | None = None) -> Xml:
    return el(
        "wsnt:NotificationMessage",
        el("wsnt:SubscriptionReference", el("wsa:Address", subscription_address)) if subscription_address else None,
        el("wsnt:Topic", f"tns1:{msg.topic}", Dialect="http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet"),
        el(
            "wsnt:Message",
            el(
                "tt:Message",
                el("tt:Source", [el("tt:SimpleItem", Name=n, Value=v) for n, v in msg.source]),
                el("tt:Data", [el("tt:SimpleItem", Name=n, Value=v) for n, v in msg.data]),
                UtcTime=iso_z(msg.utc_time),
                PropertyOperation=msg.operation,
            ),
        ),
    )
