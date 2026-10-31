"""One authoritative reference-processing path shared by all policies."""

from collections.abc import Sequence

from vmsim.core.models import Event, Frame, MemoryConfig, Metrics, PageTableEntry, PolicyState, SimulationResult, Snapshot
from vmsim.core.policies import create_policy
from vmsim.core.tlb import TLB
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

    def snapshot(self, policy_state: PolicyState | None = None, tlb=None) -> Snapshot:
        return Snapshot(self.metrics.references, tuple(Frame(i, page) for i, page in enumerate(self.frames)), self.metrics, policy_state, tlb)

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
    policy: str = "fifo", *, capture_trace: bool = True, tlb_capacity: int = 0,
) -> SimulationResult:
    accesses = normalize_and_validate(config, workload, input_mode)
    return _simulate_validated(config, accesses, input_mode, policy, capture_trace=capture_trace, tlb_capacity=tlb_capacity)


def _simulate_validated(config, accesses, input_mode, policy, *, capture_trace, tlb_capacity=0):
    """Internal runner for immutable accesses already checked against this address space."""
    selection = create_policy(policy, accesses)
    memory = Memory(config)
    require_int(tlb_capacity, 'tlb_capacity', 0, 32)
    tlb = TLB(tlb_capacity) if tlb_capacity else None
    initial = memory.snapshot(selection.snapshot(memory.frames), tlb.snapshot() if tlb else None)
    events = []
    for index, access in enumerate(accesses):
        victim = None
        cached_frame = tlb.lookup(access.page) if tlb else None
        tlb_result = ('hit' if cached_frame is not None else 'miss') if tlb else None
        if cached_frame is not None:
            frame, hit = cached_frame, True
            memory.metrics = Metrics(memory.metrics.hits + 1, memory.metrics.faults, memory.metrics.replacements)
        else:
            if access.page not in memory.mapping and None not in memory.frames:
                victim_frame, reason = selection.select_victim(memory.frames)
                victim = memory.evict(victim_frame)
                if tlb:
                    tlb.invalidate(victim)
                selection.on_evict(victim_frame)
            frame, hit = memory.resolve(access.page)
        if not hit:
            selection.on_load(frame, access.page, index)
        selection.on_access(frame, access.page, index)
        memory.check_invariants()
        if tlb:
            if cached_frame is None:
                tlb.fill(access.page, frame)
            tlb.check_invariants(memory)
        if capture_trace:
            if hit:
                reason = "Page is already resident."
            elif victim is None:
                reason = f"Loaded page into free frame {frame}."
            state = memory.snapshot(selection.snapshot(memory.frames), tlb.snapshot() if tlb else None)
            events.append(Event(state.step, access, "hit" if hit else "fault", frame,
                                physical_address(config, frame, access.offset), victim,
                                reason, state, tlb_result))
    return SimulationResult(config, input_mode, policy, accesses, initial, tuple(events), memory.metrics, tlb.snapshot() if tlb else None)
