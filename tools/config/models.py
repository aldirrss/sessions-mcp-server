from typing import Optional
from pydantic import BaseModel, Field


class ConfigWriteInput(BaseModel):
    key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Config key (e.g. 'claude_project_instructions', 'default_session_tags').",
    )
    value: str = Field(..., description="Config value to store.")
    description: str = Field(
        "",
        description="Human-readable explanation of what this config key controls.",
    )


class ConfigReadInput(BaseModel):
    key: str = Field(..., description="Config key to read.")


class ConfigDeleteInput(BaseModel):
    key: str = Field(..., description="Config key to delete.")


class ConfigListInput(BaseModel):
    prefix: Optional[str] = Field(
        None,
        description="Optional prefix to filter keys (e.g. 'claude_' returns all claude_* keys).",
    )
