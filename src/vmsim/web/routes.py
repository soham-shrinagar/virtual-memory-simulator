"""Stateless simulation/experiment HTTP endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from vmsim.core.engine import simulate
from vmsim.core.experiments import compare, experiment_payload, load_experiment, make_experiment
from vmsim.core.models import MemoryConfig
from vmsim.core.validation import ValidationError
from vmsim.web.schemas import CompareRequest, ComparisonResponse, ExperimentRequest, SimulationRequest, SimulationResponse
from vmsim.web.serialization import config_payload, metrics_payload, simulation_payload, tlb_payload

router = APIRouter(prefix="/api")


@router.post("/simulate", response_model=SimulationResponse)
def run_simulation(request: SimulationRequest):
    config = MemoryConfig(**request.config.model_dump())
    return simulation_payload(simulate(config, request.workload, request.input_mode, request.policy, tlb_capacity=request.tlb_capacity))


@router.post("/compare", response_model=ComparisonResponse)
def run_comparison(request: CompareRequest):
    config = MemoryConfig(**request.config.model_dump())
    experiment = make_experiment(config, request.workload, request.input_mode)
    rows = compare(config, experiment.workload, request.input_mode, request.policies, request.frame_counts, tlb_capacity=request.tlb_capacity)
    counts = request.frame_counts if request.frame_counts is not None else [config.physical_frames]
    return {
        "schema_version": 1, "config": config_payload(config),
        "input_mode": request.input_mode, "workload": list(experiment.workload),
        "policies": request.policies, "frame_counts": counts,
        "tlb_capacity": request.tlb_capacity,
        "rows": [{"policy": row.policy, "physical_frames": row.physical_frames, "metrics": metrics_payload(row.metrics), 'tlb': tlb_payload(row.tlb)} for row in rows],
    }


@router.post("/experiments/export")
def export_experiment(request: SimulationRequest):
    experiment = make_experiment(MemoryConfig(**request.config.model_dump()), request.workload, request.input_mode, request.policy, request.tlb_capacity)
    return JSONResponse(experiment_payload(experiment), headers={"Content-Disposition": 'attachment; filename="experiment.json"'})


@router.post("/experiments/import")
async def import_experiment(payload: ExperimentRequest, request: Request):
    # Keep the declared schema, but validate original text so duplicate keys
    # (including escaped spellings) cannot disappear during JSON decoding.
    try:
        text = (await request.body()).decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValidationError('Experiment files must use UTF-8.', 'experiment') from None
    return experiment_payload(load_experiment(text))
