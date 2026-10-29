"""Public API contracts for the application foundation."""

from typing import Literal

from pydantic import BaseModel, Field

from vmsim import IMPLEMENTATION_PHASE


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    application: Literal["vmsim"] = "vmsim"
    version: str
    phase: int = Field(default=IMPLEMENTATION_PHASE, ge=0, le=7)
    frontend_ready: bool

