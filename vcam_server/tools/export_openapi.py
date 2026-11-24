"""Export the OpenAPI specs for the web client:  py tools/export_openapi.py

Writes ../vcam_client/openapi/manager.json (Manager API) and camera.json (camera web API).
Then in vcam_client:  npm run gen:api
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from app.camera_api.app import build_camera_app  # noqa: E402
from main import build_app  # noqa: E402

out_dir = os.path.join(os.path.dirname(os.path.dirname(HERE)), "vcam_client", "openapi")
os.makedirs(out_dir, exist_ok=True)
for name, app in (("manager", build_app()), ("camera", build_camera_app())):
    path = os.path.join(out_dir, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(app.openapi(), f, indent=1)
    print(f"wrote {path} ({len(app.openapi()['paths'])} paths)")
