"""Camera user management (shared by ONVIF user ops, the camera web API and the Manager API)."""
import re

from app.cameras.models import CameraUser
from app.onvif.faults import OnvifFault
from utilities.crypto import encrypt_secret

LEVELS = ("Administrator", "Operator", "User")
_valid_name = re.compile(r"^[A-Za-z0-9_.@-]{1,32}$")


def _prohibited(sub: str, reason: str) -> OnvifFault:
    return OnvifFault("Sender", ["ter:OperationProhibited", f"ter:{sub}"], reason)


def _check(username: str, password: str | None, level: str | None) -> None:
    if not _valid_name.match(username or ""):
        raise _prohibited("UsernameTooLong" if len(username or "") > 32 else "Username", "Invalid username")
    if password is not None and not (1 <= len(password) <= 64):
        raise _prohibited("PasswordTooLong" if len(password) > 64 else "PasswordTooWeak", "Password must be 1..64 characters")
    if level is not None and level not in LEVELS:
        raise _prohibited("AnonymousNotAllowed" if level == "Anonymous" else "UserLevel", f"Unsupported user level {level}")


async def create_user(rt, username: str, password: str, level: str) -> None:
    _check(username, password, level)
    if username in rt.users:
        raise _prohibited("UsernameClash", f"User {username} already exists")
    if len(rt.users) >= 16:
        raise OnvifFault("Receiver", ["ter:Action", "ter:TooManyUsers"], "Maximum number of users reached")
    await CameraUser.create(camera_id=rt.camera_id, username=username, password_enc=encrypt_secret(password), level=level)
    await rt.manager.reload_users(rt.camera_id)
    rt.log(f"user {username} created ({level})")


async def update_user(rt, username: str, password: str | None, level: str | None) -> None:
    _check(username, password, level)
    if username not in rt.users:
        raise OnvifFault("Sender", ["ter:InvalidArgVal", "ter:UsernameMissing"], f"User {username} does not exist")
    if level and level != "Administrator" and rt.users[username].level == "Administrator" and _admin_count(rt) <= 1:
        raise _prohibited("FixedUser", "At least one Administrator must remain")
    updates = {}
    if password:
        updates["password_enc"] = encrypt_secret(password)
    if level:
        updates["level"] = level
    if updates:
        await CameraUser.filter(camera_id=rt.camera_id, username=username).update(**updates)
        await rt.manager.reload_users(rt.camera_id)
        rt.log(f"user {username} updated")


async def delete_user(rt, username: str) -> None:
    if username not in rt.users:
        raise OnvifFault("Sender", ["ter:InvalidArgVal", "ter:UsernameMissing"], f"User {username} does not exist")
    if rt.users[username].level == "Administrator" and _admin_count(rt) <= 1:
        raise _prohibited("FixedUser", "Cannot delete the last Administrator")
    await CameraUser.filter(camera_id=rt.camera_id, username=username).delete()
    await rt.manager.reload_users(rt.camera_id)
    rt.log(f"user {username} deleted")


async def reset_users(rt, username: str, password: str) -> None:
    await CameraUser.filter(camera_id=rt.camera_id).delete()
    await CameraUser.create(camera_id=rt.camera_id, username=username, password_enc=encrypt_secret(password), level="Administrator")
    await rt.manager.reload_users(rt.camera_id)


def _admin_count(rt) -> int:
    return sum(1 for u in rt.users.values() if u.level == "Administrator")
