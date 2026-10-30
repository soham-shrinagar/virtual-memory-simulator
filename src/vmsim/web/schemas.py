"""Strict request and response contracts for the local API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    application: Literal["vmsim"] = "vmsim"
    version: str
    frontend_ready: bool


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ConfigRequest(StrictModel):
    page_size: int = Field(default=4096, ge=256, le=65536)
    virtual_pages: int = Field(default=8, ge=1, le=256)
    physical_frames: int = Field(default=3, ge=1, le=32)


class SimulationRequest(StrictModel):
    config: ConfigRequest = Field(default_factory=ConfigRequest)
    workload: str | list[StrictInt]
    input_mode: Literal["pages", "addresses"] = "pages"
    policy: Literal["fifo", "lru", "optimal"] = "fifo"


class ExperimentRequest(SimulationRequest):
    schema_version: int = Field(ge=1, le=1)

    @model_validator(mode="before")
    @classmethod
    def require_complete_file(cls, data):
        fields = {"schema_version", "config", "workload", "input_mode", "policy"}
        if not isinstance(data, dict) or set(data) != fields:
            raise ValueError("An experiment file must include all five versioned fields.")
        config = data.get("config")
        if not isinstance(config, dict) or set(config) != {"page_size", "virtual_pages", "physical_frames"}:
            raise ValueError("An experiment file must include all memory configuration fields.")
        return data


class CompareRequest(StrictModel):
    config: ConfigRequest = Field(default_factory=ConfigRequest)
    workload: str | list[StrictInt]
    input_mode: Literal["pages", "addresses"] = "pages"
    policies: list[Literal["fifo", "lru", "optimal"]] = Field(default_factory=lambda: ["fifo", "lru", "optimal"], min_length=1, max_length=3)
    frame_counts: list[StrictInt] | None = Field(default=None, min_length=1, max_length=32)


class ConfigResponse(ConfigRequest):
    virtual_capacity: int
    physical_capacity: int
    offset_bits: int


class MetricsResponse(StrictModel):
    references: int
    hits: int
    faults: int
    replacements: int
    hit_rate: float | None
    fault_rate: float | None


class FrameResponse(StrictModel):
    frame_id: int
    page: int | None


class ResidentResponse(StrictModel):
    page: int
    frame_id: int


class PolicyPosition(StrictModel):
    frame_id: int
    step: int | None


class PolicyResponse(StrictModel):
    name: Literal["fifo", "lru", "optimal"]
    order: list[int]
    last_access: list[PolicyPosition]
    next_use: list[PolicyPosition]


class SnapshotResponse(StrictModel):
    step: int
    frames: list[FrameResponse]
    resident_pages: list[ResidentResponse]
    metrics: MetricsResponse
    policy_state: PolicyResponse


class EventResponse(StrictModel):
    step: int
    input_value: int
    virtual_address: int
    page: int
    offset: int
    result: Literal["hit", "fault"]
    frame_id: int
    physical_address: int
    victim_page: int | None
    reason: str
    state: SnapshotResponse


class SimulationResponse(StrictModel):
    schema_version: int
    config: ConfigResponse
    input_mode: Literal["pages", "addresses"]
    policy: Literal["fifo", "lru", "optimal"]
    workload: list[int]
    initial_state: SnapshotResponse
    events: list[EventResponse]
    metrics: MetricsResponse


class ComparisonRowResponse(StrictModel):
    policy: Literal["fifo", "lru", "optimal"]
    physical_frames: int
    metrics: MetricsResponse


class ComparisonResponse(StrictModel):
    schema_version: int
    config: ConfigResponse
    input_mode: Literal["pages", "addresses"]
    workload: list[int]
    policies: list[str]
    frame_counts: list[int]
    rows: list[ComparisonRowResponse]

