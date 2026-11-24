from tortoise import fields
from tortoise.models import Model


class EventLog(Model):
    id = fields.IntField(primary_key=True)
    camera_id = fields.IntField(db_index=True)
    topic = fields.CharField(max_length=128)
    operation = fields.CharField(max_length=16, default="Changed")
    source = fields.JSONField()
    data = fields.JSONField()
    origin = fields.CharField(max_length=64, default="simulator")  # simulator | fault | onvif | io | api
    utc_time = fields.DatetimeField(db_index=True)


class EventSchedule(Model):
    id = fields.IntField(primary_key=True)
    camera_id = fields.IntField(db_index=True)
    kind = fields.CharField(max_length=32)  # motion | tamper | digital_input | video_loss
    token = fields.CharField(max_length=64, null=True)  # input token for digital_input
    mode = fields.CharField(max_length=16, default="periodic")  # periodic | random
    interval_s = fields.FloatField(default=60)
    interval_max_s = fields.FloatField(default=120)  # random mode upper bound
    active_s = fields.FloatField(default=10)
    enabled = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
