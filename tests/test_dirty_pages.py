"""Read/write accounting across replacement, cached hits, files, and HTTP."""

from dataclasses import replace
import json

from fastapi.testclient import TestClient
import pytest

from vmsim.core.engine import simulate
from vmsim.core.experiments import compare, dump_experiment, load_experiment, make_experiment
from vmsim.core.models import MemoryConfig
from vmsim.core.policies import POLICIES
from vmsim.core.translation import normalize_and_validate
from vmsim.core.validation import ValidationError
from vmsim.web.app import create_app


@pytest.mark.parametrize("policy", POLICIES)
def test_dirty_eviction_repeated_writes_read_preservation_and_clean_reload(policy):
    result = simulate(MemoryConfig(physical_frames=1), "W:0 R:0 1 0 W:0 W:0 2",
                      policy=policy, tlb_capacity=2)
    assert (result.metrics.reads, result.metrics.writes, result.metrics.writebacks) == (4, 3, 2)
    assert (result.metrics.hits, result.metrics.faults, result.metrics.replacements) == (3, 4, 3)
    assert [event.writeback for event in result.events] == [False, False, True, False, False, False, True]
    assert [event.state.frames[0].dirty for event in result.events] == [True, True, False, False, True, True, False]
    assert result.events[4].tlb_result == "hit"  # A write through the cache marks a clean page dirty.
    assert result.initial_state.frames[0].dirty is False
    assert result.events[0].state.frames[0].dirty is True  # Later eviction preserves old snapshots.
    assert result.events[2].state.metrics.writebacks == 1
    assert result.events[1].state.metrics.writebacks == 0
    assert "written back" in result.events[2].reason


def test_resident_dirty_pages_are_not_flushed_at_the_end_and_read_faults_are_clean():
    config = MemoryConfig(physical_frames=3)
    result = simulate(config, "0 W:1 W:1 R:1")
    assert [frame.dirty for frame in result.events[-1].state.frames] == [False, True, False]
    assert result.metrics.writebacks == result.metrics.replacements == 0
    assert result.metrics.reads == result.metrics.writes == 2
    assert result.events[-1].state.frames[2].page is None


def test_address_prefixes_and_explicit_operations_have_identical_traces():
    config = MemoryConfig(physical_frames=1)
    text = simulate(config, "w:0x1001 R:4097 r:8300", "addresses")
    explicit = simulate(config, [4097, 4097, 8300], "addresses", operations=["write", "read", "read"])
    assert text == explicit
    assert [event.access.offset for event in text.events] == [1, 1, 108]
    assert text.events[-1].physical_address == 108
    assert text.metrics.writebacks == 1


@pytest.mark.parametrize("workload,operations", [
    ("W:", None), ("X:1", None), ("W: 1", None), ("W:0x1", None),
    ("W:-1", None), ("W:1,,2", None), ("W:8", None),
    ([0, 1], []), ([0, 1], ["write"]), ([0], ["READ"]), ([0], [True]),
    ([0], "write"), ("W:0", ["read"]), ("R:0", ["write"]),
])
def test_malformed_or_conflicting_operations_are_rejected(workload, operations):
    with pytest.raises(ValidationError):
        normalize_and_validate(MemoryConfig(), workload, operations=operations)


@pytest.mark.parametrize("policy", POLICIES)
def test_writes_and_tlb_do_not_change_victims_and_summary_sweeps_match(policy):
    config = MemoryConfig(physical_frames=2)
    pages = [0, 1, 0, 2, 1, 3, 0, 3, 2, 1]
    operations = ["write", "read", "write", "read", "read", "write", "read", "write", "read", "write"]
    baseline = simulate(config, pages, policy=policy)
    dirty = simulate(config, pages, policy=policy, operations=operations)
    cached = simulate(config, pages, policy=policy, tlb_capacity=2, operations=operations)
    assert [(event.frame_id, event.victim_page) for event in dirty.events] == [
        (event.frame_id, event.victim_page) for event in baseline.events]
    assert dirty.metrics == cached.metrics
    assert [event.state.frames for event in dirty.events] == [event.state.frames for event in cached.events]
    summary = simulate(config, pages, policy=policy, capture_trace=False, operations=operations)
    assert summary.metrics == dirty.metrics and summary.events == ()
    for row in compare(config, pages, policies=[policy], frame_counts=[1, 2, 4],
                       operations=operations, tlb_capacity=2):
        trace = simulate(replace(config, physical_frames=row.physical_frames), pages, policy=policy,
                         operations=operations, tlb_capacity=2)
        assert (row.metrics, row.tlb) == (trace.metrics, trace.tlb)


def test_v3_round_trip_and_legacy_files_preserve_reads():
    experiment = make_experiment(MemoryConfig(physical_frames=1), "W:0 1 W:1 2", tlb_capacity=2)
    text = dump_experiment(experiment)
    assert json.loads(text)["operations"] == ["write", "read", "write", "read"]
    assert load_experiment(text) == experiment
    restored = load_experiment(text)
    assert simulate(restored.config, restored.workload, tlb_capacity=restored.tlb_capacity,
                    operations=restored.operations).metrics.writebacks == 2
    for version in (1, 2):
        legacy = json.loads(text)
        legacy["schema_version"] = version
        del legacy["operations"]
        if version == 1:
            del legacy["tlb_capacity"]
        imported = load_experiment(json.dumps(legacy))
        assert imported.operations == ("read",) * 4
        assert json.loads(dump_experiment(imported))["schema_version"] == 3
        legacy["workload"] = "W:0"
        with pytest.raises(ValidationError):
            load_experiment(json.dumps(legacy))
    for operations in (None, [], ["write"], ["invalid"] * 4):
        with pytest.raises(ValidationError):
            load_experiment(json.dumps({**json.loads(text), "operations": operations}))


def test_http_import_export_replay_compare_and_invalid_operations():
    with TestClient(create_app()) as client:
        request = {"config": {"physical_frames": 1}, "workload": "W:0 R:0 W:1 2", "tlb_capacity": 2}
        trace = client.post("/api/simulate", json=request)
        assert trace.status_code == 200, trace.text
        assert trace.json()["metrics"]["writebacks"] == 2
        file = client.post("/api/experiments/export", json=request).json()
        assert file["schema_version"] == 3
        assert file["operations"] == ["write", "read", "write", "read"]
        assert client.post("/api/experiments/import", json=file).json() == file
        missing_operations = {key: value for key, value in file.items() if key != "operations"}
        assert client.post("/api/experiments/import", json=missing_operations).status_code == 422
        assert client.post("/api/experiments/import", json={**file, "operations": None}).status_code == 422
        del file["schema_version"]
        assert client.post("/api/simulate", json=file).json() == trace.json()
        comparison = client.post("/api/compare", json={**request, "frame_counts": [1]})
        assert comparison.status_code == 200
        assert comparison.json()["operations"] == file["operations"]
        assert all(row["metrics"]["writebacks"] == 2 for row in comparison.json()["rows"])
        for operations in ([], ["read"], [True] * 4, ["read"] * 4):
            assert client.post("/api/simulate", json={**request, "operations": operations}).status_code == 422
