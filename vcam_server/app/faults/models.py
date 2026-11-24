from tortoise import fields
from tortoise.models import Model


class FaultRecord(Model):
    id = fields.IntField(primary_key=True)
    camera_id = fields.IntField(db_index=True)
    type = fields.CharField(max_length=32)
    params = fields.JSONField(default=dict)
    started_at = fields.DatetimeField()
    expires_at = fields.DatetimeField(null=True)
    active = fields.BooleanField(default=True)
