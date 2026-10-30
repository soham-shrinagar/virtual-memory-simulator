"""One authoritative reference-processing path shared by all policies."""

from collections.abc import Sequence

from vmsim.core.models import Event, Frame, MemoryConfig, Metrics, PageTableEntry, PolicyState, SimulationResult, Snapshot
from vmsim.core.policies import create_policy
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

    def snapshot(self, policy_state: PolicyState | None = None) -> Snapshot:
        return Snapshot(self.metrics.references, tuple(Frame(i, page) for i, page in enumerate(self.frames)), self.metrics, policy_state)

    @property
    def page_table(self) -> tuple[PageTableEntry, ...]:
        return tuple(PageTableEntry(page, self.mapping.get(page)) for page in range(self.config.virtual_pages))

    def resolve(self, page: int) -> tuple[int, bool]:
        require_int(page, "page", 0, self.config.virtual_pages - 1)
        if page in self.mapping:
            self.metrics = Metrics(self.metrics.hits + 1, self.metrics.faults, self.metrics.replacements)
            return self.mapping[page], True
        try:
            frame = self.frames.index(None)
        except ValueError:
            raise MemoryFullError("Select and evict a victim before loading into full memory.") from None
        self.frames[frame] = page
        self.mapping[page] = frame
        self.metrics = Metrics(self.metrics.hits, self.metrics.faults + 1, self.metrics.replacements)
        return frame, False

    def evict(self, frame: int) -> int:
        require_int(frame, "frame_id", 0, self.config.physical_frames - 1)
        page = self.frames[frame]
        if page is None:
            raise ValueError("Cannot evict an empty frame.")
        del self.mapping[page]
        self.frames[frame] = None
        self.metrics = Metrics(self.metrics.hits, self.metrics.faults, self.metrics.replacements + 1)
        return page

    def check_invariants(self) -> None:
        occupied = [page for page in self.frames if page is not None]
        assert len(occupied) == len(set(occupied)) == len(self.mapping)
        assert self.mapping == {page: frame for frame, page in enumerate(self.frames) if page is not None}
        assert self.metrics.faults - self.metrics.replacements == len(occupied)
        assert self.metrics.replacements <= self.metrics.faults


def simulate(
    config: MemoryConfig, workload: str | Sequence[int], input_mode: str = "pages",
    policy: str = "fifo", *, capture_trace: bool = True,
) -> SimulationResult:
    accesses = normalize_and_validate(config, workload, input_mode)
    return _simulate_validated(config, accesses, input_mode, policy, capture_trace=capture_trace)


def _simulate_validated(config, accesses, input_mode, policy, *, capture_trace):
    """Internal runner for immutable accesses already checked against this address space."""
    selection = create_policy(policy, accesses)
    memory = Memory(config)
    initial = memory.snapshot(selection.snapshot(memory.frames))
    events = []
    for index, access in enumerate(accesses):
        victim = None
        if access.page not in memory.mapping and None not in memory.frames:
            victim_frame, reason = selection.select_victim(memory.frames)
            victim = memory.evict(victim_frame)
            selection.on_evict(victim_frame)
        frame, hit = memory.resolve(access.page)
        if not hit:
            selection.on_load(frame, access.page, index)
        selection.on_access(frame, access.page, index)
        memory.check_invariants()
        if capture_trace:
            if hit:
                reason = "Page is already resident."
            elif victim is None:
                reason = f"Loaded page into free frame {frame}."
            state = memory.snapshot(selection.snapshot(memory.frames))
            events.append(Event(state.step, access, "hit" if hit else "fault", frame,
                                physical_address(config, frame, access.offset), victim,
                                reason, state))
    return SimulationResult(config, input_mode, policy, accesses, initial, tuple(events), memory.metrics)
