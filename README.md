# VM Lab — Virtual Memory Simulator

A Linux-first university OS project with a **Python simulation engine/backend** and a **React + JavaScript interface**. React components use JSX. It is an educational model, not a replacement for the host operating system's memory manager.

Configure memory, simulate FIFO/LRU/Optimal/CLOCK, inspect each address and replacement, compare frame counts, and save experiments/results as JSON/CSV. The packaged app runs through one local Python server with all frontend assets included. See verification scope below for tested environments and the remaining native Linux desktop browser check.

Use the engine independently of the web server:

```python
from vmsim.core.engine import simulate
from vmsim.core.models import MemoryConfig

result = simulate(MemoryConfig(physical_frames=3), "1,2,3,1,4,2,5", policy="fifo")
print(result.metrics.faults)  # 5
print(result.events[-1].reason)
```

Input mode is `pages` (default) or `addresses`; address text also accepts `0x` hexadecimal values. Policies are `fifo`, `lru`, `optimal`, and `clock`. Optimal uses the complete fixed workload as an offline benchmark. Initial state is empty; frames/pages are numbered from zero; event steps start at one. Faults include free-frame loads, while replacements count actual evictions only.

## Interactive simulator

1. Choose page size, virtual-page count, physical frames, and replacement policy. Page/frame IDs start at zero. The configuration shows virtual address space separately from physical capacity.
2. Choose page numbers or virtual byte addresses, then enter comma/whitespace-separated references. **Load example** fills a suitable example for the selected input mode and resets memory sizes to the defaults.
3. Select **Run simulation** to calculate the complete trace. Playback starts at step 0 with empty frames; select **Next** to perform one reference or **Play** to advance automatically.
4. Use **Previous**, the timeline, or a history-step link to revisit a saved state. **Reset** returns to step 0 while retaining the same experiment. Speed ranges from 0.5× to 4×; autoplay stops at the final step or when the page becomes hidden.
5. Inspect the selected reference's address calculation, frame highlights, page table, replacement explanation, and policy metadata. The main counters/rates belong to the selected step. **Run totals** are labeled separately and always describe the complete workload. Initial rates are unavailable until a reference completes.

Editing any setting or loading an example stops playback, cancels pending work, and clears the old trace. Run again to apply the new experiment. Validation failures preserve the editor contents; a pending request can be canceled, and obsolete responses cannot overwrite a newer run. Requests time out after 15 seconds with a retryable error.

The page table scrolls within its panel for large address spaces. Reference history renders at most 12 completed rows; the timeline can reach every step in a 1,000-reference trace. Controls support keyboard navigation and show hits, loads, and evictions with text as well as color.

## Comparison and files

Select **Compare**, choose an inclusive frame range (1–32), then **Compare**. Each FIFO/LRU/Optimal/CLOCK run starts empty. The table and SVG chart show returned fault counts; a FIFO increase is called out as Belady's anomaly. **Belady preset** loads the classic workload and the 3–4 frame sweep (FIFO: 9 then 10 faults). Editing settings or the sweep clears obsolete results. Changing views pauses playback.

**Export CSV** saves every comparison row with raw counts and unrounded fractional rates. **Save JSON** validates and downloads the current experiment; **Load JSON** validates a UTF-8 file up to 128 KiB and restores configuration, input mode, policy, and references. Run again to reproduce its trace. Invalid files and duplicate JSON keys are rejected without changing the editor. CSV contains results; JSON contains reproducible inputs, rather than playback position or comparison range.

## CLOCK replacement

**CLOCK · Second chance** maintains a circular hand and one reference bit per occupied frame. Loads and all page hits (including TLB hits) set the frame's bit. A replacement scans from the hand: clear set bits and advance; evict the first frame with bit 0. After loading, move the hand to the next frame, wrapping at the frame count. Free frames still use the lowest ID. The saved policy state displays the hand, bits, and scan explanation; backward playback restores them together.

CLOCK approximates recency and is distinct from exact LRU. It is an online teaching policy, not a claim about Linux reclaim. All four policies are included in comparison sweeps (up to 128 fresh runs). `examples/clock.json` demonstrates a complete scan and second chances with TLB enabled. The Belady workload produces CLOCK faults 9 and 10 at three and four frames, respectively.

## Seeded workloads

Expand **Generate references**, choose a seed (0–4294967295), count (1–1000), and profile, then select **Generate workload**. This replaces the editor and clears its previous trace. It uses the configured virtual pages and input mode; addresses preserve the same generated page sequence with independently seeded byte offsets.

- **Uniform:** independent draws across the virtual page range.
- **Sequential:** cycle through pages from a seeded starting point, wrapping at the end.
- **Locality:** 80% of draws favor a contiguous hot set of up to four pages, relocated every 32 references; the rest draw from the whole range.

The recipes use private seeded RNG streams, with no global or time-based state. The same seed and settings reproduce the same references on the tested Python versions. JSON exports store the resulting list, so replay does not depend on rerunning a generator. These are synthetic teaching workloads, not samples of real Linux memory traffic.

`POST /api/workloads/generate` accepts `config`, `seed`, `length`, `profile`, and `input_mode`, and returns the normalized recipe and workload.

## Translation cache (TLB)

Set **Translation cache (TLB)** to 1–32 entries, or leave it **Disabled**. This is a fully associative simulated cache with fixed LRU replacement, separate from the page-replacement policy. Playback shows cached page/frame mappings from least to most recent and the selected step's TLB hits/misses. A TLB miss can still be a page hit; only a nonresident page faults. Memory evictions invalidate cached mappings before a frame is reused. Hits through the TLB still update memory-policy recency.

The TLB starts empty on every run. Its capacity may exceed the physical frame count. It never changes page-fault/replacement decisions for the same workload and memory policy. Comparison and CSV include separate cache counters when enabled; no hardware timing formula is implied. Send `tlb_capacity: 0` (disabled, default) or an integer 1–32 to the simulation, comparison, and experiment-export APIs.

New experiment exports use **schema version 2**, including `tlb_capacity`. Version 1 files remain importable and explicitly mean TLB disabled. Import normalizes them to version 2. Trace/comparison responses retain schema version 1 with additive TLB fields: per-state/final `tlb` (null when disabled), `tlb_capacity`, and per-event `tlb_result` (hit/miss/null).

## Simulation API

Run the local server, then send JSON to these routes:

| Route | Purpose |
| --- | --- |
| `GET /api/health` | Application version and frontend readiness |
| `POST /api/simulate` | Full initial state, immutable events, and final metrics |
| `POST /api/compare` | Fresh summary runs for each policy/frame-count pair |
| `POST /api/workloads/generate` | Reproducible uniform, sequential, or locality references |
| `POST /api/experiments/export` | Download a canonical schema-version-2 experiment |
| `POST /api/experiments/import` | Validate and normalize a complete versioned experiment |

Example simulation request:

```json
{
  "config": {"page_size": 4096, "virtual_pages": 8, "physical_frames": 3},
  "workload": "1,2,3,1,4,2,5",
  "input_mode": "pages",
  "policy": "fifo"
}
```

For comparison, replace `policy` with `policies: ["fifo", "lru", "optimal", "clock"]` and optionally add `frame_counts: [3, 4]`. Default configuration is 4096-byte pages, 8 virtual pages, and 3 frames. Comparison defaults to all four policies and the configured frame count. Each pair starts empty; summary runs do not retain detailed event histories.

Workload may be text or an integer array. Limits: 1–1000 references; 1–256 virtual pages; 1–32 frames; power-of-two page sizes from 256 to 65536 bytes; at most 32 distinct frame counts. Request bodies are limited to 128 KiB, including requests without Content-Length. Invalid fields/references return HTTP 422 with `errors` containing `field`, `message`, and optional one-based `token_index`; oversized requests return 413. Unknown fields and numeric coercion are rejected. Empty comma-separated references are invalid.

Response schema version is 1. Config responses include byte capacities and offset bits. Each event contains the input value, split address, hit/fault result, resolved physical address, optional victim, reason, frame state, policy metadata, and cumulative metrics. Snapshot `resident_pages` lists only resident mappings; all other virtual pages are nonresident. FIFO/LRU `order` lists frame IDs from oldest to newest; LRU `last_access` and Optimal `next_use` use one-based access steps. A null Optimal next use means never used again. Zero-reference rates in the initial state are null.

The JavaScript client in `frontend/src/api/client.js` provides `getHealth`, `simulateExperiment`, `compareAlgorithms`, `generateWorkload`, `exportExperiment`, and `importExperiment`, with an optional AbortSignal. It validates response structure and consistency and exposes structured HTTP failures as `ApiError`. Python API tests keep shared JSON fixtures synchronized with the JavaScript contract tests.

Example files in `examples/` cover FIFO, Belady's anomaly, address offsets, TLB caching, and CLOCK. To run a saved experiment without HTTP:

```python
from pathlib import Path
from vmsim.core.experiments import load_experiment

experiment = load_experiment(Path("examples/translation.json").read_text(encoding="utf-8"))
result = simulate(
    experiment.config, experiment.workload, experiment.input_mode, experiment.policy,
    tlb_capacity=experiment.tlb_capacity,
)
```

`dump_experiment` serializes validated experiments for repeatable JSON round-trips. Experiment files require schema_version, all three config values, workload, input_mode, and policy; version 2 additionally requires tlb_capacity. CLOCK experiments use version 2. Import validation does not execute a simulation.

## Requirements

- Python 3.12 or 3.13 (the initial test matrix).
- For frontend development/builds: Node **22.23.2** (pinned in `frontend/.nvmrc`) and npm. The frontend enforces its supported Node range.
- A modern browser. Linux is the primary target; Windows is also supported.
- Internet for initial dependency installation. The built application uses local assets at runtime.

On Ubuntu, if Python's venv support is missing, install it once with your package manager (`sudo apt install python3-venv`). Running the project itself does not require root.

## First setup on Linux

Run from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
npm --prefix frontend ci
```

Use a Node version manager to select the version in `frontend/.nvmrc` if your distribution's Node is older. Do not share a virtual environment or `node_modules` directory between Linux and Windows; each has platform-specific dependencies. For WSL development, use a separate Linux checkout/directory and create its own environment there.

On Windows PowerShell, replace `python3` with `python`, and `.venv/bin/python` with `.venv\Scripts\python.exe`. The npm commands are the same. Explicit executable paths avoid virtual-environment activation and PowerShell execution-policy changes.

## Development — two terminals

Backend:

```bash
.venv/bin/python -m uvicorn vmsim.web.app:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```bash
npm --prefix frontend run dev
```

Open **http://127.0.0.1:5173**. Vite proxies `/api` to `http://127.0.0.1:8000`; no CORS configuration is needed. The home page checks the real backend and allows retrying a failed connection. Both development servers bind locally. Stop each with Ctrl+C.

The API remains usable before building the frontend: `GET /api/health`. Opening the Python server's root before staging assets returns an actionable 503 response; use Vite while developing.

## Build and run — one Python server

```bash
npm --prefix frontend run build
.venv/bin/python tools/stage_frontend.py
.venv/bin/python -m vmsim
```

Open **http://127.0.0.1:8000**. This serves the compiled React application and API from Python. Node/Vite need not be running. The server prints its URL and works from any current directory after installation.

To select another port, use `python -m vmsim --port 8001` with your environment's Python. If the selected port is already occupied, the launcher reports the problem and suggests another port. Stop with Ctrl+C.

Generated directories (`frontend/dist/`, `src/vmsim/web/static/`, `build/`, `dist/`) are ignored in Git. Rebuild and stage before producing a release. Keep all hand-authored frontend files in `frontend/src/`.

## Checks

```bash
.venv/bin/python -m pytest
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

Vite builds the JavaScript/JSX frontend. Backend tests cover algorithms, translation, validation, HTTP contracts, JSON round-trips, concurrency, and packaging foundations. React tests cover connection handling, runtime API validation, selected-step rendering, playback boundaries/speed, Strict Mode timer cleanup, bounded history, duplicate submissions, cancellation, stale responses, and timeouts. API responses are validated at runtime before the UI uses them.

## Build and verify an installable release

After building and staging the frontend:

```bash
.venv/bin/python -m build --no-isolation
python3 -m venv .venv-release
.venv-release/bin/python -m pip install -r requirements.txt
.venv-release/bin/python -m pip install --no-deps dist/vmsim_os-0.1.0-py3-none-any.whl
.venv-release/bin/python tools/smoke_release.py
```

The smoke tool launches the installed package from an unrelated temporary directory, checks the API, HTML, and compiled assets over real HTTP, and shuts the server down. It rejects editable/source imports. It needs no Node process. Distribute the wheel and `requirements.txt`; install them into a fresh virtual environment and run that environment's `python -m vmsim`. Example JSON files and frontend contract fixtures are included in the source archive.

Rehearse both distributions in disposable, fresh virtual environments:

```bash
.venv/bin/python tools/verify_release.py --wheel dist/vmsim_os-0.1.0-py3-none-any.whl --source dist/vmsim_os-0.1.0.tar.gz
```

This checks archive contents, installs the pinned requirements and each distribution, and runs the installed-package smoke check. Initial installation needs internet or a populated pip cache. During the smoke check, outbound socket connections are blocked in the server child only; its HTTP API and local React assets must still work. Machine networking is unchanged. Source archives include staged assets, so installing either distribution needs no Node runtime. Rebuilding edited frontend source still needs Node.

## Verification scope and model limits

Recorded on 31 October 2026: Ubuntu 24.04.3 x86-64 under WSL2 (kernel 5.15.167.4, Python 3.12.3) and Windows 11 (Python 3.13.1); Node 22.23.2 for builds. Both platforms passed 142 Python tests, 52 JavaScript tests, production builds, and fresh wheel/source installations. Linux shutdown with SIGINT exits cleanly. Browser checks verified real JSON/CSV downloads, restored address-mode settings, replay, and Belady's anomaly. Chromium 156.0.8078.4 rendered the application under WSLg. The full Firefox/Chromium desktop demo has not yet been completed on an independent Linux desktop/VM; do not treat WSL API/build tests as that check.

Measure the bounded workload on your demo machine, with the server running:

```bash
.venv/bin/python tools/benchmark.py --url http://127.0.0.1:8000
```

The script uses 1,000 references, 256 virtual pages, 32 frames, and a sweep of all 128 policy/frame pairs. It reports warmed repetitions (default five) with median and maximum times, separating engine/JSON work from HTTP. On 31 October, three measured repetitions with `--tlb-capacity 32` gave HTTP Optimal median **0.64 seconds** (max 0.72) and the full four-policy comparison median **2.03 seconds** (max 2.63). Engine + JSON medians were 0.12/0.13/0.11/0.15 seconds for FIFO/LRU/Optimal/CLOCK. These are reference-machine measurements, not guarantees under contention. Browser rendering/control latency is excluded.

The model uses one process, a flat page table, and successful abstract page loads. It does not manipulate Linux memory, access swap, emulate dirty writeback/permissions/multilevel paging, or measure hardware timing. LRU is exact simulated recency; Optimal uses future knowledge. TLB, CLOCK, and seeded synthetic workloads are optional teaching extensions, now included. No hardware timing or effective-access-time model is claimed.

Suggested 5–7 minute demo: run the default FIFO workload (5 faults, 2 hits); inspect a load, hit, and replacement; step backward/reset/replay; use address inputs `4096,8300,4097` to explain offsets; compare all policies; load Belady's preset (FIFO 9→10 faults for 3→4 frames); export CSV and save/load JSON. Repeat this flow in Firefox and Chromium on the target Linux desktop, check keyboard controls/narrow screens, and stop the server with Ctrl+C.

`requirements.txt` contains pinned runtime dependencies; `requirements-dev.txt` additionally pins test/build/locking tools. `package-lock.json` locks the frontend. After intentionally changing Python dependencies, regenerate both locks and test on Linux and Windows:

```bash
.venv/bin/python -m piptools compile --strip-extras --no-emit-index-url -o requirements.txt requirements.in
.venv/bin/python -m piptools compile --allow-unsafe --strip-extras --no-emit-index-url -o requirements-dev.txt requirements-dev.in
```

Keep direct Python dependencies in `requirements.in` and `pyproject.toml` synchronized. Build with the locked development environment using `--no-isolation`.

## Layout

```text
src/vmsim/core/          Memory, translation, policies, comparisons, experiment files
src/vmsim/web/           FastAPI adapter and generated frontend assets
frontend/src/           JavaScript/JSX React UI, API client, and frontend tests
examples/               Versioned, reproducible experiment workloads
tests/                  Python tests
tools/                  Cross-platform staging and release verification
```

Planning notes, screenshots, and repository instructions are kept locally and ignored by Git. The `docs/` and `doc/` folders are excluded from version control and release packages. `README.md` is the only Markdown file included in version control.

