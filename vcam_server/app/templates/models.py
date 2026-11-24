from tortoise import fields
from tortoise.models import Model


class CameraTemplate(Model):
    """User-defined template. Built-in templates live in app/templates/builtin.py."""

    id = fields.IntField(primary_key=True)
    key = fields.CharField(max_length=64, unique=True)
    name = fields.CharField(max_length=128)
    definition = fields.JSONField()  # same shape as a BUILTIN_TEMPLATES entry
    created_at = fields.DatetimeField(auto_now_add=True)
