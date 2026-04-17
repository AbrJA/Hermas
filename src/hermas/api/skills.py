"""Skill endpoints – list, get, create (upload .md), delete."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from hermas.api.dependencies import get_app_config, get_db, require_session
from hermas.config import AppConfig
from hermas.schemas.skill import SkillCreateRequest
from hermas.services import skill_service

router = APIRouter(prefix="/api", tags=["skills"])


@router.get("/skills")
async def list_skills(
    cfg: Annotated[AppConfig, Depends(get_app_config)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[str, Depends(require_session)],
):
    skills = await skill_service.list_skills(db, user_id=user_id)
    return {"skills": [{"id": s["id"], "name": s["name"], "description": s["description"], "updatedAt": s["updatedAt"]} for s in skills]}


@router.get("/skills/{skill_id}")
async def get_skill(
    skill_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[str, Depends(require_session)],
):
    skill = await skill_service.get_skill(db, skill_id, user_id=user_id)
    if skill is None:
        raise HTTPException(404, detail="Skill not found")
    return {
        "id": skill["id"],
        "name": skill["name"],
        "description": skill["description"],
        "systemPrompt": skill["content"],
    }


@router.post("/skills")
async def create_skill(
    body: SkillCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[str, Depends(require_session)],
):
    result = await skill_service.create_skill(
        db,
        skill_id=body.id,
        name=body.name,
        description=body.description,
        content=body.content,
        user_id=user_id,
    )
    return {"skill": result}


@router.post("/skills/upload")
async def upload_skill(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_session),
):
    if not file.filename or not file.filename.endswith(".md"):
        raise HTTPException(400, detail="Only .md files are accepted")
    raw = await file.read()
    markdown = raw.decode("utf-8")
    result = await skill_service.upload_skill_md(db, markdown, user_id=user_id)
    return {"skill": result}


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[str, Depends(require_session)],
):
    deleted = await skill_service.delete_skill(db, skill_id, user_id=user_id)
    if not deleted:
        raise HTTPException(404, detail="Skill not found")
    return {"deleted": True}
