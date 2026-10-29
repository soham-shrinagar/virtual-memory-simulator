"""Stateless simulation/experiment HTTP endpoints."""

import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from vmsim.core.engine import simulate
from vmsim.core.experiments import compare, experiment_payload, load_experiment, make_experiment
from vmsim.core.models import MemoryConfig
from vmsim.web.schemas import CompareRequest, ComparisonResponse, ExperimentRequest, SimulationRequest, SimulationResponse
from vmsim.web.serialization import config_payload, metrics_payload, simulation_payload

router = APIRouter(prefix="/api")


@router.post("/simulate", response_model=SimulationResponse)
def run_simulation(request: SimulationRequest):
    config = MemoryConfig(**request.config.model_dump())
    return simulation_payload(simulate(config, request.workload, request.input_mode, request.policy))


@router.post("/compare", response_model=ComparisonResponse)
def run_comparison(request: CompareRequest):
    config = MemoryConfig(**request.config.model_dump())
    experiment = make_experiment(config, request.workload, request.input_mode)
    rows = compare(config, experiment.workload, request.input_mode, request.policies, request.frame_counts)
    counts = request.frame_counts if request.frame_counts is not None else [config.physical_frames]
    return {
        "schema_version": 1, "config": config_payload(config),
        "input_mode": request.input_mode, "workload": list(experiment.workload),
        "policies": request.policies, "frame_counts": counts,
        "rows": [{"policy": row.policy, "physical_frames": row.physical_frames, "metrics": metrics_payload(row.metrics)} for row in rows],
    }


@router.post("/experiments/export")
def export_experiment(request: SimulationRequest):
    experiment = make_experiment(MemoryConfig(**request.config.model_dump()), request.workload, request.input_mode, request.policy)
    return JSONResponse(experiment_payload(experiment), headers={"Content-Disposition": 'attachment; filename="experiment.json"'})


@router.post("/experiments/import")
def import_experiment(request: ExperimentRequest):
    return experiment_payload(load_experiment(json.dumps(request.model_dump())))
