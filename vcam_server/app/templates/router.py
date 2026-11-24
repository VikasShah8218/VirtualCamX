from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.auth.deps import AdminDep
from app.templates.builtin import BUILTIN_TEMPLATES
from app.templates.models import CameraTemplate
from app.system.responses import TemplateOut
from app.cameras.responses import OkOut

router = APIRouter(prefix="/api/v1/templates", tags=["templates"], dependencies=[AdminDep])

REQUIRED = {"name", "model", "native", "main_res", "main", "sub", "ptz", "inputs", "relays"}


class TemplateIn(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]{2,64}$")
    definition: dict


def _summary(key: str, d: dict, builtin: bool) -> dict:
    return {"key": key, "builtin": builtin, **d}


@router.get("", response_model=list[TemplateOut])
async def list_templates():
    out = [_summary(k, v, True) for k, v in BUILTIN_TEMPLATES.items()]
    out += [_summary(t.key, t.definition, False) for t in await CameraTemplate.all()]
    return out


@router.post("", status_code=201, response_model=OkOut)
async def create_template(body: TemplateIn):
    if body.key in BUILTIN_TEMPLATES or await CameraTemplate.exists(key=body.key):
        raise HTTPException(409, "Template key already exists")
    missing = REQUIRED - set(body.definition)
    if missing:
        raise HTTPException(422, f"Missing fields: {sorted(missing)}")
    await CameraTemplate.create(key=body.key, name=body.definition["name"], definition=body.definition)
    return {"ok": True}


@router.post("/{key}/clone", status_code=201, response_model=OkOut)
async def clone_template(key: str, new_key: str):
    src = BUILTIN_TEMPLATES.get(key)
    if src is None:
        t = await CameraTemplate.get_or_none(key=key)
        src = t.definition if t else None
    if src is None:
        raise HTTPException(404, "Template not found")
    if new_key in BUILTIN_TEMPLATES or await CameraTemplate.exists(key=new_key):
        raise HTTPException(409, "Template key already exists")
    d = {**src, "name": f"{src['name']} (copy)"}
    await CameraTemplate.create(key=new_key, name=d["name"], definition=d)
    return {"ok": True}


@router.delete("/{key}", response_model=OkOut)
async def delete_template(key: str):
    if key in BUILTIN_TEMPLATES:
        raise HTTPException(400, "Built-in templates cannot be deleted")
    await CameraTemplate.filter(key=key).delete()
    return {"ok": True}
