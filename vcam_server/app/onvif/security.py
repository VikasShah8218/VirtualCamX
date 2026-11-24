"""Authentication for camera listeners: WS-UsernameToken (ONVIF) and HTTP Digest/Basic.

Both need the plain password of the camera user, which is why camera passwords are
stored encrypted (utilities/crypto.py).
"""
import base64
import hashlib
import hmac
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime

from settings.settings import settings
from utilities.common import parse_xs_datetime

REALM = "VirtualCamX"
_DIGEST_NONCE_TTL = 300


@dataclass
class UserEntry:
    username: str
    password: str
    level: str  # Administrator | Operator | User


@dataclass
class AuthResult:
    ok: bool
    user: UserEntry | None = None
    method: str = "none"  # wsse | digest | basic | none
    reason: str = ""


class NonceCache:
    """Remembers recent WS-Security nonces to block replays."""

    def __init__(self, ttl: float):
        self.ttl = ttl
        self._seen: dict[str, float] = {}

    def check_and_add(self, nonce: str) -> bool:
        now = time.monotonic()
        if len(self._seen) > 5000:
            self._seen = {k: v for k, v in self._seen.items() if now - v < self.ttl}
        if nonce in self._seen and now - self._seen[nonce] < self.ttl:
            return False
        self._seen[nonce] = now
        return True


def verify_wsse(token: dict, users: dict[str, UserEntry], camera_now: datetime, nonces: NonceCache,
                allow_text: bool) -> AuthResult:
    user = users.get(token.get("username", ""))
    if user is None:
        return AuthResult(False, method="wsse", reason="unknown user")
    ptype = token.get("password_type", "")
    supplied = token.get("password", "")
    if ptype.endswith("PasswordText") or (not ptype and not token.get("nonce")):
        if not allow_text:
            return AuthResult(False, method="wsse", reason="PasswordText not allowed")
        ok = hmac.compare_digest(supplied, user.password)
        return AuthResult(ok, user if ok else None, "wsse", "" if ok else "bad password")

    try:
        nonce_bytes = base64.b64decode(token.get("nonce", ""))
    except Exception:
        return AuthResult(False, method="wsse", reason="bad nonce encoding")
    created = token.get("created", "")
    expected = base64.b64encode(
        hashlib.sha1(nonce_bytes + created.encode("utf-8") + user.password.encode("utf-8")).digest()
    ).decode()
    if not hmac.compare_digest(expected, supplied):
        return AuthResult(False, method="wsse", reason="bad password digest")

    tol = settings.wssec_time_tolerance_s
    if tol > 0:
        created_dt = parse_xs_datetime(created)
        if created_dt is None:
            return AuthResult(False, method="wsse", reason="bad Created")
        skew = abs((camera_now - created_dt).total_seconds())
        if skew > tol:
            return AuthResult(False, method="wsse", reason=f"Created is {int(skew)}s away from camera time")
        if not nonces.check_and_add(token.get("nonce", "") + created):
            return AuthResult(False, method="wsse", reason="nonce replay")
    return AuthResult(True, user, "wsse")


# ---- HTTP Digest (RFC 7616, MD5, qop=auth) ------------------------------------------------

def _nonce_sig(ts: str) -> str:
    return hmac.new(settings.secret_key.encode(), ts.encode(), hashlib.sha256).hexdigest()[:24]


def new_digest_nonce() -> str:
    ts = str(int(time.time()))
    return base64.b64encode(f"{ts}:{_nonce_sig(ts)}".encode()).decode()


def _nonce_valid(nonce: str) -> bool:
    try:
        ts, sig = base64.b64decode(nonce).decode().split(":", 1)
    except Exception:
        return False
    if not hmac.compare_digest(sig, _nonce_sig(ts)):
        return False
    return time.time() - int(ts) < _DIGEST_NONCE_TTL


def digest_challenge(stale: bool = False) -> str:
    opaque = secrets.token_hex(8)
    return (
        f'Digest realm="{REALM}", qop="auth", nonce="{new_digest_nonce()}", opaque="{opaque}", '
        f'algorithm=MD5{", stale=TRUE" if stale else ""}'
    )


_kv = re.compile(r'(\w+)\s*=\s*(?:"([^"]*)"|([^,\s]+))')


def parse_auth_header(value: str) -> tuple[str, dict[str, str] | str]:
    scheme, _, rest = value.partition(" ")
    scheme = scheme.lower()
    if scheme == "basic":
        return "basic", rest.strip()
    return scheme, {m.group(1).lower(): (m.group(2) if m.group(2) is not None else m.group(3)) for m in _kv.finditer(rest)}


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def verify_http_auth(header: str | None, method: str, users: dict[str, UserEntry], allow_basic: bool) -> AuthResult:
    if not header:
        return AuthResult(False, method="none", reason="no credentials")
    scheme, params = parse_auth_header(header)
    if scheme == "basic":
        if not allow_basic:
            return AuthResult(False, method="basic", reason="basic auth disabled")
        try:
            username, _, password = base64.b64decode(params).decode("utf-8").partition(":")  # type: ignore[arg-type]
        except Exception:
            return AuthResult(False, method="basic", reason="bad basic header")
        user = users.get(username)
        ok = bool(user) and hmac.compare_digest(user.password, password)
        return AuthResult(ok, user if ok else None, "basic", "" if ok else "bad credentials")
    if scheme != "digest" or not isinstance(params, dict):
        return AuthResult(False, method=scheme, reason="unsupported auth scheme")

    user = users.get(params.get("username", ""))
    if user is None:
        return AuthResult(False, method="digest", reason="unknown user")
    nonce = params.get("nonce", "")
    if not _nonce_valid(nonce):
        return AuthResult(False, method="digest", reason="stale nonce")
    realm = params.get("realm", REALM)
    ha1 = _md5(f"{user.username}:{realm}:{user.password}")
    ha2 = _md5(f"{method}:{params.get('uri', '')}")
    qop = params.get("qop")
    if qop:
        expected = _md5(f"{ha1}:{nonce}:{params.get('nc', '')}:{params.get('cnonce', '')}:{qop}:{ha2}")
    else:
        expected = _md5(f"{ha1}:{nonce}:{ha2}")
    ok = hmac.compare_digest(expected, params.get("response", ""))
    return AuthResult(ok, user if ok else None, "digest", "" if ok else "bad digest response")
