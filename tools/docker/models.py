import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

import config


class StackInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    project: str = Field(
        ...,
        description="Docker Compose project name (alphanumeric, dash, underscore, dot only). "
                    "Must match an existing directory under COMPOSE_BASE_DIR.",
        min_length=1,
        max_length=64,
    )

    @field_validator("project")
    @classmethod
    def validate_project(cls, v: str) -> str:
        if not re.fullmatch(r'[a-zA-Z0-9_\-\.]+', v):
            raise ValueError("project name contains invalid characters")
        return v


class StackServiceInput(StackInput):
    service: Optional[str] = Field(
        default=None,
        description="Specific service name within the compose project. "
                    "Leave empty to target all services.",
        max_length=64,
    )

    @field_validator("service")
    @classmethod
    def validate_service(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.fullmatch(r'[a-zA-Z0-9_\-\.]+', v):
            raise ValueError("service name contains invalid characters")
        return v


class StackLogsInput(StackServiceInput):
    tail: int = Field(
        default=100,
        description=f"Number of log lines to return (max {config.LOG_MAX_LINES}).",
        ge=1,
        le=500,
    )


class StackDownInput(StackInput):
    remove_volumes: bool = Field(
        default=False,
        description="If true, also remove named volumes declared in the compose file. "
                    "WARNING: this is destructive and irreversible.",
    )


class ContainerListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    all_containers: bool = Field(
        default=False,
        description="If true, include stopped containers as well.",
    )


class ContainerInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    container: str = Field(
        ...,
        description="Container name or ID (alphanumeric, dash, underscore, dot only).",
        min_length=1,
        max_length=128,
    )

    @field_validator("container")
    @classmethod
    def validate_container(cls, v: str) -> str:
        if not re.fullmatch(r'[a-zA-Z0-9_\-\.]+', v):
            raise ValueError("container name contains invalid characters")
        return v


class ExecInput(ContainerInput):
    command: list[str] = Field(
        ...,
        description="Command to execute inside the container as a list of tokens. "
                    "Example: ['cat', '/etc/os-release']. No shell expansion is performed.",
        min_length=1,
        max_length=20,
    )
