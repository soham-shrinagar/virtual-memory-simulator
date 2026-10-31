"""Fully associative translation cache with fixed LRU replacement."""

from collections import OrderedDict

from vmsim.core.models import PageTableEntry, TLBState
from vmsim.core.validation import require_int


class TLB:
    def __init__(self, capacity):
        self.capacity = require_int(capacity, 'tlb_capacity', 1, 32)
        self.entries = OrderedDict()
        self.hits = 0
        self.misses = 0

    def lookup(self, page):
        frame = self.entries.get(page)
        if frame is None:
            self.misses += 1
        else:
            self.hits += 1
            self.entries.move_to_end(page)
        return frame

    def invalidate(self, page):
        self.entries.pop(page, None)

    def fill(self, page, frame):
        self.entries[page] = frame
        self.entries.move_to_end(page)
        if len(self.entries) > self.capacity:
            self.entries.popitem(last=False)

    def snapshot(self):
        return TLBState(self.capacity, self.hits, self.misses,
                        tuple(PageTableEntry(page, frame) for page, frame in self.entries.items()))

    def check_invariants(self, memory):
        assert len(self.entries) <= self.capacity
        assert self.hits + self.misses == memory.metrics.references
        assert all(memory.mapping.get(page) == frame for page, frame in self.entries.items())
