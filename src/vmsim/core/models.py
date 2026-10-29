"""Immutable domain records. Sizes and addresses are expressed in bytes."""

from dataclasses import dataclass

from vmsim.core.validation import ValidationError, require_int


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    page_size: int = 4096
    virtual_pages: int = 8
    physical_frames: int = 3

    def __post_init__(self):
        require_int(self.page_size, "page_size", 256, 65536)
        if self.page_size & (self.page_size - 1):
            raise ValidationError("Page size must be a power of two.", "page_size")
        require_int(self.virtual_pages, "virtual_pages", 1, 256)
        require_int(self.physical_frames, "physical_frames", 1, 32)

    @property
    def virtual_capacity(self) -> int:
        return self.virtual_pages * self.page_size

    @property
    def physical_capacity(self) -> int:
        return self.physical_frames * self.page_size

    @property
    def offset_bits(self) -> int:
        return self.page_size.bit_length() - 1


@dataclass(frozen=True, slots=True)
class Access:
    input_value: int
    virtual_address: int
    page: int
    offset: int


@dataclass(frozen=True, slots=True)
class Frame:
    frame_id: int
    page: int | None = None


@dataclass(frozen=True, slots=True)
class PageTableEntry:
    page: int
    frame_id: int | None

    @property
    def resident(self) -> bool:
        return self.frame_id is not None


@dataclass(frozen=True, slots=True)
class Metrics:
    hits: int = 0
    faults: int = 0
    replacements: int = 0

    @property
    def references(self) -> int:
        return self.hits + self.faults

    @property
    def hit_rate(self) -> float | None:
        return self.hits / self.references if self.references else None

    @property
    def fault_rate(self) -> float | None:
        return self.faults / self.references if self.references else None


@dataclass(frozen=True, slots=True)
class PolicyState:
    name: str
    order: tuple[int, ...] = ()
    last_access: tuple[tuple[int, int], ...] = ()
    next_use: tuple[tuple[int, int | None], ...] = ()


@dataclass(frozen=True, slots=True)
class Snapshot:
    step: int
    frames: tuple[Frame, ...]
    metrics: Metrics
    policy_state: PolicyState | None = None

    @property
    def resident_pages(self) -> tuple[PageTableEntry, ...]:
        return tuple(sorted(
            (PageTableEntry(frame.page, frame.frame_id) for frame in self.frames if frame.page is not None),
            key=lambda entry: entry.page,
        ))


@dataclass(frozen=True, slots=True)
class Event:
    step: int
    access: Access
    result: str
    frame_id: int
    physical_address: int
    victim_page: int | None
    reason: str
    state: Snapshot


@dataclass(frozen=True, slots=True)
class SimulationResult:
    config: MemoryConfig
    input_mode: str
    policy: str | None
    accesses: tuple[Access, ...]
    initial_state: Snapshot
    events: tuple[Event, ...]
    metrics: Metrics
