"""Public API contracts for the application foundation."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    application: Literal["vmsim"] = "vmsim"
    version: str
    phase: Literal[0] = 0
    frontend_ready: bool

