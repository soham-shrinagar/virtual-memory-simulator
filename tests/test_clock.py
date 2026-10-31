"""Second-chance hand movement, reference-bit snapshots, and persistence."""

import json

import pytest
from fastapi.testclient import TestClient

from vmsim.core.engine import simulate
from vmsim.core.experiments import dump_experiment, load_experiment, make_experiment
from vmsim.core.models import MemoryConfig
from vmsim.core.validation import ValidationError
from vmsim.web.app import create_app


def test_clock_full_scan_hit_bits_hand_and_immutable_history():
    result = simulate(MemoryConfig(physical_frames=3), [0, 1, 2, 0, 3, 1, 4], policy='clock')
    assert [event.victim_page for event in result.events if event.victim_page is not None] == [0, 2]
    assert result.initial_state.policy_state.hand == 0
    assert result.initial_state.policy_state.reference_bits == ()
    assert [event.state.policy_state.hand for event in result.events] == [1, 2, 0, 0, 1, 1, 0]
    assert result.events[4].state.policy_state.reference_bits == ((0, True), (1, False), (2, False))
    assert result.events[5].state.policy_state.reference_bits == ((0, True), (1, True), (2, False))
    assert 'Cleared reference bits in frames 0, 1, 2' in result.events[4].reason
    assert result.events[2].state.policy_state.reference_bits == ((0, True), (1, True), (2, True))


@pytest.mark.parametrize('frames', [1, 4, 32])
def test_clock_repeated_hits_free_frames_and_cache_are_consistent(frames):
    result = simulate(MemoryConfig(physical_frames=frames), [0, 0, 1, 1, 0], policy='clock', tlb_capacity=2)
    assert result.metrics.faults == (3 if frames == 1 else 2)
    assert result.metrics.replacements == (2 if frames == 1 else 0)
    for event in result.events:
        state = event.state.policy_state
        assert 0 <= state.hand < frames
        assert dict(state.reference_bits).keys() == {frame.frame_id for frame in event.state.frames if frame.page is not None}
        assert dict(state.reference_bits)[event.frame_id] is True


def test_clock_experiment_and_http_comparison_round_trip():
    experiment = make_experiment(MemoryConfig(), [0, 1, 2, 3, 0], policy='clock', tlb_capacity=2)
    text = dump_experiment(experiment)
    assert load_experiment(text) == experiment
    legacy = json.loads(text)
    legacy['schema_version'] = 1
    del legacy['tlb_capacity']
    with pytest.raises(ValidationError):
        load_experiment(json.dumps(legacy))
    with TestClient(create_app()) as client:
        payload = json.loads(text)
        assert client.post('/api/experiments/import', json=payload).json() == payload
        del payload['schema_version']
        trace = client.post('/api/simulate', json=payload).json()
        assert trace['policy'] == 'clock'
        assert trace['events'][-1]['state']['policy_state']['reference_bits']
        comparison = client.post('/api/compare', json={'workload': [0, 1, 2, 3, 0], 'frame_counts': [1, 3]}).json()
        assert comparison['policies'] == ['fifo', 'lru', 'optimal', 'clock']
        assert len(comparison['rows']) == 8
