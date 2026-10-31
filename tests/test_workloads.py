"""Seeded recipes must be bounded, reproducible, and independent of global RNG."""

from random import random, seed as global_seed

import pytest
from fastapi.testclient import TestClient

from vmsim.core.models import MemoryConfig
from vmsim.core.workloads import generate_workload
from vmsim.core.validation import ValidationError
from vmsim.web.app import create_app


@pytest.mark.parametrize('profile', ['uniform', 'sequential', 'locality'])
@pytest.mark.parametrize('pages', [1, 8, 256])
def test_deterministic_ranges_modes_and_global_rng_independence(profile, pages):
    config = MemoryConfig(page_size=256, virtual_pages=pages)
    values = generate_workload(config, seed=0, length=1000, profile=profile)
    global_seed(19)
    random()
    assert values == generate_workload(config, seed=0, length=1000, profile=profile)
    assert len(values) == 1000 and all(0 <= page < pages for page in values)
    addresses = generate_workload(config, seed=0, length=1000, profile=profile, input_mode='addresses')
    assert tuple(address // 256 for address in addresses) == values
    assert all(0 <= address < config.virtual_capacity for address in addresses)


def test_sequential_wrap_and_uniform_reference_recipe():
    config = MemoryConfig(virtual_pages=8)
    assert generate_workload(config, seed=42, length=5, profile='uniform') == (0, 2, 1, 5, 5)
    sequence = generate_workload(config, seed=42, length=10, profile='sequential')
    assert sequence == (5, 6, 7, 0, 1, 2, 3, 4, 5, 6)
    assert generate_workload(config, seed=43) != generate_workload(config, seed=42)


@pytest.mark.parametrize('options', [{'seed': -1}, {'seed': 2**32}, {'seed': True}, {'length': 0}, {'length': 1001}, {'length': 2.5}, {'profile': 'guess'}, {'input_mode': 'hex'}])
def test_invalid_recipes(options):
    with pytest.raises(ValidationError):
        generate_workload(MemoryConfig(), **options)


def test_http_generation_and_saved_experiment_reproduction():
    with TestClient(create_app()) as client:
        recipe = {'seed': 42, 'length': 100, 'profile': 'locality', 'input_mode': 'addresses'}
        result = client.post('/api/workloads/generate', json=recipe)
        assert result.status_code == 200
        assert result.json() == client.post('/api/workloads/generate', json=recipe).json()
        request = {'workload': result.json()['workload'], 'input_mode': 'addresses', 'tlb_capacity': 2}
        exported = client.post('/api/experiments/export', json=request).json()
        restored = client.post('/api/experiments/import', json=exported).json()
        del restored['schema_version']
        assert client.post('/api/simulate', json=restored).json() == client.post('/api/simulate', json=request).json()
        assert client.post('/api/workloads/generate', json={**recipe, 'seed': True}).status_code == 422
