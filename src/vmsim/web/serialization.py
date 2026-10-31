"""JSON-safe response construction; no policy decisions occur here."""

from vmsim.core.experiments import SCHEMA_VERSION


def config_payload(config):
    return {"page_size": config.page_size, "virtual_pages": config.virtual_pages,
            "physical_frames": config.physical_frames, "virtual_capacity": config.virtual_capacity,
            "physical_capacity": config.physical_capacity, "offset_bits": config.offset_bits}


def metrics_payload(metrics):
    return {"hits": metrics.hits, "faults": metrics.faults, "replacements": metrics.replacements, "references": metrics.references,
            "hit_rate": metrics.hit_rate, "fault_rate": metrics.fault_rate}


def tlb_payload(tlb):
    if tlb is None:
        return None
    return {'capacity': tlb.capacity, 'hits': tlb.hits, 'misses': tlb.misses,
            'entries': [{'page': entry.page, 'frame_id': entry.frame_id} for entry in tlb.entries]}


def snapshot_payload(state):
    policy = state.policy_state
    return {
        "step": state.step,
        "frames": [{"frame_id": frame.frame_id, "page": frame.page} for frame in state.frames],
        "resident_pages": [{"page": entry.page, "frame_id": entry.frame_id} for entry in state.resident_pages],
        "metrics": metrics_payload(state.metrics),
        "tlb": tlb_payload(state.tlb),
        "policy_state": {
            "name": policy.name,
            "order": list(policy.order),
            "last_access": [{"frame_id": frame, "step": step} for frame, step in policy.last_access],
            "next_use": [{"frame_id": frame, "step": step} for frame, step in policy.next_use],
            "hand": policy.hand,
            "reference_bits": [{'frame_id': frame, 'referenced': referenced} for frame, referenced in policy.reference_bits],
        },
    }


def simulation_payload(result):
    return {
        "schema_version": SCHEMA_VERSION,
        "config": config_payload(result.config), "input_mode": result.input_mode,
        "policy": result.policy, "workload": [access.input_value for access in result.accesses],
        "initial_state": snapshot_payload(result.initial_state),
        "events": [{
            "step": event.step, "input_value": event.access.input_value,
            "virtual_address": event.access.virtual_address, "page": event.access.page,
            "offset": event.access.offset, "result": event.result,
            "frame_id": event.frame_id, "physical_address": event.physical_address,
            "victim_page": event.victim_page, "reason": event.reason,
            "tlb_result": event.tlb_result,
            "state": snapshot_payload(event.state),
        } for event in result.events],
        "metrics": metrics_payload(result.metrics),
        "tlb_capacity": result.tlb.capacity if result.tlb else 0,
        "tlb": tlb_payload(result.tlb),
    }
