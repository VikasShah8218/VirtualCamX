import base64
import hashlib
from datetime import datetime, timedelta, timezone

from app.onvif.security import NonceCache, UserEntry, digest_challenge, parse_auth_header, verify_http_auth, verify_wsse

USERS = {"admin": UserEntry("admin", "admin123", "Administrator")}
NOW = datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)


def token(password="admin123", created=NOW, nonce=b"0123456789abcdef", user="admin"):
    c = created.strftime("%Y-%m-%dT%H:%M:%SZ")
    d = base64.b64encode(hashlib.sha1(nonce + c.encode() + password.encode()).digest()).decode()
    return {"username": user, "password": d, "password_type": "...#PasswordDigest", "nonce": base64.b64encode(nonce).decode(), "created": c}


def test_wsse_digest_ok():
    assert verify_wsse(token(), USERS, NOW, NonceCache(600), True).ok


def test_wsse_wrong_password():
    r = verify_wsse(token(password="nope"), USERS, NOW, NonceCache(600), True)
    assert not r.ok and "digest" in r.reason


def test_wsse_unknown_user():
    assert not verify_wsse(token(user="ghost"), USERS, NOW, NonceCache(600), True).ok


def test_wsse_created_too_far_from_camera_clock():
    r = verify_wsse(token(created=NOW - timedelta(hours=1)), USERS, NOW, NonceCache(600), True)
    assert not r.ok and "camera time" in r.reason


def test_wsse_replay_rejected():
    cache = NonceCache(600)
    t = token()
    assert verify_wsse(t, USERS, NOW, cache, True).ok
    assert not verify_wsse(t, USERS, NOW, cache, True).ok


def test_wsse_password_text():
    t = {"username": "admin", "password": "admin123", "password_type": "...#PasswordText", "nonce": "", "created": ""}
    assert verify_wsse(t, USERS, NOW, NonceCache(600), True).ok
    assert not verify_wsse(t, USERS, NOW, NonceCache(600), False).ok


def _md5(s):
    return hashlib.md5(s.encode()).hexdigest()


def test_http_digest_roundtrip():
    ch = parse_auth_header(digest_challenge())[1]
    uri, nc, cnonce = "/onvif/device_service", "00000001", "abc"
    ha1 = _md5(f"admin:{ch['realm']}:admin123")
    ha2 = _md5(f"POST:{uri}")
    resp = _md5(f"{ha1}:{ch['nonce']}:{nc}:{cnonce}:auth:{ha2}")
    header = (f'Digest username="admin", realm="{ch["realm"]}", nonce="{ch["nonce"]}", uri="{uri}", '
              f'response="{resp}", qop=auth, nc={nc}, cnonce="{cnonce}"')
    assert verify_http_auth(header, "POST", USERS, False).ok
    assert not verify_http_auth(header.replace(resp, "0" * 32), "POST", USERS, False).ok


def test_basic_disabled_by_default():
    hdr = "Basic " + base64.b64encode(b"admin:admin123").decode()
    assert not verify_http_auth(hdr, "GET", USERS, False).ok
    assert verify_http_auth(hdr, "GET", USERS, True).ok
