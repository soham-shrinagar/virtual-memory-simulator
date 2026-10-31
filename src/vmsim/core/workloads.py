"""Deterministic synthetic workloads; unrelated to host memory measurements."""

from random import Random

from vmsim.core.models import MemoryConfig
from vmsim.core.validation import MAX_REFERENCES, ValidationError, require_int

PROFILES = ('uniform', 'sequential', 'locality')


def generate_workload(config: MemoryConfig, seed=42, length=100, profile='locality', input_mode='pages'):
    require_int(seed, 'seed', 0, 2**32 - 1)
    require_int(length, 'length', 1, MAX_REFERENCES)
    if profile not in PROFILES:
        raise ValidationError('Choose uniform, sequential, or locality.', 'profile')
    if input_mode not in ('pages', 'addresses'):
        raise ValidationError('Choose pages or addresses.', 'input_mode')
    # random() has a stable seeded sequence. Avoid global RNG state and give
    # offsets their own stream so both modes use the same page-reference sequence.
    rng = Random(seed)
    def choose(bound):
        return int(rng.random() * bound)

    start = choose(config.virtual_pages)
    hot_size = min(4, config.virtual_pages)
    pages = []
    for index in range(length):
        if profile == 'uniform':
            page = choose(config.virtual_pages)
        elif profile == 'sequential':
            page = (start + index) % config.virtual_pages
        else:
            if index % 32 == 0:
                hot_start = choose(config.virtual_pages - hot_size + 1)
            page = hot_start + choose(hot_size) if rng.random() < .8 else choose(config.virtual_pages)
        pages.append(page)
    if input_mode == 'pages':
        return tuple(pages)
    offsets = Random(seed ^ 0x9E3779B9)
    return tuple(page * config.page_size + int(offsets.random() * config.page_size) for page in pages)
