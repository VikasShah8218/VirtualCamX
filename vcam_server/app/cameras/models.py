from tortoise import fields
from tortoise.models import Model


class Camera(Model):
    id = fields.IntField(primary_key=True)
    number = fields.IntField(unique=True)  # 1 -> "cam001" (RTSP path prefix)
    name = fields.CharField(max_length=128, unique=True)
    enabled = fields.BooleanField(default=True)
    template_key = fields.CharField(max_length=64)
    addr_mode = fields.CharField(max_length=8, default="port")  # port | ip
    ip = fields.CharField(max_length=64, null=True)  # IP Mode only
    http_port = fields.IntField()
    state = fields.JSONField()  # CameraState document
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


class CameraUser(Model):
    id = fields.IntField(primary_key=True)
    camera = fields.ForeignKeyField("models.Camera", related_name="users", on_delete=fields.CASCADE)
    username = fields.CharField(max_length=64)
    # Encrypted, not hashed: WS-Security / HTTP Digest need the plain password (see utilities/crypto.py)
    password_enc = fields.TextField()
    level = fields.CharField(max_length=16, default="Administrator")  # Administrator | Operator | User

    class Meta:
        unique_together = (("camera", "username"),)
