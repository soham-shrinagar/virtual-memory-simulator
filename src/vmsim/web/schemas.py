"""Strict request and response contracts for the local API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt
from vmsim.core.policies import POLICIES

PolicyName = Literal['fifo', 'lru', 'optimal', 'clock']
Operation = Literal['read', 'write']


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
    policy: PolicyName = "fifo"
    tlb_capacity: int = Field(default=0, ge=0, le=32)
    operations: list[Operation] | None = None


class ExperimentRequest(SimulationRequest):
    schema_version: int = Field(ge=1, le=3)


class CompareRequest(StrictModel):
    config: ConfigRequest = Field(default_factory=ConfigRequest)
    workload: str | list[StrictInt]
    input_mode: Literal["pages", "addresses"] = "pages"
    tlb_capacity: int = Field(default=0, ge=0, le=32)
    operations: list[Operation] | None = None
    policies: list[PolicyName] = Field(default_factory=lambda: list(POLICIES), min_length=1, max_length=len(POLICIES))
    frame_counts: list[StrictInt] | None = Field(default=None, min_length=1, max_length=32)


class WorkloadRequest(StrictModel):
    config: ConfigRequest = Field(default_factory=ConfigRequest)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    length: int = Field(default=100, ge=1, le=1000)
    profile: Literal['uniform', 'sequential', 'locality'] = 'locality'
    input_mode: Literal['pages', 'addresses'] = 'pages'


class ConfigResponse(ConfigRequest):
    virtual_capacity: int
    physical_capacity: int
    offset_bits: int


class MetricsResponse(StrictModel):
    references: int
    hits: int
    faults: int
    replacements: int
    reads: int
    writes: int
    writebacks: int
    hit_rate: float | None
    fault_rate: float | None


class FrameResponse(StrictModel):
    frame_id: int
    page: int | None
    dirty: bool


class ResidentResponse(StrictModel):
    page: int
    frame_id: int


class PolicyPosition(StrictModel):
    frame_id: int
    step: int | None


class ReferenceBit(StrictModel):
    frame_id: int
    referenced: bool


class PolicyResponse(StrictModel):
    name: PolicyName
    order: list[int]
    last_access: list[PolicyPosition]
    next_use: list[PolicyPosition]
    hand: int | None
    reference_bits: list[ReferenceBit]


class TLBResponse(StrictModel):
    capacity: int
    hits: int
    misses: int
    entries: list[ResidentResponse]


class SnapshotResponse(StrictModel):
    step: int
    frames: list[FrameResponse]
    resident_pages: list[ResidentResponse]
    metrics: MetricsResponse
    policy_state: PolicyResponse
    tlb: TLBResponse | None


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
    tlb_result: Literal['hit', 'miss'] | None
    operation: Operation
    writeback: bool


class SimulationResponse(StrictModel):
    schema_version: int
    config: ConfigResponse
    input_mode: Literal["pages", "addresses"]
    policy: PolicyName
    workload: list[int]
    operations: list[Operation]
    initial_state: SnapshotResponse
    events: list[EventResponse]
    metrics: MetricsResponse
    tlb_capacity: int
    tlb: TLBResponse | None


class ComparisonRowResponse(StrictModel):
    policy: PolicyName
    physical_frames: int
    metrics: MetricsResponse
    tlb: TLBResponse | None


class ComparisonResponse(StrictModel):
    schema_version: int
    config: ConfigResponse
    input_mode: Literal["pages", "addresses"]
    workload: list[int]
    operations: list[Operation]
    policies: list[str]
    frame_counts: list[int]
    rows: list[ComparisonRowResponse]
    tlb_capacity: int

