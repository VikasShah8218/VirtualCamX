from tortoise import fields
from tortoise.models import Model


class MediaItem(Model):
    """Footage registered by path. The file is used in place: never uploaded, copied or moved."""

    id = fields.IntField(primary_key=True)
    path = fields.CharField(max_length=1024, unique=True)
    label = fields.CharField(max_length=128, default="")
    probe = fields.JSONField(null=True)
    fingerprint = fields.CharField(max_length=64, default="")  # size + mtime
    created_at = fields.DatetimeField(auto_now_add=True)
