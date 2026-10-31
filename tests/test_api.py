"""HTTP results must agree with the pure engine and reject invalid requests."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json

from fastapi.testclient import TestClient
import pytest

from vmsim.core.engine import simulate
from vmsim.core.models import MemoryConfig
from vmsim.web.app import create_app
from vmsim.web.serialization import simulation_payload


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "missing")) as client:
        yield client


@pytest.mark.parametrize("policy,faults", [("fifo", 5), ("lru", 6), ("optimal", 5)])
def test_http_matches_engine_exactly(client, policy, faults):
    response = client.post("/api/simulate", json={"workload": "1,2,3,1,4,2,5", "policy": policy})
    assert response.status_code == 200, response.text
    assert response.json() == simulation_payload(simulate(MemoryConfig(), [1, 2, 3, 1, 4, 2, 5], policy=policy))
    assert response.json()["metrics"]["faults"] == faults
    assert response.json()["initial_state"]["metrics"]["fault_rate"] is None
    assert "Infinity" not in response.text


@pytest.mark.parametrize("body", [
    {}, {"workload": ""}, {"workload": [True]}, {"workload": [1.0]},
    {"workload": [-1]}, {"workload": [8]}, {"workload": [0] * 1001},
    {"workload": [0], "policy": "random"}, {"workload": [0], "unexpected": 1},
    {"workload": [0], "config": {"physical_frames": True}},
    {"workload": [0], "config": {"page_size": 1000}},
])
def test_invalid_requests_have_structured_errors(client, body):
    response = client.post("/api/simulate", json=body)
    assert response.status_code == 422
    assert all("field" in error and "message" in error and "token_index" in error for error in response.json()["errors"])


def test_token_position_and_malformed_json(client):
    response = client.post("/api/simulate", json={"workload": "0, 1, 8"})
    assert response.json()["errors"][0]["token_index"] == 3
    assert client.post("/api/simulate", content="{", headers={"Content-Type": "application/json"}).status_code == 422


def test_request_limit_without_content_length(client):
    response = client.post("/api/simulate", content=(chunk for chunk in [b" " * 70000, b" " * 70000]), headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_concurrent_requests_have_independent_initial_state(client):
    def run(policy):
        return client.post("/api/simulate", json={"workload": [0, 1, 0, 2], "policy": policy, "config": {"physical_frames": 2}}).json()
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run, ["fifo", "lru", "optimal"] * 3))
    assert all(all(frame["page"] is None for frame in result["initial_state"]["frames"]) for result in results)
    assert results[0] == results[3] == results[6]
    results[0]["events"][0]["state"]["frames"][0]["page"] = 99
    assert run("fifo") == results[3]


def test_export_import_round_trip_and_missing_fields(client):
    request = {"workload": "0x1000 8300 4097", "input_mode": "addresses", "policy": "lru"}
    exported = client.post("/api/experiments/export", json=request)
    assert exported.status_code == 200
    assert "attachment" in exported.headers["Content-Disposition"]
    imported = client.post("/api/experiments/import", json=exported.json())
    assert imported.status_code == 200
    assert imported.json() == exported.json()
    restored = dict(imported.json())
    del restored["schema_version"]
    assert client.post("/api/simulate", json=restored).json() == client.post("/api/simulate", json=request).json()
    assert client.post("/api/experiments/import", json={"schema_version": 1, "workload": [0]}).status_code == 422
    invalid_version = {**exported.json(), "schema_version": True}
    assert client.post("/api/experiments/import", json=invalid_version).status_code == 422


def test_compare_api_belady_and_invalid_options(client):
    body = {"workload": "1,2,3,4,1,2,5,1,2,3,4,5", "frame_counts": [3, 4]}
    response = client.post("/api/compare", json=body)
    assert response.status_code == 200, response.text
    assert [row["metrics"]["faults"] for row in response.json()["rows"]] == [9, 10, 7, 9, 10, 8, 6, 10]
    for bad in ({"frame_counts": [True]}, {"policies": ["fifo", "fifo"]}, {"frame_counts": [1, 1]}):
        assert client.post("/api/compare", json={**body, **bad}).status_code == 422


@pytest.mark.parametrize('duplicate', ['"policy":"lru",', '"po\\u006cicy":"lru",'])
def test_import_rejects_duplicate_keys_in_original_json(client, duplicate):
    payload = client.post('/api/experiments/export', json={'workload': [0, 1]}).text
    text = '{' + duplicate + payload[1:]
    result = client.post('/api/experiments/import', content=text, headers={'Content-Type': 'application/json'})
    assert result.status_code == 422
    assert 'Duplicate JSON key: policy' in result.json()['errors'][0]['message']


def test_import_supports_utf8_bom_and_reproduces_address_offsets(client):
    experiment = client.post('/api/experiments/export', json={'workload': '0x1000,8300,4097', 'input_mode': 'addresses', 'policy': 'lru'}).json()
    restored = client.post('/api/experiments/import', content=b'\xef\xbb\xbf' + json.dumps(experiment).encode(), headers={'Content-Type': 'application/json'})
    assert restored.status_code == 200
    payload = restored.json()
    del payload['schema_version']
    trace = client.post('/api/simulate', json=payload).json()
    assert trace['events'][1]['physical_address'] == 4204
    assert trace['metrics']['faults'] == 2


def contract_payloads(client):
    request = {"config": {"page_size": 4096, "virtual_pages": 8, "physical_frames": 2},
               "workload": [0, 4097, 0, 8194], "input_mode": "addresses"}
    return {
        "simulations": [client.post("/api/simulate", json={**request, "policy": policy}).json() for policy in ("fifo", "lru", "optimal")],
        "comparison": client.post("/api/compare", json={**request, "frame_counts": [1, 2]}).json(),
        "experiment": client.post("/api/experiments/export", json={**request, "policy": "fifo"}).json(),
        "tlb_simulation": client.post('/api/simulate', json={**request, 'policy': 'lru', 'tlb_capacity': 2}).json(),
        "generated_workload": client.post('/api/workloads/generate', json={'seed': 42, 'length': 5, 'profile': 'uniform'}).json(),
        "clock_simulation": client.post('/api/simulate', json={'workload': [0, 1, 2, 0, 3, 1, 4], 'policy': 'clock', 'tlb_capacity': 2}).json(),
    }


def test_javascript_contract_fixtures_match_current_python_api(client):
    fixture = Path(__file__).resolve().parents[1] / "frontend/src/test/fixtures/contracts.json"
    assert json.loads(fixture.read_text()) == contract_payloads(client)
