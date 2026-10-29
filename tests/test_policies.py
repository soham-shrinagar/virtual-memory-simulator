"""Known answers, intermediate victim decisions, and independent OPT oracle."""

from dataclasses import FrozenInstanceError
from functools import lru_cache
from itertools import product

import pytest

from vmsim.core.engine import simulate
from vmsim.core.models import MemoryConfig
from vmsim.core.policies import POLICIES
from vmsim.core.validation import ValidationError

EXAMPLE = [1, 2, 3, 1, 4, 2, 5]
BELADY = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]


@pytest.mark.parametrize("pages,frames,policy,faults", [
    (EXAMPLE, 3, "fifo", 5), (EXAMPLE, 3, "lru", 6), (EXAMPLE, 3, "optimal", 5),
    (BELADY, 3, "fifo", 9), (BELADY, 4, "fifo", 10),
    (BELADY, 3, "lru", 10), (BELADY, 4, "lru", 8),
    (BELADY, 3, "optimal", 7), (BELADY, 4, "optimal", 6),
])
def test_known_fault_counts_and_accounting(pages, frames, policy, faults):
    config = MemoryConfig(physical_frames=frames)
    result = simulate(config, pages, policy=policy)
    assert result.metrics.faults == faults
    assert result.metrics.hits == len(pages) - faults
    for event in result.events:
        metrics = event.state.metrics
        resident = [frame.page for frame in event.state.frames if frame.page is not None]
        assert len(resident) == len(set(resident))
        assert metrics.references == event.step
        assert metrics.faults - metrics.replacements == len(resident)
        assert event.state.frames[event.frame_id].page == event.access.page
        assert 0 <= event.physical_address < config.physical_capacity
        assert metrics.fault_rate + metrics.hit_rate == pytest.approx(1)


def test_hits_change_lru_but_not_fifo_order():
    fifo = simulate(MemoryConfig(physical_frames=2), [0, 1, 0, 2], policy="fifo")
    lru = simulate(MemoryConfig(physical_frames=2), [0, 1, 0, 2], policy="lru")
    assert fifo.events[2].state.policy_state.order == (0, 1)
    assert lru.events[2].state.policy_state.order == (1, 0)
    assert fifo.events[3].victim_page == 0
    assert lru.events[3].victim_page == 1
    assert "oldest resident arrival" in fifo.events[3].reason
    assert "step 2" in lru.events[3].reason


def test_optimal_tie_break_and_next_use_explanations():
    result = simulate(MemoryConfig(physical_frames=2), [0, 1, 2, 3], policy="optimal")
    assert result.events[2].frame_id == 0
    assert "never used again" in result.events[2].reason
    assert all(next_use is None for _, next_use in result.events[-1].state.policy_state.next_use)
    result = simulate(MemoryConfig(physical_frames=2), [0, 1, 2, 0, 1], policy="optimal")
    assert result.events[2].victim_page == 1
    assert "step 5" in result.events[2].reason


@pytest.mark.parametrize("policy", POLICIES)
def test_single_frame_offsets_repeated_runs_and_summary(policy):
    config = MemoryConfig(physical_frames=1)
    result = simulate(config, [0, 4097, 4098, 0], "addresses", policy)
    assert [event.physical_address for event in result.events] == [0, 1, 2, 0]
    assert (result.metrics.hits, result.metrics.faults, result.metrics.replacements) == (1, 3, 2)
    assert simulate(config, [0, 4097, 4098, 0], "addresses", policy) == result
    summary = simulate(config, [0, 4097, 4098, 0], "addresses", policy, capture_trace=False)
    assert summary.metrics == result.metrics
    assert summary.events == ()
    with pytest.raises(FrozenInstanceError):
        result.events[0].state.metrics.hits = 20
    assert result.events[0].state.frames[0].page == 0


def optimal_oracle(pages, capacity):
    @lru_cache(None)
    def solve(index, resident):
        if index == len(pages):
            return 0
        page = pages[index]
        if page in resident:
            return solve(index + 1, resident)
        if len(resident) < capacity:
            return 1 + solve(index + 1, tuple(sorted((*resident, page))))
        return 1 + min(solve(index + 1, tuple(sorted((*[p for p in resident if p != victim], page)))) for victim in resident)
    return solve(0, ())


def test_exhaustive_short_traces_against_independent_oracle():
    for length in range(1, 6):
        for pages in product(range(3), repeat=length):
            previous_lru = previous_opt = length + 1
            for capacity in (1, 2, 3):
                config = MemoryConfig(virtual_pages=3, physical_frames=capacity)
                faults = {policy: simulate(config, pages, policy=policy, capture_trace=False).metrics.faults for policy in POLICIES}
                assert faults["optimal"] == optimal_oracle(pages, capacity)
                assert faults["optimal"] <= min(faults["fifo"], faults["lru"])
                assert faults["lru"] <= previous_lru
                assert faults["optimal"] <= previous_opt
                previous_lru, previous_opt = faults["lru"], faults["optimal"]


def test_unknown_policy_is_rejected():
    with pytest.raises(ValidationError) as error:
        simulate(MemoryConfig(), [0], policy="random")
    assert error.value.field == "policy"
