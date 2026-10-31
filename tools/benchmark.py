"""Measure the supported upper bounds, separately from browser rendering."""

import argparse
import json
import platform
import statistics
import time
from urllib.request import Request, urlopen

from vmsim.core.engine import simulate
from vmsim.core.experiments import compare
from vmsim.core.models import MemoryConfig
from vmsim.core.policies import POLICIES
from vmsim.web.serialization import simulation_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', help='Optional running local server for HTTP measurements')
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--tlb-capacity', type=int, choices=range(33), default=0)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error('--repeats must be from 1 to 20')
    config = MemoryConfig(virtual_pages=256, physical_frames=32)
    # Deterministic mix of locality and churn; all 256 virtual pages are reachable.
    workload = [(index * 17 + index // 8) % 256 for index in range(1000)]
    def measure(label, task):
        task()  # Exclude the first warm-up run; startup is not part of this target.
        samples = []
        for _ in range(args.repeats):
            start = time.perf_counter()
            task()
            samples.append(time.perf_counter() - start)
        return {'case': label, 'median_seconds': statistics.median(samples), 'max_seconds': max(samples)}
    results = [measure(f'{policy}: engine + JSON, 1000 references / 32 frames',
                       lambda policy=policy: json.dumps(simulation_payload(simulate(config, workload, policy=policy, tlb_capacity=args.tlb_capacity)), allow_nan=False))
               for policy in POLICIES]
    results.append(measure('engine: 4 policies × frames 1–32 × 1000 references',
                           lambda: compare(config, workload, frame_counts=list(range(1, 33)), tlb_capacity=args.tlb_capacity)))
    if args.url:
        def post(path, payload):
            request = Request(args.url.rstrip('/') + path, json.dumps(payload).encode(), {'Content-Type': 'application/json'})
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        base = {'config': {'page_size': 4096, 'virtual_pages': 256, 'physical_frames': 32}, 'workload': workload, 'tlb_capacity': args.tlb_capacity}
        results.append(measure('HTTP simulate Optimal: compute, validation, serialization, transfer', lambda: post('/api/simulate', {**base, 'policy': 'optimal'})))
        results.append(measure('HTTP compare: 128 fresh runs', lambda: post('/api/compare', {**base, 'frame_counts': list(range(1, 33))})))
    print(json.dumps({'platform': platform.platform(), 'python': platform.python_version(), 'tlb_capacity': args.tlb_capacity, 'repeats': args.repeats, 'measurements': results}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
