"""Input rules shared by the engine and HTTP adapter; standard library only."""

import re
from collections.abc import Sequence

MAX_REFERENCES = 1000
MAX_WORKLOAD_CHARS = 65536


class ValidationError(ValueError):
    def __init__(self, message: str, field: str = "workload", token_index: int | None = None):
        super().__init__(message)
        self.field = field
        self.token_index = token_index


def require_int(value: object, field: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValidationError(f"Must be an integer between {minimum} and {maximum}.", field)
    return value


def parse_workload(workload: str | Sequence[int], input_mode: str) -> tuple[int, ...]:
    if input_mode not in ("pages", "addresses"):
        raise ValidationError("Choose pages or addresses.", "input_mode")
    if isinstance(workload, str):
        if len(workload) > MAX_WORKLOAD_CHARS:
            raise ValidationError(f"Workload text must not exceed {MAX_WORKLOAD_CHARS} characters.")
        if not workload.strip():
            raise ValidationError("Enter at least one reference.")
        tokens = []
        for segment in workload.split(","):
            if not segment.strip():
                raise ValidationError("Empty reference between commas.", token_index=len(tokens) + 1)
            tokens.extend(segment.split())
        if len(tokens) > MAX_REFERENCES:
            raise ValidationError(f"At most {MAX_REFERENCES} references are supported.")
        values = []
        for position, token in enumerate(tokens, 1):
            decimal = re.fullmatch(r"[0-9]+", token)
            hexadecimal = input_mode == "addresses" and re.fullmatch(r"0[xX][0-9a-fA-F]+", token)
            if len(token) > 64 or not (decimal or hexadecimal):
                raise ValidationError("Expected a nonnegative decimal integer" + (" or 0x hexadecimal address." if input_mode == "addresses" else "."), token_index=position)
            values.append(int(token, 16 if hexadecimal else 10))
        return tuple(values)
    if not isinstance(workload, (list, tuple)):
        raise ValidationError("Workload must be text or an array of integers.")
    if not 1 <= len(workload) <= MAX_REFERENCES:
        raise ValidationError(f"Supply between 1 and {MAX_REFERENCES} references.")
    for position, value in enumerate(workload, 1):
        if type(value) is not int or value < 0:
            raise ValidationError("Expected a nonnegative integer.", token_index=position)
    return tuple(workload)
