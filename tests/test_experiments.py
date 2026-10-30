"""Versioned files and fresh-run algorithm comparisons."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from vmsim.core.engine import simulate
from vmsim.core.experiments import compare, dump_experiment, experiment_payload, load_experiment, make_experiment
from vmsim.core.models import MemoryConfig
from vmsim.core.validation import ValidationError


def test_json_round_trip_preserves_addresses_policy_and_results():
    original = make_experiment(MemoryConfig(), "0x1000,8300,4097", "addresses", "lru")
    restored = load_experiment(dump_experiment(original))
    assert restored == original
    assert simulate(restored.config, restored.workload, restored.input_mode, restored.policy) == simulate(original.config, original.workload, original.input_mode, original.policy)


@pytest.mark.parametrize("change", [
    {"schema_version": 2}, {"schema_version": True}, {"extra": 1},
    {"workload": [True]}, {"input_mode": "guess"}, {"policy": "random"},
    {"config": {"page_size": 4096}},
])
def test_invalid_experiment_fields(change):
    data = experiment_payload(make_experiment(MemoryConfig(), [0]))
    data.update(change)
    with pytest.raises(ValidationError):
        load_experiment(json.dumps(data))


@pytest.mark.parametrize("text", ["{", "[]", '{"schema_version":1,"schema_version":2}', "[" * 1100])
def test_malformed_duplicate_and_deep_json(text):
    with pytest.raises(ValidationError):
        load_experiment(text)


def test_comparison_is_fresh_and_matches_standalone():
    config = MemoryConfig()
    pages = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    rows = compare(config, pages, frame_counts=[3, 4])
    assert [row.metrics.faults for row in rows] == [9, 10, 7, 10, 8, 6]
    for row in rows:
        standalone = simulate(replace(config, physical_frames=row.physical_frames), pages, policy=row.policy)
        assert row.metrics == standalone.metrics
    assert compare(config, pages, frame_counts=[3, 4]) == rows


@pytest.mark.parametrize('page_size', [256, 4096, 65536])
def test_address_sweeps_match_full_traces_with_offsets_and_excess_frames(page_size):
    config = MemoryConfig(page_size=page_size, virtual_pages=5)
    addresses = [0, page_size + 17, page_size - 1, page_size * 4 + 5, page_size + 2]
    for row in compare(config, addresses, 'addresses', frame_counts=[1, 3, 32]):
        trace = simulate(replace(config, physical_frames=row.physical_frames), addresses, 'addresses', row.policy)
        assert row.metrics == trace.metrics
        assert [event.access.offset for event in trace.events] == [0, 17, page_size - 1, 5, 2]


@pytest.mark.parametrize("options", [
    {"policies": []}, {"policies": ["fifo", "fifo"]}, {"policies": ["other"]},
    {"frame_counts": []}, {"frame_counts": [1, 1]}, {"frame_counts": [True]},
    {"frame_counts": [0]}, {"frame_counts": [33]},
])
def test_invalid_comparison_options(options):
    with pytest.raises(ValidationError):
        compare(MemoryConfig(), [0], **options)


def test_example_files_are_valid_reproducible_experiments():
    root = Path(__file__).resolve().parents[1]
    for name, faults in (("fifo", 5), ("belady", 9), ("translation", 2)):
        experiment = load_experiment((root / "examples" / f"{name}.json").read_text())
        assert simulate(experiment.config, experiment.workload, experiment.input_mode, experiment.policy).metrics.faults == faults
