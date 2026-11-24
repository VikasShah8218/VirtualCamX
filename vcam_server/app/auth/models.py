from tortoise import fields
from tortoise.models import Model


class AdminUser(Model):
    id = fields.IntField(primary_key=True)
    username = fields.CharField(max_length=64, unique=True)
    password_hash = fields.CharField(max_length=255)
    role = fields.CharField(max_length=16, default="admin")
    must_change_password = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
