"""Domain boundaries and concrete translation/free-frame behavior."""

from dataclasses import FrozenInstanceError

import pytest

from vmsim.core.engine import Memory, MemoryFullError, simulate
from vmsim.core.models import MemoryConfig
from vmsim.core.translation import normalize_and_validate, physical_address, split_address
from vmsim.core.validation import ValidationError


@pytest.mark.parametrize("field,value", [
    ("page_size", 0), ("page_size", 1000), ("page_size", 131072),
    ("page_size", True), ("virtual_pages", 0), ("virtual_pages", 257),
    ("virtual_pages", 8.0), ("physical_frames", 0), ("physical_frames", 33),
])
def test_invalid_configuration(field, value):
    with pytest.raises(ValidationError) as error:
        MemoryConfig(**{field: value})
    assert error.value.field == field


def test_capacities_and_address_boundaries():
    config = MemoryConfig(page_size=4096, virtual_pages=3, physical_frames=5)
    assert (config.virtual_capacity, config.physical_capacity, config.offset_bits) == (12288, 20480, 12)
    assert [split_address(config, address) for address in (0, 4095, 4096, 8300, 12287)] == [(0, 0), (0, 4095), (1, 0), (2, 108), (2, 4095)]
    assert physical_address(config, 1, 108) == 4204
    for address in (-1, 12288, True, 2.0):
        with pytest.raises(ValidationError):
            split_address(config, address)
    for frame, offset in ((5, 0), (0, 4096), (-1, 0), (0, -1)):
        with pytest.raises(ValidationError):
            physical_address(config, frame, offset)


def test_modes_and_hexadecimal_normalize_to_same_addresses():
    config = MemoryConfig()
    pages = normalize_and_validate(config, "0, 2\n1", "pages")
    addresses = normalize_and_validate(config, "0 0x2000, 4096", "addresses")
    assert [(a.virtual_address, a.page, a.offset) for a in pages] == [(a.virtual_address, a.page, a.offset) for a in addresses]
    assert normalize_and_validate(config, "0002")[0].page == 2


@pytest.mark.parametrize("workload,mode", [
    ("", "pages"), ("1,,2", "pages"), ("1,", "pages"),
    ("-1", "pages"), ("+1", "pages"), ("1.5", "pages"),
    ("0x2", "pages"), ("0xGG", "addresses"), ("8", "pages"),
    ("32768", "addresses"), ([True], "pages"), ([2.0], "pages"),
    ([], "pages"), ([0] * 1001, "pages"), ("0" * 65, "pages"),
    (" " * 65537, "pages"), (None, "pages"), ("0", "unknown"),
])
def test_invalid_workloads_are_rejected(workload, mode):
    with pytest.raises(ValidationError):
        normalize_and_validate(MemoryConfig(), workload, mode)


def test_invalid_reference_identifies_token():
    with pytest.raises(ValidationError) as error:
        normalize_and_validate(MemoryConfig(), "0, 1, 8")
    assert error.value.token_index == 3


def test_initial_page_table_and_free_frame_allocation():
    memory = Memory(MemoryConfig())
    assert memory.snapshot().metrics.fault_rate is None
    assert all(not entry.resident for entry in memory.page_table)
    assert memory.resolve(2) == (0, False)
    assert memory.resolve(0) == (1, False)
    assert memory.resolve(2) == (0, True)
    assert memory.page_table[0].frame_id == 1
    assert memory.page_table[2].frame_id == 0


def test_no_eviction_trace_preserves_offsets_and_initial_snapshot():
    result = simulate(MemoryConfig(), "4096,8300,4097", "addresses")
    assert [event.physical_address for event in result.events] == [0, 4204, 1]
    assert [event.result for event in result.events] == ["fault", "fault", "hit"]
    assert (result.metrics.faults, result.metrics.hits, result.metrics.replacements) == (2, 1, 0)
    assert all(frame.page is None for frame in result.initial_state.frames)
    assert result.events[0].state.frames[1].page is None
    with pytest.raises(FrozenInstanceError):
        result.events[0].state.frames[0].page = 5


def test_phase_one_reports_full_memory_instead_of_wrong_eviction():
    with pytest.raises(MemoryFullError):
        simulate(MemoryConfig(physical_frames=1), [0, 1])


def test_more_frames_than_pages_and_maximum_trace():
    result = simulate(MemoryConfig(virtual_pages=1, physical_frames=3), [0] * 1000)
    assert result.metrics.hits == 999
    assert result.metrics.faults == 1
    assert result.events[-1].state.frames[1].page is None
