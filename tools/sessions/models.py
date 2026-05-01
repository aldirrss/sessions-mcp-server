import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

_SESSION_ID_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,100}$')


def _validate_session_id(v: str) -> str:
    if not _SESSION_ID_RE.match(v):
        raise ValueError(
            f"Invalid session_id '{v}'. "
            "Use only letters, digits, hyphens, underscores (max 100 chars)."
        )
    return v


class SessionWriteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    session_id: str = Field(
        ...,
        description="Unique session identifier (letters, digits, hyphens, underscores). "
                    "Example: 'feat-auth-dev', 'odoo-refactor-2026'.",
        min_length=1,
        max_length=100,
    )
    title: str = Field(
        ...,
        description="Short human-readable title for the session.",
        min_length=1,
        max_length=200,
    )
    context: str = Field(
        ...,
        description="Full context to store: current state, goals, decisions, next steps. "
                    "This is the main body that will be read when resuming the session.",
        min_length=1,
    )
    source: str = Field(
        default="unknown",
        description="Origin client: 'web', 'cli', 'vscode', or any identifier.",
        max_length=50,
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="Optional list of tags for filtering (e.g. ['odoo', 'backend']).",
    )

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_session_id(v)


class SessionReadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    session_id: str = Field(..., description="Session ID to read.", min_length=1, max_length=100)

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_session_id(v)


class SessionAppendInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    session_id: str = Field(
        ..., description="Session ID to append the note to.", min_length=1, max_length=100
    )
    content: str = Field(
        ..., description="Note content to append (progress update, decision, blocker, etc.).",
        min_length=1,
    )
    source: str = Field(
        default="unknown",
        description="Origin client: 'web', 'cli', 'vscode'.",
        max_length=50,
    )

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_session_id(v)


class SessionDeleteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    session_id: str = Field(..., description="Session ID to delete.", min_length=1, max_length=100)

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_session_id(v)


class SessionListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tag: Optional[str] = Field(default=None, description="Filter sessions by tag. Omit to list all.")
    show_archived: bool = Field(
        default=False,
        description="Include archived sessions in results (default false).",
    )


class SessionSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(
        ..., description="Keyword to search across title, context, notes, and tags.",
        min_length=1,
    )


class NotePinInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_id: int = Field(..., description="ID of the note to pin.", ge=1)
    session_id: str = Field(..., description="Session ID the note belongs to.", min_length=1, max_length=100)

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_session_id(v)


class NoteUnpinInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_id: int = Field(..., description="ID of the note to unpin.", ge=1)
    session_id: str = Field(..., description="Session ID the note belongs to.", min_length=1, max_length=100)

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_session_id(v)


class SessionCompactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(..., description="Session ID to compact.", min_length=1, max_length=100)
    before_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description=(
            "Compact unpinned notes older than this many days into the context field "
            "and delete them. Pinned notes are never compacted. Default: 30 days."
        ),
    )

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_session_id(v)


class SessionPinInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(..., description="Session ID to pin.", min_length=1, max_length=100)

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_session_id(v)


class SessionArchiveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(..., description="Session ID to archive or restore.", min_length=1, max_length=100)

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_session_id(v)
