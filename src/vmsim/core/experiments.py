"""Fresh-run comparisons and portable, versioned experiment files."""

from dataclasses import asdict, dataclass, replace
import json

from vmsim.core.engine import _simulate_validated
from vmsim.core.models import MemoryConfig, Metrics, TLBState
from vmsim.core.policies import POLICIES
from vmsim.core.translation import normalize_and_validate
from vmsim.core.validation import ValidationError, require_int

SCHEMA_VERSION = 1
EXPERIMENT_SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class Experiment:
    config: MemoryConfig
    workload: tuple[int, ...]
    input_mode: str = "pages"
    policy: str = "fifo"
    tlb_capacity: int = 0


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    policy: str
    physical_frames: int
    metrics: Metrics
    tlb: TLBState | None = None


def make_experiment(config, workload, input_mode="pages", policy="fifo", tlb_capacity=0) -> Experiment:
    accesses = normalize_and_validate(config, workload, input_mode)
    if policy not in POLICIES:
        raise ValidationError("Choose fifo, lru, or optimal.", "policy")
    require_int(tlb_capacity, 'tlb_capacity', 0, 32)
    return Experiment(config, tuple(access.input_value for access in accesses), input_mode, policy, tlb_capacity)


def experiment_payload(experiment: Experiment) -> dict:
    return {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "config": asdict(experiment.config),
        "workload": list(experiment.workload),
        "input_mode": experiment.input_mode,
        "policy": experiment.policy,
        "tlb_capacity": experiment.tlb_capacity,
    }


def dump_experiment(experiment: Experiment) -> str:
    # Revalidate even records constructed directly by a caller.
    checked = make_experiment(experiment.config, experiment.workload, experiment.input_mode, experiment.policy, experiment.tlb_capacity)
    return json.dumps(experiment_payload(checked), indent=2, allow_nan=False) + "\n"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"Duplicate JSON key: {key}.", "experiment")
        result[key] = value
    return result


def load_experiment(text: str) -> Experiment:
    if not isinstance(text, str) or len(text) > 131072:
        raise ValidationError("Experiment must be JSON text of at most 131072 characters.", "experiment")
    try:
        data = json.loads(text, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, RecursionError):
        raise ValidationError("Invalid experiment JSON.", "experiment") from None
    keys = {"schema_version", "config", "workload", "input_mode", "policy"}
    if isinstance(data, dict) and data.get('schema_version') == 2:
        keys.add('tlb_capacity')
    if not isinstance(data, dict) or set(data) != keys:
        raise ValidationError("Invalid or incomplete experiment fields for this schema version.", "experiment")
    if type(data["schema_version"]) is not int or data["schema_version"] not in (1, 2):
        raise ValidationError("Unsupported experiment schema version; expected 1 or 2.", "schema_version")
    config = data["config"]
    if not isinstance(config, dict) or set(config) != {"page_size", "virtual_pages", "physical_frames"}:
        raise ValidationError("Invalid memory configuration fields.", "config")
    return make_experiment(MemoryConfig(**config), data["workload"], data["input_mode"], data["policy"], data['tlb_capacity'] if data['schema_version'] == 2 else 0)


def compare(config, workload, input_mode="pages", policies=POLICIES, frame_counts=None, *, tlb_capacity=0) -> tuple[ComparisonRow, ...]:
    accesses = normalize_and_validate(config, workload, input_mode)
    if not isinstance(policies, (tuple, list)) or not 1 <= len(policies) <= 3 or any(p not in POLICIES for p in policies):
        raise ValidationError("Select between one and three supported policies.", "policies")
    if len(set(policies)) != len(policies):
        raise ValidationError("Policies must be unique.", "policies")
    counts = [config.physical_frames] if frame_counts is None else frame_counts
    if not isinstance(counts, (tuple, list)) or not 1 <= len(counts) <= 32:
        raise ValidationError("Select between one and 32 frame counts.", "frame_counts")
    for count in counts:
        require_int(count, "frame_counts", 1, 32)
    if len(set(counts)) != len(counts):
        raise ValidationError("Frame counts must be unique.", "frame_counts")
    # Only frame count changes, so the same validated immutable accesses apply
    # to every fresh run. Preserve their original mode and offsets.
    require_int(tlb_capacity, 'tlb_capacity', 0, 32)
    rows = []
    for count in counts:
        for policy in policies:
            result = _simulate_validated(replace(config, physical_frames=count), accesses, input_mode, policy,
                                         capture_trace=False, tlb_capacity=tlb_capacity)
            rows.append(ComparisonRow(policy, count, result.metrics, result.tlb))
    return tuple(rows)
