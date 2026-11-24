from settings.settings import settings

MODEL_MODULES = [
    "app.auth.models",
    "app.cameras.models",
    "app.templates.models",
    "app.media_library.models",
    "app.events.models",
    "app.faults.models",
    "app.system.models",
]

TORTOISE_ORM = {
    "connections": {"default": f"sqlite://{(settings.data_dir / 'vcam.db').as_posix()}"},
    "apps": {"models": {"models": MODEL_MODULES, "default_connection": "default"}},
    "use_tz": True,
    "timezone": "UTC",
}
