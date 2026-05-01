import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

_SLUG_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,100}$')


def _validate_slug(v: str) -> str:
    if not _SLUG_RE.match(v):
        raise ValueError(
            f"Invalid slug '{v}'. Use only letters, digits, hyphens, underscores (max 100 chars)."
        )
    return v


class SkillWriteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    slug: str = Field(
        ...,
        description="Unique skill identifier (letters, digits, hyphens, underscores). "
                    "Example: 'mcp-builder', 'brainstorming', 'docker'.",
        min_length=1,
        max_length=100,
    )
    name: str = Field(
        ...,
        description="Human-readable skill name. Example: 'MCP Builder', 'Brainstorming'.",
        min_length=1,
        max_length=200,
    )
    content: str = Field(
        ...,
        description="Full skill content in Markdown. This is the complete skill definition.",
        min_length=1,
    )
    summary: str = Field(
        default="",
        description="One or two sentence description of what this skill does. "
                    "Used in skill_list and skill_search results. Auto-generate if empty.",
        max_length=500,
    )
    source: str = Field(
        default="manual",
        description="Origin of this skill: 'file' (imported from disk) or 'manual' (created via tool).",
        max_length=50,
    )
    category: Optional[str] = Field(
        default=None,
        description="Skill category for grouping. Example: 'development', 'design', 'devops'.",
        max_length=100,
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="Tags for filtering and recommendation. Example: ['python', 'mcp', 'docker'].",
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        return _validate_slug(v)


class SkillReadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    slug: str = Field(..., description="Skill slug to read.", min_length=1, max_length=100)
    session_id: Optional[str] = Field(
        default=None,
        description="Active session ID. When provided, auto-records skill use in session_skills.",
        max_length=100,
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        return _validate_slug(v)


class SkillDeleteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    slug: str = Field(..., description="Skill slug to delete.", min_length=1, max_length=100)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        return _validate_slug(v)


class SkillListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Optional[str] = Field(default=None, description="Filter by category.")
    tag: Optional[str] = Field(default=None, description="Filter by tag.")
    source: Optional[str] = Field(default=None, description="Filter by source: 'file' or 'manual'.")


class SkillSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(
        ...,
        description="Keyword to search across skill name, summary, content, and tags.",
        min_length=1,
    )


class SkillSyncInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skills: list[dict] = Field(
        ...,
        description="List of skill dicts to bulk-import. Each must have: slug, name, content. "
                    "Optional: summary, category, tags.",
        min_length=1,
    )


class SkillTrackInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    session_id: str = Field(
        ...,
        description="Session ID to associate the skill with.",
        min_length=1,
        max_length=100,
    )
    skill_slug: str = Field(
        ...,
        description="Slug of the skill that was invoked.",
        min_length=1,
        max_length=100,
    )

    @field_validator("skill_slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        return _validate_slug(v)


class SessionSkillsListInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    session_id: str = Field(..., description="Session ID to list skills for.", min_length=1, max_length=100)


class SkillSessionsListInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    slug: str = Field(..., description="Skill slug to find sessions for.", min_length=1, max_length=100)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        return _validate_slug(v)


class SkillRecommendInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    session_id: str = Field(..., description="Session ID to base recommendations on.", min_length=1, max_length=100)
    limit: int = Field(default=5, description="Maximum number of recommendations to return.", ge=1, le=20)
