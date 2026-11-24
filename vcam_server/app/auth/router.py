from fastapi import APIRouter, HTTPException

from app.auth.deps import AdminDep
from app.auth.models import AdminUser
from app.auth.schemas import AdminUserIn, AdminUserOut, ChangePasswordIn, LoginIn, TokenOut
from app.auth.services import authenticate, create_token
from utilities.crypto import hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn):
    user = await authenticate(body.username, body.password)
    if not user:
        raise HTTPException(401, "Wrong username or password")
    return TokenOut(access_token=create_token(user.username), must_change_password=user.must_change_password)


@router.get("/me")
async def me(user: str = AdminDep):
    return {"username": user}


@router.post("/change-password")
async def change_password(body: ChangePasswordIn, user: str = AdminDep):
    u = await AdminUser.get_or_none(username=user)
    if not u or not verify_password(u.password_hash, body.old_password):
        raise HTTPException(400, "Old password is wrong")
    u.password_hash = hash_password(body.new_password)
    u.must_change_password = False
    await u.save()
    return {"ok": True}


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(_: str = AdminDep):
    return [AdminUserOut(id=u.id, username=u.username, role=u.role, must_change_password=u.must_change_password) for u in await AdminUser.all()]


@router.post("/users", response_model=AdminUserOut)
async def create_user(body: AdminUserIn, _: str = AdminDep):
    if await AdminUser.exists(username=body.username):
        raise HTTPException(409, "User already exists")
    u = await AdminUser.create(username=body.username, password_hash=hash_password(body.password))
    return AdminUserOut(id=u.id, username=u.username, role=u.role, must_change_password=u.must_change_password)


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, user: str = AdminDep):
    u = await AdminUser.get_or_none(id=user_id)
    if not u:
        raise HTTPException(404, "Not found")
    if u.username == user:
        raise HTTPException(400, "You cannot delete yourself")
    if await AdminUser.all().count() <= 1:
        raise HTTPException(400, "At least one admin must remain")
    await u.delete()
    return {"ok": True}
