# VM Lab — Virtual Memory Simulator

A Linux-first university OS project with a **Python simulation engine/backend** and a **React + JavaScript interface**. React components use JSX. It is an educational model, not a replacement for the host operating system's memory manager.

**Current milestone: Phase 5.** The simulator includes FIFO/LRU/Optimal playback, address translation, frame/page-table visualization, fresh-run comparison sweeps, local SVG charts, Belady's anomaly, and JSON/CSV files.

Use the engine independently of the web server:

```python
from vmsim.core.engine import simulate
from vmsim.core.models import MemoryConfig

result = simulate(MemoryConfig(physical_frames=3), "1,2,3,1,4,2,5", policy="fifo")
print(result.metrics.faults)  # 5
print(result.events[-1].reason)
```

Input mode is `pages` (default) or `addresses`; address text also accepts `0x` hexadecimal values. Policies are `fifo`, `lru`, and `optimal`. Optimal uses the complete fixed workload as an offline benchmark. Initial state is empty; frames/pages are numbered from zero; event steps start at one. Faults include free-frame loads, while replacements count actual evictions only.

## Interactive simulator

1. Choose page size, virtual-page count, physical frames, and replacement policy. Page/frame IDs start at zero. The configuration shows virtual address space separately from physical capacity.
2. Choose page numbers or virtual byte addresses, then enter comma/whitespace-separated references. **Load example** fills a suitable example for the selected input mode and resets memory sizes to the defaults.
3. Select **Run simulation** to calculate the complete trace. Playback starts at step 0 with empty frames; select **Next** to perform one reference or **Play** to advance automatically.
4. Use **Previous**, the timeline, or a history-step link to revisit a saved state. **Reset** returns to step 0 while retaining the same experiment. Speed ranges from 0.5× to 4×; autoplay stops at the final step or when the page becomes hidden.
5. Inspect the selected reference's address calculation, frame highlights, page table, replacement explanation, and policy metadata. The main counters/rates belong to the selected step. **Run totals** are labeled separately and always describe the complete workload. Initial rates are unavailable until a reference completes.

Editing any setting or loading an example stops playback, cancels pending work, and clears the old trace. Run again to apply the new experiment. Validation failures preserve the editor contents; a pending request can be canceled, and obsolete responses cannot overwrite a newer run. Requests time out after 15 seconds with a retryable error.

The page table scrolls within its panel for large address spaces. Reference history renders at most 12 completed rows; the timeline can reach every step in a 1,000-reference trace. Controls support keyboard navigation and show hits, loads, and evictions with text as well as color.

## Comparison and files

Select **Compare**, choose an inclusive frame range (1–32), then **Compare**. Each FIFO/LRU/Optimal run starts empty. The table and SVG chart show returned fault counts; a FIFO increase is called out as Belady's anomaly. **Belady preset** loads the classic workload and the 3–4 frame sweep (FIFO: 9 then 10 faults). Editing settings or the sweep clears obsolete results. Changing views pauses playback.

**Export CSV** saves every comparison row with raw counts and unrounded fractional rates. **Save JSON** validates and downloads the current experiment; **Load JSON** validates a file up to 128 KiB and restores configuration, input mode, policy, and references. Run again to reproduce its trace. Invalid files preserve the editor. CSV contains results; JSON contains reproducible inputs, rather than playback position or comparison range.

## Simulation API

Run the local server, then send JSON to these routes:

| Route | Purpose |
| --- | --- |
| `GET /api/health` | Application/phase and frontend readiness |
| `POST /api/simulate` | Full initial state, immutable events, and final metrics |
| `POST /api/compare` | Fresh summary runs for each policy/frame-count pair |
| `POST /api/experiments/export` | Download a canonical schema-version-1 experiment |
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

For comparison, replace `policy` with `policies: ["fifo", "lru", "optimal"]` and optionally add `frame_counts: [3, 4]`. Default configuration is 4096-byte pages, 8 virtual pages, and 3 frames. Comparison defaults to all three policies and the configured frame count. Each pair starts empty; summary runs do not retain detailed event histories.

Workload may be text or an integer array. Limits: 1–1000 references; 1–256 virtual pages; 1–32 frames; power-of-two page sizes from 256 to 65536 bytes; at most 32 distinct frame counts. Request bodies are limited to 128 KiB, including requests without Content-Length. Invalid fields/references return HTTP 422 with `errors` containing `field`, `message`, and optional one-based `token_index`; oversized requests return 413. Unknown fields and numeric coercion are rejected. Empty comma-separated references are invalid.

Response schema version is 1. Config responses include byte capacities and offset bits. Each event contains the input value, split address, hit/fault result, resolved physical address, optional victim, reason, frame state, policy metadata, and cumulative metrics. Snapshot `resident_pages` lists only resident mappings; all other virtual pages are nonresident. FIFO/LRU `order` lists frame IDs from oldest to newest; LRU `last_access` and Optimal `next_use` use one-based access steps. A null Optimal next use means never used again. Zero-reference rates in the initial state are null.

The JavaScript client in `frontend/src/api/client.js` provides `simulateExperiment`, `compareAlgorithms`, `exportExperiment`, and `importExperiment`, with an optional AbortSignal. It validates response structure and consistency and exposes structured HTTP failures as `ApiError`. Python API tests keep shared JSON fixtures synchronized with the JavaScript contract tests.

Example files in `examples/` cover FIFO, Belady's anomaly, and address offsets. To run a saved experiment without HTTP:

```python
from pathlib import Path
from vmsim.core.experiments import load_experiment

experiment = load_experiment(Path("examples/translation.json").read_text())
result = simulate(experiment.config, experiment.workload, experiment.input_mode, experiment.policy)
```

`dump_experiment` serializes validated experiments for repeatable JSON round-trips. Experiment files require schema_version, all three config values, workload, input_mode, and policy. Import validation does not execute a simulation.

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

