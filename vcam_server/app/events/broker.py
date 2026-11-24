"""EventBroker: one per camera. Keeps property state and fans messages out to subscriptions."""
import logging
from typing import TYPE_CHECKING

from app.events.messages import EventMessage
from app.events.subscriptions import PullPointSubscription, PushSubscription, Subscription
from app.events.topics import TOPICS
from app.system import hub

if TYPE_CHECKING:
    from app.runtime.camera_runtime import CameraRuntime

logger = logging.getLogger("vcam.events")

# Written to EventLog in batches by the event_log_flush loop
EVENT_LOG_BUFFER: list[dict] = []


class EventBroker:
    def __init__(self, runtime: "CameraRuntime"):
        self.rt = runtime
        self.properties: dict[tuple[str, tuple], EventMessage] = {}
        self.subscriptions: dict[str, Subscription] = {}

    # ---- topic set --------------------------------------------------------------------------
    def topic_keys(self) -> list[str]:
        keys = ["motion_alarm", "cell_motion", "tamper", "signal_loss"]
        if self.rt.state.io.inputs:
            keys.append("digital_input")
        if self.rt.state.io.relays:
            keys.append("relay")
        return keys

    def reset_properties(self) -> None:
        """Called at camera start: every property gets its initial value."""
        self.properties.clear()
        st = self.rt.state
        vs = st.video_source.token
        vsc = st.video_source_configs[0].token if st.video_source_configs else "VideoSourceConfig_1"
        for key, src, data in [
            ("motion_alarm", [("Source", vs)], [("State", "false")]),
            ("cell_motion", [("VideoSourceConfigurationToken", vsc), ("VideoAnalyticsConfigurationToken", "VideoAnalyticsConfig_1"), ("Rule", "MyMotionDetectorRule")], [("IsMotion", "false")]),
            ("tamper", [("Source", vs)], [("State", "false")]),
            ("signal_loss", [("Source", vs)], [("State", "false")]),
        ]:
            self._store(key, src, data, "Initialized")
        for di in st.io.inputs:
            self._store("digital_input", [("InputToken", di.token)], [("LogicalState", "true" if di.active else "false")], "Initialized")
        for ro in st.io.relays:
            self._store("relay", [("RelayToken", ro.token)], [("LogicalState", "active" if ro.active else "inactive")], "Initialized")

    def _store(self, key: str, source, data, op: str) -> EventMessage:
        topic = TOPICS[key].path
        msg = EventMessage(topic, self.rt.clock.now(), op, list(source), list(data))
        self.properties[(topic, tuple(source))] = msg
        return msg

    def property_value(self, key: str, source: list[tuple[str, str]]) -> dict | None:
        msg = self.properties.get((TOPICS[key].path, tuple(source)))
        return dict(msg.data) if msg else None

    # ---- publishing ------------------------------------------------------------------------
    def publish(self, key: str, source: list[tuple[str, str]], data: list[tuple[str, str]], origin: str = "simulator") -> EventMessage | None:
        topic = TOPICS[key].path
        prev = self.properties.get((topic, tuple(source)))
        if prev is not None and prev.data == list(data):
            return None  # property did not change: a real camera sends nothing
        msg = self._store(key, source, data, "Changed")
        for sub in list(self.subscriptions.values()):
            if not sub.closed and sub.matches(topic):
                sub.deliver(msg)
        EVENT_LOG_BUFFER.append(
            {
                "camera_id": self.rt.camera_id,
                "topic": f"tns1:{topic}",
                "operation": "Changed",
                "source": dict(source),
                "data": dict(data),
                "origin": origin,
                "utc_time": msg.utc_time,
            }
        )
        hub.publish("event", {"camera_id": self.rt.camera_id, "origin": origin, **msg.to_json()})
        self.rt.on_event_published(key, msg)
        return msg

    def initial_messages(self, sub: Subscription) -> list[EventMessage]:
        now = self.rt.clock.now()
        return [
            EventMessage(m.topic, now, "Initialized", m.source, m.data)
            for m in self.properties.values()
            if sub.matches(m.topic)
        ]

    # ---- subscriptions -----------------------------------------------------------------------
    def add(self, sub: Subscription) -> None:
        self.subscriptions[sub.id] = sub
        for m in self.initial_messages(sub):
            sub.deliver(m)

    def get(self, sub_id: str) -> Subscription | None:
        sub = self.subscriptions.get(sub_id)
        return None if sub is None or sub.closed else sub

    def remove(self, sub_id: str) -> None:
        sub = self.subscriptions.pop(sub_id, None)
        if sub:
            sub.close()

    def count(self) -> int:
        return sum(1 for s in self.subscriptions.values() if not s.closed)

    def cleanup(self) -> None:
        now = self.rt.clock.now()
        for sid, sub in list(self.subscriptions.items()):
            if sub.closed or sub.termination < now:
                self.remove(sid)

    def close_all(self) -> None:
        for sid in list(self.subscriptions):
            self.remove(sid)

    def summary(self) -> list[dict]:
        return [
            {
                "id": s.id,
                "kind": s.kind,
                "termination": s.termination.isoformat(),
                "consumer": getattr(s, "consumer_url", None),
                "queued": len(s.queue) if isinstance(s, PullPointSubscription) else s.queue.qsize() if isinstance(s, PushSubscription) else 0,
            }
            for s in self.subscriptions.values()
            if not s.closed
        ]
