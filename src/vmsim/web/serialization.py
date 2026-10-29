"""JSON-safe response construction; no policy decisions occur here."""

from dataclasses import asdict

from vmsim.core.experiments import SCHEMA_VERSION


def config_payload(config):
    return {**asdict(config), "virtual_capacity": config.virtual_capacity,
            "physical_capacity": config.physical_capacity, "offset_bits": config.offset_bits}


def metrics_payload(metrics):
    return {**asdict(metrics), "references": metrics.references,
            "hit_rate": metrics.hit_rate, "fault_rate": metrics.fault_rate}


def snapshot_payload(state):
    policy = state.policy_state
    return {
        "step": state.step,
        "frames": [asdict(frame) for frame in state.frames],
        "resident_pages": [asdict(entry) for entry in state.resident_pages],
        "metrics": metrics_payload(state.metrics),
        "policy_state": {
            "name": policy.name,
            "order": list(policy.order),
            "last_access": [{"frame_id": frame, "step": step} for frame, step in policy.last_access],
            "next_use": [{"frame_id": frame, "step": step} for frame, step in policy.next_use],
        },
    }


def simulation_payload(result):
    return {
        "schema_version": SCHEMA_VERSION,
        "config": config_payload(result.config), "input_mode": result.input_mode,
        "policy": result.policy, "workload": [access.input_value for access in result.accesses],
        "initial_state": snapshot_payload(result.initial_state),
        "events": [{
            "step": event.step, **asdict(event.access), "result": event.result,
            "frame_id": event.frame_id, "physical_address": event.physical_address,
            "victim_page": event.victim_page, "reason": event.reason,
            "state": snapshot_payload(event.state),
        } for event in result.events],
        "metrics": metrics_payload(result.metrics),
    }
