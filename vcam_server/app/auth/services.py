"""Manager UI / API login. Admin passwords are argon2-hashed; tokens are HS256 JWTs."""
from datetime import timedelta

import jwt

from app.auth.models import AdminUser
from settings.settings import settings
from utilities.common import utcnow
from utilities.crypto import hash_password, verify_password

ALGO = "HS256"


def create_token(username: str) -> str:
    now = utcnow()
    payload = {"sub": username, "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes), "typ": "vcam"}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGO)


def decode_token(token: str) -> str | None:
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=[ALGO])
    except jwt.PyJWTError:
        return None
    return data.get("sub")


async def authenticate(username: str, password: str) -> AdminUser | None:
    user = await AdminUser.get_or_none(username=username)
    if user and verify_password(user.password_hash, password):
        return user
    return None


async def ensure_default_admin() -> None:
    if not await AdminUser.exists():
        await AdminUser.create(
            username=settings.admin_default_user,
            password_hash=hash_password(settings.admin_default_password),
            must_change_password=True,
        )
