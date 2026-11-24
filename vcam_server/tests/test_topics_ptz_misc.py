from app.discovery.wsd import scope_matches
from app.events.topics import parse_filter, topic_matches
from app.ptz.controller import crop_rect
from app.runtime.camera_runtime import onvif_fmt_to_strftime, tz_offset_hours
from utilities.common import parse_iso_duration


def test_topic_filter_concrete_and_descendants():
    f = parse_filter("tns1:VideoSource/MotionAlarm|tns1:RuleEngine//.")
    assert topic_matches(f, "VideoSource/MotionAlarm")
    assert topic_matches(f, "RuleEngine/CellMotionDetector/Motion")
    assert not topic_matches(f, "Device/Trigger/DigitalInput")


def test_topic_filter_other_prefix_and_none():
    assert topic_matches(parse_filter("ns0:Device/Trigger/*"), "Device/Trigger/Relay")
    assert topic_matches(None, "anything/at/all")


def test_crop_rect_zoom_and_pan():
    assert crop_rect(0, 0, 0, 1920, 1080) == (1920, 1080, 0, 0)
    w, h, x, y = crop_rect(1, -1, 1, 1920, 1080)  # full zoom, far right, far down
    assert (w, h) == (480, 270) and x == 1920 - 480 and y == 1080 - 270


def test_tz_offsets():
    assert tz_offset_hours("UTC-5:30") == 5.5
    assert tz_offset_hours("CET-1CEST") == 1.0
    assert tz_offset_hours("EST5EDT") == -5.0
    assert tz_offset_hours("garbage") == 0.0


def test_onvif_date_format():
    assert onvif_fmt_to_strftime("yyyy-MM-dd HH:mm:ss") == "%Y-%m-%d %H:%M:%S"
    assert onvif_fmt_to_strftime("dd/MM/yyyy hh:mm:ss tt") == "%d/%m/%Y %I:%M:%S %p"


def test_iso_duration():
    assert parse_iso_duration("PT60S") == 60
    assert parse_iso_duration("PT1M30S") == 90
    assert parse_iso_duration("PT0.5S") == 0.5
    assert parse_iso_duration("nonsense") is None


def test_wsd_scope_matching():
    scopes = ["onvif://www.onvif.org/type/video_encoder", "onvif://www.onvif.org/name/Gate-1"]
    assert scope_matches(["onvif://www.onvif.org/type"], scopes)
    assert scope_matches(["onvif://www.onvif.org/name/Gate-1"], scopes)
    assert not scope_matches(["onvif://www.onvif.org/name/Gate"], scopes)  # segment-wise, not string prefix
    assert not scope_matches(["onvif://www.onvif.org/location/x"], scopes)
