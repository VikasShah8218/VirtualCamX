"""ONVIF event topics supported by a virtual camera, and topic-filter matching."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TopicDef:
    key: str
    path: str  # without the tns1: prefix
    source: tuple[tuple[str, str], ...]  # (SimpleItem name, xsd type)
    data: tuple[tuple[str, str], ...]
    is_property: bool = True


TOPICS: dict[str, TopicDef] = {
    t.key: t
    for t in [
        TopicDef("motion_alarm", "VideoSource/MotionAlarm", (("Source", "tt:ReferenceToken"),), (("State", "xs:boolean"),)),
        TopicDef(
            "cell_motion",
            "RuleEngine/CellMotionDetector/Motion",
            (
                ("VideoSourceConfigurationToken", "tt:ReferenceToken"),
                ("VideoAnalyticsConfigurationToken", "tt:ReferenceToken"),
                ("Rule", "xs:string"),
            ),
            (("IsMotion", "xs:boolean"),),
        ),
        TopicDef("tamper", "VideoSource/GlobalSceneChange/ImagingService", (("Source", "tt:ReferenceToken"),), (("State", "xs:boolean"),)),
        TopicDef("digital_input", "Device/Trigger/DigitalInput", (("InputToken", "tt:ReferenceToken"),), (("LogicalState", "xs:boolean"),)),
        TopicDef("relay", "Device/Trigger/Relay", (("RelayToken", "tt:ReferenceToken"),), (("LogicalState", "tt:RelayLogicalState"),)),
        TopicDef("signal_loss", "VideoSource/SignalLoss", (("Source", "tt:ReferenceToken"),), (("State", "xs:boolean"),)),
    ]
}

# Simulator "kinds" -> topics they raise
KIND_TOPICS = {
    "motion": ["motion_alarm", "cell_motion"],
    "tamper": ["tamper"],
    "digital_input": ["digital_input"],
    "video_loss": ["signal_loss"],
}

TOPIC_DIALECTS = [
    "http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet",
    "http://docs.oasis-open.org/wsn/t-1/TopicExpression/Concrete",
]


def _strip_prefix(segment: str) -> str:
    return segment.split(":", 1)[1] if ":" in segment else segment


def parse_filter(expression: str | None) -> list[list[str]] | None:
    """'tns1:VideoSource/MotionAlarm|tns1:RuleEngine//.' -> [['VideoSource','MotionAlarm'], ['RuleEngine','//.']]"""
    if not expression or not expression.strip():
        return None
    out = []
    for part in expression.split("|"):
        part = part.strip()
        if not part:
            continue
        descendants = part.endswith("//.")
        if descendants:
            part = part[:-3]
        segs = [_strip_prefix(s) for s in part.split("/") if s]
        if descendants:
            segs.append("//.")
        out.append(segs)
    return out or None


def topic_matches(filters: list[list[str]] | None, topic_path: str) -> bool:
    if filters is None:
        return True
    segs = topic_path.split("/")
    for f in filters:
        if f and f[-1] == "//.":
            prefix = f[:-1]
            if len(segs) >= len(prefix) and all(p in ("*", s) for p, s in zip(prefix, segs)):
                return True
        elif len(f) == len(segs) and all(p in ("*", s) for p, s in zip(f, segs)):
            return True
    return False
