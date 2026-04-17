"""Skill service: DB-backed CRUD, filesystem seed, markdown upload, caching."""

from __future__ import annotations

import re
import time
from pathlib import Path

import structlog
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hermas.models.skill import Skill

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# In-memory cache (list of lightweight dicts)
# ---------------------------------------------------------------------------

_cache: dict[str, list[dict]] = {}
_cache_ts: dict[str, float] = {}
_CACHE_TTL = 30.0  # seconds


def invalidate_cache() -> None:
    global _cache, _cache_ts
    _cache = {}
    _cache_ts = {}


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


async def _next_available_skill_id(db: AsyncSession, base_id: str) -> str:
    """Return a globally available skill id for legacy DBs with UNIQUE(skills.id)."""
    clean_base = base_id.strip() or "uploaded-skill"
    # Keep room for suffix and stay within VARCHAR(128)
    clean_base = clean_base[:110]

    result = await db.execute(select(Skill).where(Skill.id == clean_base))
    if result.scalar_one_or_none() is None:
        return clean_base

    for i in range(2, 1000):
        candidate = f"{clean_base}-{i}"
        result = await db.execute(select(Skill).where(Skill.id == candidate))
        if result.scalar_one_or_none() is None:
            return candidate

    raise ValueError("Could not allocate a unique skill id")


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------


async def list_skills(db: AsyncSession, user_id: str = "__global__") -> list[dict]:
    global _cache, _cache_ts
    cache_key = user_id.strip() or "anonymous"
    if cache_key in _cache and (time.monotonic() - _cache_ts.get(cache_key, 0.0)) < _CACHE_TTL:
        return _cache[cache_key]

    result = await db.execute(
        select(Skill)
        .where(Skill.user_id == cache_key)
        .order_by(Skill.name)
    )
    raw = [
        {
            "id": s.id,
            "userId": s.user_id,
            "name": s.name,
            "description": s.description,
            "updatedAt": s.updated_at.strftime("%Y-%m-%dT%H:%M:%S") if s.updated_at else "",
        }
        for s in result.scalars()
    ]

    skills = [
        {
            "id": s["id"],
            "name": s["name"],
            "description": s["description"],
            "updatedAt": s["updatedAt"],
        }
        for s in sorted(raw, key=lambda x: x["name"].lower())
    ]
    _cache[cache_key] = skills
    _cache_ts[cache_key] = time.monotonic()
    return skills


async def get_skill(db: AsyncSession, skill_id: str, user_id: str = "__global__") -> dict | None:
    owner = user_id.strip() or "anonymous"

    result = await db.execute(select(Skill).where(Skill.id == skill_id, Skill.user_id == owner))
    s = result.scalar_one_or_none()
    if s is None:
        return None

    return {
        "id": s.id,
        "userId": s.user_id,
        "name": s.name,
        "description": s.description,
        "content": s.content,
        "updatedAt": s.updated_at.strftime("%Y-%m-%dT%H:%M:%S") if s.updated_at else "",
    }


async def get_skill_orm(db: AsyncSession, skill_id: str, user_id: str = "__global__") -> Skill | None:
    """Return raw ORM object for routing service."""
    owner = user_id.strip() or "anonymous"
    result = await db.execute(select(Skill).where(Skill.id == skill_id, Skill.user_id == owner))
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
    owner = user_id.strip() or "anonymous"
    if not skill_id:
        skill_id = _normalize_skill_id(name)

    existing = await db.execute(select(Skill).where(Skill.id == skill_id, Skill.user_id == owner))
    if existing.scalar_one_or_none() is not None:
        # Update in place
        return await update_skill(
            db,
            skill_id=skill_id,
            user_id=owner,
            name=name,
            description=description,
            content=content,
        )

    skill = Skill(id=skill_id, user_id=owner, name=name, description=description, content=content)
    db.add(skill)
    try:
        await db.commit()
        await db.refresh(skill)
    except IntegrityError as exc:
        await db.rollback()

        # Legacy SQLite tables can still enforce UNIQUE(skills.id).
        # In that case, allocate a new globally unique id and retry once.
        if "skills.id" not in str(exc).lower():
            raise

        fallback_id = await _next_available_skill_id(db, skill_id)
        skill = Skill(id=fallback_id, user_id=owner, name=name, description=description, content=content)
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
    user_id: str,
    name: str | None = None,
    description: str | None = None,
    content: str | None = None,
) -> dict:
    owner = user_id.strip() or "anonymous"
    result = await db.execute(select(Skill).where(Skill.id == skill_id, Skill.user_id == owner))
    skill = result.scalar_one_or_none()
    if skill is None:
        raise ValueError(f"Skill '{skill_id}' not found for user '{owner}'")

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


async def delete_skill(db: AsyncSession, skill_id: str, user_id: str) -> bool:
    owner = user_id.strip() or "anonymous"
    result = await db.execute(delete(Skill).where(Skill.id == skill_id, Skill.user_id == owner))
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
