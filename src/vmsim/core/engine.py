"""One authoritative reference-processing path; initially free-frame loads only."""

from collections.abc import Sequence

from vmsim.core.models import Event, Frame, MemoryConfig, Metrics, PageTableEntry, SimulationResult, Snapshot
from vmsim.core.translation import normalize_and_validate, physical_address
from vmsim.core.validation import require_int


class MemoryFullError(RuntimeError):
    """A replacement policy is required when no frame is free."""


class Memory:
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.frames: list[int | None] = [None] * config.physical_frames
        self.mapping: dict[int, int] = {}
        self.metrics = Metrics()

    def snapshot(self) -> Snapshot:
        return Snapshot(self.metrics.references, tuple(Frame(i, page) for i, page in enumerate(self.frames)), self.metrics)

    @property
    def page_table(self) -> tuple[PageTableEntry, ...]:
        return tuple(PageTableEntry(page, self.mapping.get(page)) for page in range(self.config.virtual_pages))

    def resolve(self, page: int) -> tuple[int, bool]:
        require_int(page, "page", 0, self.config.virtual_pages - 1)
        if page in self.mapping:
            self.metrics = Metrics(self.metrics.hits + 1, self.metrics.faults)
            return self.mapping[page], True
        try:
            frame = self.frames.index(None)
        except ValueError:
            raise MemoryFullError("All frames are occupied; replacement is not implemented in Phase 1.") from None
        self.frames[frame] = page
        self.mapping[page] = frame
        self.metrics = Metrics(self.metrics.hits, self.metrics.faults + 1)
        return frame, False


def simulate(config: MemoryConfig, workload: str | Sequence[int], input_mode: str = "pages") -> SimulationResult:
    accesses = normalize_and_validate(config, workload, input_mode)
    memory = Memory(config)
    initial = memory.snapshot()
    events = []
    for access in accesses:
        frame, hit = memory.resolve(access.page)
        state = memory.snapshot()
        events.append(Event(state.step, access, "hit" if hit else "fault", frame,
                            physical_address(config, frame, access.offset), None,
                            "Page is already resident." if hit else f"Loaded page into free frame {frame}.", state))
    return SimulationResult(config, input_mode, None, accesses, initial, tuple(events), memory.metrics)
