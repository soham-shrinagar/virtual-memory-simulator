"""Fresh-run comparisons and portable, versioned experiment files."""

from dataclasses import asdict, dataclass, replace
import json

from vmsim.core.engine import _simulate_validated
from vmsim.core.models import MemoryConfig, Metrics, TLBState
from vmsim.core.policies import POLICIES
from vmsim.core.translation import normalize_and_validate
from vmsim.core.validation import ValidationError, require_int

SCHEMA_VERSION = 1
EXPERIMENT_SCHEMA_VERSION = 3


@dataclass(frozen=True, slots=True)
class Experiment:
    config: MemoryConfig
    workload: tuple[int, ...]
    input_mode: str = "pages"
    policy: str = "fifo"
    tlb_capacity: int = 0
    operations: tuple[str, ...] | None = None

    def __post_init__(self):
        accesses = normalize_and_validate(self.config, self.workload, self.input_mode, operations=self.operations)
        if self.policy not in POLICIES:
            raise ValidationError("Choose fifo, lru, optimal, or clock.", "policy")
        require_int(self.tlb_capacity, 'tlb_capacity', 0, 32)
        object.__setattr__(self, "workload", tuple(access.input_value for access in accesses))
        object.__setattr__(self, "operations", tuple(access.operation for access in accesses))


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    policy: str
    physical_frames: int
    metrics: Metrics
    tlb: TLBState | None = None


def make_experiment(config, workload, input_mode="pages", policy="fifo", tlb_capacity=0, *, operations=None) -> Experiment:
    return Experiment(config, workload, input_mode, policy, tlb_capacity, operations)


def experiment_payload(experiment: Experiment) -> dict:
    return {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "config": asdict(experiment.config),
        "workload": list(experiment.workload),
        "input_mode": experiment.input_mode,
        "policy": experiment.policy,
        "tlb_capacity": experiment.tlb_capacity,
        "operations": list(experiment.operations),
    }


def dump_experiment(experiment: Experiment) -> str:
    return json.dumps(experiment_payload(experiment), indent=2, allow_nan=False) + "\n"


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
    if isinstance(data, dict) and data.get('schema_version') in (2, 3):
        keys.add('tlb_capacity')
    if isinstance(data, dict) and data.get('schema_version') == 3:
        keys.add('operations')
    if not isinstance(data, dict) or set(data) != keys:
        raise ValidationError("Invalid or incomplete experiment fields for this schema version.", "experiment")
    if type(data["schema_version"]) is not int or data["schema_version"] not in (1, 2, 3):
        raise ValidationError("Unsupported experiment schema version; expected 1, 2, or 3.", "schema_version")
    if data["schema_version"] == 3 and not isinstance(data["operations"], list):
        raise ValidationError("Supply one operation for each reference.", "operations")
    config = data["config"]
    if not isinstance(config, dict) or set(config) != {"page_size", "virtual_pages", "physical_frames"}:
        raise ValidationError("Invalid memory configuration fields.", "config")
    if data['schema_version'] == 1 and data['policy'] == 'clock':
        raise ValidationError('CLOCK requires experiment schema version 2.', 'policy')
    if data['schema_version'] < 3 and isinstance(data['workload'], str) and ':' in data['workload']:
        raise ValidationError('Read/write references require experiment schema version 3.', 'workload')
    return make_experiment(MemoryConfig(**config), data["workload"], data["input_mode"], data["policy"],
                           data.get('tlb_capacity', 0), operations=data.get('operations'))


def compare(config, workload, input_mode="pages", policies=POLICIES, frame_counts=None, *, tlb_capacity=0, operations=None) -> tuple[ComparisonRow, ...]:
    accesses = normalize_and_validate(config, workload, input_mode, operations=operations)
    if not isinstance(policies, (tuple, list)) or not 1 <= len(policies) <= len(POLICIES) or any(p not in POLICIES for p in policies):
        raise ValidationError("Select between one and four supported policies.", "policies")
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
