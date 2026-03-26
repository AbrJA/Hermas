"""Skill service: DB-backed CRUD, filesystem seed, markdown upload, caching."""

from __future__ import annotations

import re
import time
from pathlib import Path

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from solomon.models.skill import Skill

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# In-memory cache (list of lightweight dicts)
# ---------------------------------------------------------------------------

_cache: list[dict] | None = None
_cache_ts: float = 0.0
_CACHE_TTL = 30.0  # seconds


def invalidate_cache() -> None:
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0.0


# ---------------------------------------------------------------------------
# Frontmatter parser (ported from Julia SkillLoader.jl)
# ---------------------------------------------------------------------------


def parse_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    lines = markdown.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, markdown

    frontmatter: dict[str, str] = {}
    body_start = 0
    for i in range(1, len(lines)):
        line = lines[i]
        if line.strip() == "---":
            body_start = i + 1
            break
        if ":" in line:
            parts = line.split(":", 1)
            key = parts[0].strip().lower()
            value = parts[1].strip().strip("\"'")
            frontmatter[key] = value

    if body_start == 0:
        return {}, markdown

    body = "\n".join(lines[body_start:])
    return frontmatter, body


def _normalize_skill_id(name: str) -> str:
    lowered = name.strip().lower()
    replaced = re.sub(r"[^a-z0-9]+", "-", lowered)
    return replaced.strip("-")


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------


async def list_skills(db: AsyncSession, user_id: str = "__global__") -> list[dict]:
    global _cache, _cache_ts
    if _cache is not None and (time.monotonic() - _cache_ts) < _CACHE_TTL:
        return _cache

    result = await db.execute(
        select(Skill)
        .where(Skill.user_id.in_([user_id, "__global__"]))
        .order_by(Skill.name)
    )
    skills = [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "updatedAt": s.updated_at.strftime("%Y-%m-%dT%H:%M:%S") if s.updated_at else "",
        }
        for s in result.scalars()
    ]
    _cache = skills
    _cache_ts = time.monotonic()
    return skills


async def get_skill(db: AsyncSession, skill_id: str) -> dict | None:
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    s = result.scalar_one_or_none()
    if s is None:
        return None
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "content": s.content,
        "updatedAt": s.updated_at.strftime("%Y-%m-%dT%H:%M:%S") if s.updated_at else "",
    }


async def get_skill_orm(db: AsyncSession, skill_id: str) -> Skill | None:
    """Return raw ORM object for routing service."""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    return result.scalar_one_or_none()


async def create_skill(
    db: AsyncSession,
    *,
    skill_id: str = "",
    name: str,
    description: str = "No description provided",
    content: str,
    user_id: str = "__global__",
) -> dict:
    if not skill_id:
        skill_id = _normalize_skill_id(name)

    existing = await db.execute(select(Skill).where(Skill.id == skill_id))
    if existing.scalar_one_or_none() is not None:
        # Update in place
        return await update_skill(db, skill_id=skill_id, name=name, description=description, content=content)

    skill = Skill(id=skill_id, user_id=user_id, name=name, description=description, content=content)
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    invalidate_cache()

    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "content": skill.content,
        "updatedAt": skill.updated_at.strftime("%Y-%m-%dT%H:%M:%S") if skill.updated_at else "",
    }


async def update_skill(
    db: AsyncSession,
    *,
    skill_id: str,
    name: str | None = None,
    description: str | None = None,
    content: str | None = None,
) -> dict:
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if skill is None:
        raise ValueError(f"Skill '{skill_id}' not found")

    if name is not None:
        skill.name = name
    if description is not None:
        skill.description = description
    if content is not None:
        skill.content = content

    await db.commit()
    await db.refresh(skill)
    invalidate_cache()

    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "content": skill.content,
        "updatedAt": skill.updated_at.strftime("%Y-%m-%dT%H:%M:%S") if skill.updated_at else "",
    }


async def delete_skill(db: AsyncSession, skill_id: str) -> bool:
    result = await db.execute(delete(Skill).where(Skill.id == skill_id))
    await db.commit()
    invalidate_cache()
    return (result.rowcount or 0) > 0


async def upload_skill_md(db: AsyncSession, markdown: str, user_id: str = "__global__") -> dict:
    """Parse a SKILL.md file and upsert into DB."""
    frontmatter, body = parse_frontmatter(markdown)
    name = frontmatter.get("name", "Uploaded Skill")
    description = frontmatter.get("description", "No description provided")
    skill_id = frontmatter.get("id", _normalize_skill_id(name))

    return await create_skill(
        db,
        skill_id=skill_id,
        name=name,
        description=description,
        content=body.strip(),
        user_id=user_id,
    )


# ---------------------------------------------------------------------------
# Filesystem seeding – import existing skills/*/SKILL.md on first boot
# ---------------------------------------------------------------------------


async def seed_from_directory(db: AsyncSession, skills_dir: str) -> int:
    """Import skills from filesystem into DB. Returns number imported."""
    skills_path = Path(skills_dir)
    if not skills_path.is_dir():
        return 0

    count = 0
    for entry in sorted(skills_path.iterdir()):
        if not entry.is_dir():
            continue
        skill_file = entry / "SKILL.md"
        if not skill_file.is_file():
            continue

        raw = skill_file.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(raw)
        name = frontmatter.get("name", entry.name)
        description = frontmatter.get("description", "No description provided")
        skill_id = frontmatter.get("id", _normalize_skill_id(name))

        # Only seed if not already in DB
        existing = await db.execute(select(Skill).where(Skill.id == skill_id))
        if existing.scalar_one_or_none() is not None:
            continue

        db.add(
            Skill(
                id=skill_id,
                name=name,
                description=description,
                content=body.strip(),
                user_id="__global__",
            )
        )
        count += 1
        logger.info("skill_seeded", skill_id=skill_id, name=name)

    if count > 0:
        await db.commit()
    invalidate_cache()
    return count
