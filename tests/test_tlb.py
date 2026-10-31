"""Cache accounting, recency, invalidation, and transparent page replacement."""

from dataclasses import replace
from itertools import product
import json

import pytest
from fastapi.testclient import TestClient

from vmsim.core.engine import simulate
from vmsim.core.experiments import compare, dump_experiment, load_experiment, make_experiment
from vmsim.core.models import MemoryConfig
from vmsim.core.validation import ValidationError
from vmsim.web.app import create_app


@pytest.mark.parametrize('policy', ['fifo', 'lru', 'optimal'])
def test_cache_hit_miss_and_resident_miss_are_separate(policy):
    result = simulate(MemoryConfig(), [0, 1, 0, 0], policy=policy, tlb_capacity=1)
    assert [event.tlb_result for event in result.events] == ['miss', 'miss', 'miss', 'hit']
    assert [event.result for event in result.events] == ['fault', 'fault', 'hit', 'hit']
    assert (result.tlb.hits, result.tlb.misses) == (1, 3)
    assert result.events[-1].frame_id == 0  # F0 is a valid cached mapping.
    assert result.initial_state.tlb.entries == ()
    assert result.events[0].state.tlb.entries[0].page == 0


def test_tlb_lru_evicts_translation_and_memory_eviction_invalidates_cache():
    result = simulate(MemoryConfig(physical_frames=3), [0, 1, 0, 2], tlb_capacity=2)
    assert [entry.page for entry in result.tlb.entries] == [0, 2]
    result = simulate(MemoryConfig(physical_frames=1), [0, 1, 0], tlb_capacity=32)
    assert result.tlb.hits == 0
    assert result.tlb.misses == 3
    assert [entry.page for entry in result.tlb.entries] == [0]


def test_lru_hits_through_tlb_update_the_memory_policy():
    result = simulate(MemoryConfig(physical_frames=2), [0, 1, 0, 2], policy='lru', tlb_capacity=2)
    assert result.events[2].tlb_result == 'hit'
    assert result.events[3].victim_page == 1


@pytest.mark.parametrize('policy', ['fifo', 'lru', 'optimal'])
def test_tlb_never_changes_page_decisions_on_exhaustive_short_workloads(policy):
    for pages in product(range(3), repeat=5):
        baseline = simulate(MemoryConfig(physical_frames=2), pages, policy=policy)
        for capacity in (1, 2, 4):
            cached = simulate(baseline.config, pages, policy=policy, tlb_capacity=capacity)
            assert cached.metrics == baseline.metrics
            assert [(event.frame_id, event.victim_page, event.state.policy_state) for event in cached.events] == [
                (event.frame_id, event.victim_page, event.state.policy_state) for event in baseline.events]
            for event in cached.events:
                assert event.state.tlb.hits + event.state.tlb.misses == event.step
                assert all(event.state.frames[entry.frame_id].page == entry.page for entry in event.state.tlb.entries)


@pytest.mark.parametrize('capacity', [-1, 33, True, 1.5])
def test_invalid_tlb_capacity(capacity):
    with pytest.raises(ValidationError):
        simulate(MemoryConfig(), [0], tlb_capacity=capacity)


def test_disabled_cache_and_summary_comparisons():
    config = MemoryConfig(physical_frames=2)
    baseline = simulate(config, [0, 1, 0, 2])
    assert baseline.tlb is None
    assert all(event.tlb_result is None and event.state.tlb is None for event in baseline.events)
    for row in compare(config, [0, 1, 0, 2], frame_counts=[1, 2, 3], tlb_capacity=2):
        standalone = simulate(replace(config, physical_frames=row.physical_frames), [0, 1, 0, 2], policy=row.policy, tlb_capacity=2)
        assert (row.metrics, row.tlb) == (standalone.metrics, standalone.tlb)


def test_versioned_experiments_and_http_cache_contract():
    experiment = make_experiment(MemoryConfig(), [0, 1, 0], tlb_capacity=2)
    assert load_experiment(dump_experiment(experiment)) == experiment
    legacy = json.loads(dump_experiment(experiment))
    legacy['schema_version'] = 1
    del legacy['tlb_capacity']
    assert load_experiment(json.dumps(legacy)).tlb_capacity == 0
    with TestClient(create_app()) as client:
        request = {'workload': [0, 1, 0], 'tlb_capacity': 2}
        trace = client.post('/api/simulate', json=request).json()
        assert trace['tlb']['hits'] == 1
        assert trace['events'][2]['tlb_result'] == 'hit'
        exported = client.post('/api/experiments/export', json=request).json()
        assert exported['schema_version'] == 2
        assert client.post('/api/experiments/import', json=exported).json() == exported
        assert client.post('/api/experiments/import', json=legacy).json()['tlb_capacity'] == 0
        assert client.post('/api/simulate', json={**request, 'tlb_capacity': True}).status_code == 422
