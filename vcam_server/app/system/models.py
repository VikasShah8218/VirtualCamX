from tortoise import fields
from tortoise.models import Model


class SystemSetting(Model):
    key = fields.CharField(max_length=64, primary_key=True)
    value = fields.JSONField()
