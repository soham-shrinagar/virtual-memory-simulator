"""Victim-selection policies. Memory ownership and counters stay in the engine."""

from collections import defaultdict, deque

from vmsim.core.models import Access, PolicyState
from vmsim.core.validation import ValidationError

POLICIES = ("fifo", "lru", "optimal")


class ReplacementPolicy:
    def on_load(self, frame: int, page: int, index: int) -> None:
        pass

    def on_evict(self, frame: int) -> None:
        pass

    def on_access(self, frame: int, page: int, index: int) -> None:
        pass


class FIFO(ReplacementPolicy):
    def __init__(self):
        self.order: deque[int] = deque()

    def on_load(self, frame, page, index):
        self.order.append(frame)

    def on_evict(self, frame):
        self.order.remove(frame)

    def select_victim(self, frames):
        frame = self.order[0]
        return frame, f"FIFO evicted page {frames[frame]} from frame {frame}: oldest resident arrival."

    def snapshot(self, frames):
        return PolicyState("fifo", order=tuple(self.order))


class LRU(ReplacementPolicy):
    def __init__(self):
        self.last_access: dict[int, int] = {}

    def on_access(self, frame, page, index):
        self.last_access[frame] = index + 1

    def on_evict(self, frame):
        del self.last_access[frame]

    def select_victim(self, frames):
        frame = min(self.last_access, key=lambda frame: (self.last_access[frame], frame))
        return frame, f"LRU evicted page {frames[frame]} from frame {frame}: last accessed at step {self.last_access[frame]}."

    def snapshot(self, frames):
        order = tuple(sorted(self.last_access, key=lambda frame: (self.last_access[frame], frame)))
        return PolicyState("lru", order=order, last_access=tuple(sorted(self.last_access.items())))


class Optimal(ReplacementPolicy):
    def __init__(self, accesses: tuple[Access, ...]):
        self.future: dict[int, deque[int]] = defaultdict(deque)
        for index, access in enumerate(accesses):
            self.future[access.page].append(index + 1)

    def on_access(self, frame, page, index):
        assert self.future[page][0] == index + 1
        self.future[page].popleft()

    def next_use(self, page):
        positions = self.future[page]
        return positions[0] if positions else None

    def select_victim(self, frames):
        # Maximize next-use position; negative frame ID breaks ties toward F0.
        frame = max(range(len(frames)), key=lambda frame: (self.next_use(frames[frame]) or float("inf"), -frame))
        next_use = self.next_use(frames[frame])
        explanation = "never used again" if next_use is None else f"next used at step {next_use}, farthest in the future"
        return frame, f"Optimal evicted page {frames[frame]} from frame {frame}: {explanation}."

    def snapshot(self, frames):
        return PolicyState("optimal", next_use=tuple((frame, self.next_use(page)) for frame, page in enumerate(frames) if page is not None))


def create_policy(name: str, accesses: tuple[Access, ...]) -> ReplacementPolicy:
    if name == "fifo":
        return FIFO()
    if name == "lru":
        return LRU()
    if name == "optimal":
        return Optimal(accesses)
    raise ValidationError("Choose fifo, lru, or optimal.", "policy")
