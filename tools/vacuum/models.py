from pydantic import BaseModel, Field


class VacuumRunInput(BaseModel):
    dry_run: bool = Field(
        default=False,
        description=(
            "If true, preview what WOULD be deleted without making any changes. "
            "Use this to verify vacuum settings before running for real."
        ),
    )
