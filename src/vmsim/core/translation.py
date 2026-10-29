"""Address splitting and workload normalization independent of replacement."""

from collections.abc import Sequence

from vmsim.core.models import Access, MemoryConfig
from vmsim.core.validation import ValidationError, parse_workload, require_int


def split_address(config: MemoryConfig, address: int) -> tuple[int, int]:
    require_int(address, "address", 0, config.virtual_capacity - 1)
    return divmod(address, config.page_size)


def physical_address(config: MemoryConfig, frame_id: int, offset: int) -> int:
    require_int(frame_id, "frame_id", 0, config.physical_frames - 1)
    require_int(offset, "offset", 0, config.page_size - 1)
    return frame_id * config.page_size + offset


def normalize_and_validate(
    config: MemoryConfig, workload: str | Sequence[int], input_mode: str = "pages"
) -> tuple[Access, ...]:
    values = parse_workload(workload, input_mode)
    upper = config.virtual_pages if input_mode == "pages" else config.virtual_capacity
    accesses = []
    for position, value in enumerate(values, 1):
        if value >= upper:
            raise ValidationError(f"Reference must be between 0 and {upper - 1}.", token_index=position)
        address = value * config.page_size if input_mode == "pages" else value
        page, offset = split_address(config, address)
        accesses.append(Access(value, address, page, offset))
    return tuple(accesses)
