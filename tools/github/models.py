from pydantic import BaseModel, Field


class SessionLinkRepoInput(BaseModel):
    session_id: str = Field(..., description="Session ID to link the repository to.")
    repo_url: str = Field(
        ...,
        description="GitHub repository URL (e.g. https://github.com/owner/repo).",
    )


class SessionUnlinkRepoInput(BaseModel):
    session_id: str = Field(..., description="Session ID to unlink the repository from.")


class RepoGetContextInput(BaseModel):
    session_id: str = Field(
        ...,
        description="Session ID whose linked repository will be queried.",
    )
    include_prs: bool = Field(
        True,
        description="Whether to include open pull requests (default true).",
    )
    commit_limit: int = Field(
        10,
        ge=1,
        le=30,
        description="Number of recent commits to fetch (1–30, default 10).",
    )
