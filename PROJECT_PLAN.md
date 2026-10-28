# Virtual Memory Simulator — reviewed specification and implementation plan

Prepared for the university OS project, 28 October 2026.

**Implementation status:** Phase 0 is complete. Python/React scaffolding, dependency locks, development proxy, packaging, and smoke tests pass on Ubuntu 24.04 via WSL2 and on Windows. See [Phase 0 verification](docs/PHASE_0.md). Phase 1 is next.

## 1. Review outcome

The proposed project is academically useful and feasible as a focused 2–3 week project. Its address-translation example, FIFO execution table, algorithm descriptions, and basic hit/fault formulas are correct. The important work before implementation is to specify the behavior between those components so that the engine, interface, and reports agree.

**Project objective:** Build a deterministic, single-process, demand-paging simulator that explains virtual-to-physical address translation, demonstrates FIFO/LRU/Optimal replacement, and compares their page-fault behavior. It must install and run reliably on Linux; Windows is a secondary target.

This is a teaching model running on Linux, not a reproduction of Linux's actual memory manager or reclaim policy. Linux uses architecture-dependent hierarchical page tables and handles several kinds of page fault; this project deliberately uses a flat table and only simulated nonresident-page faults. [Linux page-table documentation](https://docs.kernel.org/mm/page_tables.html)

Confirmed technology decisions: use **Python for the simulation engine and backend**, and **React for the browser interface**. No C/C++ implementation is planned. Use TypeScript with React as the frontend default so simulation events and component props have explicit types. The remaining planning assumptions are that the course accepts this stack and roughly 15 working days are available; confirm submission requirements at the beginning of Phase 0.

## 2. Gaps in the description and their fixes

| Gap or risk | Agreed behavior for this project |
| --- | --- |
| Page reference strings and virtual byte addresses are mixed together. | Provide two explicit input modes: **page numbers** and **virtual byte addresses**. Normalize both into the same internal access format. Never guess the mode from the numbers. |
| A page fault can be mistaken for an eviction. | A nonresident access causes one fault. An eviction/replacement occurs only if no free frame exists. Loading into a free frame is a fault without a replacement. |
| A TLB miss can be mistaken for a page fault. | A TLB miss leads to a page-table lookup. If the page is resident, the access is still a page hit. Keep translation-cache counters separate from residency counters. |
| The source uses zero-based pages but labels frames starting at 1. | Use zero-based page and frame IDs everywhere: P0, P1, F0, F1. Human-facing access numbers start at 1. |
| The initial memory state is not fully specified. | Each new run starts with empty frames, nonresident page-table entries, empty policy metadata, zero counters, and an empty TLB when enabled. |
| The backing-store model is unspecified. | Every in-range virtual page is valid and can be made resident by a successful abstract page load. No disk files, simulated data contents, I/O failures, or measured disk latency in the core project. |
| Backward stepping might undo visible frames but leave policy metadata incorrect. | Compute a complete immutable trace, including the initial state, and navigate it with a playback cursor. Going backward changes the displayed state, not the completed simulation. |
| The original layer diagram could allow policies to duplicate mapping and fault logic. | One engine owns page tables, frames, counters, and events. Policies choose victims and maintain only their own selection metadata. |
| Equal victim scores are unspecified. | Allocate the lowest-numbered free frame. For equal victim scores, choose the lowest frame ID. This matters especially when several OPT candidates are never used again. |
| Mid-run edits and Optimal's knowledge of the future are unspecified. | A run has a fixed complete workload. Editing workload/configuration stops playback and requires a new run. OPT is explicitly labeled an offline theoretical benchmark. |
| “Performance” might imply real hardware measurements. | Compare fault counts/rates and replacements. Do not present animation time, Python execution time, or assumed disk delays as actual Linux memory-access performance. |
| Linux support is an intention without an acceptance test. | Start Linux verification in Phase 0 and repeat at each milestone. Release requires a fresh-environment Linux installation and real Linux browser checks. |

TLB/cache behavior and fault handling have more detail in real hardware and Linux; the interface must identify the simplified model. [Linux MMU, TLB, and page faults](https://docs.kernel.org/mm/page_tables.html)

## 3. Scope and priorities

### Required submission

- Validated memory configuration and both workload input modes.
- FIFO, exact simulated LRU, and Optimal replacement implemented by the team.
- Page-table/frame visualization and correct address translation after fault resolution.
- Next, Previous, Play, Pause, Reset, and playback speed controls.
- A reason for each hit, load, and eviction; visible policy metadata.
- Algorithm comparison on identical workloads, plus a frame-count sweep.
- Built-in example workloads, including Belady's anomaly.
- JSON experiment save/load and CSV results export.
- Automated engine tests, Linux installation/run instructions, and a short project report.

### Optional, only after the required version passes

1. Fully associative simulated TLB with a fixed LRU replacement policy.
2. Seeded synthetic workload generation for locality experiments.
3. CLOCK as a fourth replacement policy, if there is time to explain and test it properly.

Keep actual kernel integration, swap files, process isolation, multiple processes, dirty-page writeback, permission faults, multi-level paging, and hardware timing outside the submitted core scope. They materially increase the model and testing burden.

## 4. Selected technology and Linux strategy

| Part | Choice | Reason |
| --- | --- | --- |
| Simulation engine | Python, standard library only | Easy to inspect, deterministic, and independently testable; sufficient for the bounded educational workloads. |
| Local API/application server | FastAPI + Uvicorn | Typed input validation and one local process serving both the API and interface. |
| Interface | React + TypeScript, built with Vite; CSS for styling | Reusable visualization components and typed simulation data, with a small frontend toolchain. |
| Frontend state | React state/reducer and a playback hook | Keep the active experiment, immutable trace, playback cursor, and timer lifecycle explicit. |
| Charts | SVG rendered by React | Small fault-count charts without an external chart service or CDN. |
| Tests | pytest + HTTP test client; Vitest + React Testing Library for critical UI behavior | Verify algorithm decisions, API contracts, playback state, and error handling. |
| Storage | JSON files and CSV downloads | Reproducible experiments without a database. |

Use Python 3.12 and 3.13 as the initial tested interpreter matrix. Make Ubuntu 24.04 LTS x86-64 the primary reference environment. Test Firefox and Chromium on Linux; add another Linux distribution only if time permits. Record exact tested OS, Python, browser, and dependency versions in the release notes.

React's documentation supports a Vite-based application built from scratch, which fits a browser client backed by a separate Python API. The Phase 0 build baseline is Node **22.23.2**, pinned in `frontend/.nvmrc` and compatible with the selected Vite/test dependencies. Commit `package-lock.json` and use `npm ci` for reproducible frontend installs. [React application setup](https://react.dev/learn/build-a-react-app-from-scratch), [Vite prerequisites](https://vite.dev/guide/)

Development uses a Vite frontend server and a Python API server, with frontend `/api` requests proxied to Python. The submitted release uses the compiled React assets served by FastAPI, so it needs only one Python server process and no Node runtime. Include those compiled assets in the release package. [Vite production builds](https://vite.dev/guide/build), [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/)

Uvicorn binds to `127.0.0.1`; local execution is sufficient for this project. [Uvicorn settings](https://uvicorn.dev/settings/)

Linux reliability rules:

- Install into a project virtual environment; do not require root to run or use system-wide pip installation. A machine missing Python/venv may need one-time distro package setup, documented separately.
- Pin the dependency set tested for the release. Keep application dependencies separate from development/test dependencies.
- Keep Node/npm as development and build dependencies. Provide a release package containing the built frontend so a Linux demo does not depend on running Vite or downloading npm packages.
- Serve all interface assets locally, including fonts/icons if any. After dependencies are installed, the simulator must run without internet access.
- Bind locally by default. Print the URL even if automatic browser opening fails; provide a configurable port and a readable port-conflict error.
- Resolve application assets relative to the installed package, not the shell's working directory. Use `pathlib` and case-correct filenames.
- Use one application process in the submitted release and ordinary HTTP requests. Two development servers are acceptable. Playback happens in React; it does not require server-side sleeps, WebSockets, or background jobs.
- Start headless engine/API tests on Linux immediately. WSL2 is useful during development from Windows; verify the final interface in a native Linux desktop or Linux VM with a browser.
- Keep a single cross-platform Python entry point; optional `.sh`/`.ps1` files should be convenience wrappers only.

Python virtual environments use different executable paths on Linux and Windows and should be recreated on each target machine. [Python venv documentation](https://docs.python.org/3/library/venv.html)

Planned developer commands once Phase 0 creates packaging and dependency files:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pytest
npm --prefix frontend ci
npm --prefix frontend run test -- --run
npm --prefix frontend run build
.venv/bin/python tools/stage_frontend.py
.venv/bin/python -m vmsim
```

The planned staging helper copies `frontend/dist/` into the Python package's generated static-assets directory. Configure package data so built assets are included in the distributable; verify that the installed application serves them outside the source tree. For active frontend development, use `npm --prefix frontend run dev` alongside the API server.

On Windows, use `python` to create the environment and `.venv\Scripts\python.exe` for subsequent Python commands. The user installation guide will use the runtime requirements file and packaged frontend, without test dependencies or Node. Document building from source separately. Verify both workflows in fresh environments before delivery.

## 5. Precise simulation rules

### Configuration and input

Use `P` for page size in bytes, `V` for virtual-page count, `F` for physical-frame count, and `N` for references. Suggested default: `P=4096`, `V=8`, `F=3`.

Initial product limits, chosen to bound work rather than describe real hardware:

- Page size: power of two from 256 through 65,536 bytes; offer common presets.
- Virtual pages: 1 through 256.
- Physical frames: 1 through 32. `F > V` is allowed; extra frames simply remain unused.
- Workload: 1 through 1,000 references per submitted run.
- Frame sweep: at most 32 selected frame counts within the same supported range.
- At most three required policies in one comparison. Reject oversized requests on the server, with the same limits explained in the UI.

Page mode accepts comma/whitespace-separated decimal page IDs with `0 <= page < V`; normalize each to address `page * P`, with offset zero. Address mode accepts decimal or explicitly prefixed `0x` hexadecimal byte addresses with `0 <= address < V * P`. One reference means one byte access; accesses spanning page boundaries are outside scope. Reject negative values, fractions, malformed tokens, and out-of-range values with their token positions. Ignore separator whitespace; do not silently discard malformed values.

Validate the complete workload before simulation; no partially accepted runs. An empty editor is a valid idle UI state, but Run requires at least one reference.

Derived quantities:

```text
virtual address space = V * P bytes
simulated frame capacity = F * P bytes
VPN, offset = divmod(virtual_address, P)
physical_address = frame_id * P + offset
```

For power-of-two page sizes, show `log2(P)` offset bits. If `V` is not a power of two, some values in the padded VPN bit field are invalid; the numeric range check still applies. Simulated frame capacity excludes the bookkeeping memory used by page tables and the simulator itself.

### One reference, in order

1. Take the next normalized address and compute its VPN and offset.
2. If enabled, look in the TLB; otherwise go directly to the page table.
3. If resident, record one page hit and find its mapped frame.
4. If nonresident, record one page fault. Allocate the lowest free frame, or ask the selected policy for a victim frame if full.
5. On eviction, remove the victim's mapping, invalidate its TLB entry if enabled, and increment replacements once. Record the victim and selection reason.
6. Install the incoming page in the chosen frame and update its page-table mapping.
7. Update policy metadata for the completed reference, including hits reached through the TLB. Fill/update the TLB if enabled.
8. Compute the physical address using the resolved mapping, then emit the completed event/state and cumulative counters.

Each reference counts exactly once. A reference that faults and is then resolved remains a fault in the statistics; do not count the resolution/retry as an additional reference or page hit. Initial state is step 0; the first completed reference is displayed as access 1.

### Policy details

| Policy | Metadata and victim rule | Important detail |
| --- | --- | --- |
| FIFO | Queue of occupied frame IDs ordered by page arrival; evict the head. | Hits never move queue entries. A new load joins the tail, including after replacement. |
| LRU | Last-access reference index for each resident frame; evict the smallest index. | Update on every completed reference. Use logical indices, never wall-clock timestamps. This is exact simulated LRU, not a claim about Linux's implementation. |
| OPT | Next-use positions in the fixed remaining workload; evict the farthest next use. | A page with no future use has next-use distance infinity. Resolve equal scores by lowest frame ID. |

Keep the simple `O(F)` victim scan: the product caps `F` at 32. For OPT, pre-index future page occurrences and advance their cursors as references are consumed, avoiding repeated scans through the remaining workload. Offsets do not affect page-replacement decisions.

Optimal is an offline benchmark that minimizes faults for this model. It is not implementable as a general online policy without future knowledge. [OSTEP: Beyond Physical Memory — Policies](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-beyondphys-policy.pdf)

### State and output contract

Keep the core independent of FastAPI, the DOM, and file paths. Suggested public operations:

```text
normalize_and_validate(config, workload) -> normalized accesses
simulate(config, accesses, policy) -> initial state + events + final metrics
compare(config, accesses, policies, frame_counts) -> summary rows
```

Policies expose initialization, victim selection, load notification, access notification, and a serializable explanation of their metadata. They do not own page tables, allocate frames, increment metrics, or render HTML. OPT alone receives the future-use index it needs.

An event contains: access index, input address, VPN, offset, page hit/fault, allocated frame, optional victim, optional TLB result, physical address, selection reason, frame state after access, policy metadata, and cumulative metrics. Include a schema version in exported data.

Use detached immutable snapshots or copied serialized values; never retain references to mutable frame lists/queues that later steps will change. Store occupied mappings/frame snapshots, and derive the full page-table display from those mappings; avoid copying all `V` entries into every event. Comparison sweeps collect summaries without retaining every detailed trace.

### Metrics and fairness

- `hits + faults = completed references`.
- `replacements <= faults`; with empty initial memory and no other allocation/freeing, `faults - replacements = occupied frames`.
- Fault rate is `faults / references`; hit rate is `hits / references`. At initial step 0, show rates as unavailable, not a division error.
- Compare identical normalized inputs, page size, frame count, empty initial state, and model options. Each policy/frame-count pair gets a fresh engine and fresh policy instance.
- In page mode, changing page size changes byte addresses but does not change the page sequence or fault counts. In address mode, changing page size may change the page sequence. Explain this when comparing experiments.
- Export raw counts and sufficient precision; round percentages only for display.
- “Fewer faults” is the comparison conclusion. Do not claim the lowest-fault policy has the lowest implementation overhead or is Linux's current policy.

## 6. Architecture and user interface

```text
React + TypeScript: configuration, playback cursor, tables, charts, downloads
                 |
                 | same-origin HTTP / JSON
                 v
FastAPI adapter: request validation, errors, serialization, local static assets
                 |
                 v
Pure simulation engine
  normalized workload -> residency/translation -> replacement policy -> events
                 |
                 v
Shared metrics and experiment/export utilities
```

One stateless request computes a bounded trace; the browser stores it and selects which completed state to display. Do not recalculate the engine for every playback tick. All authoritative algorithm and metric calculations stay in Python. The frontend only renders returned data and navigates it.

Keep React components focused: `ConfigurationForm`, `WorkloadEditor`, `AddressBreakdown`, `FrameView`, `PageTable`, `PolicyState`, `PlaybackControls`, `MetricsPanel`, and `ComparisonView`. A `usePlayback` hook owns the cursor/timer lifecycle, while a small reducer coordinates run/reset/edit/load actions. Use the selected trace position as the source for all displayed simulation state; do not independently mutate frame or counter state in components.

Keep API request/response types in one frontend module and validate the contract against Python responses with representative integration fixtures. Use relative `/api` URLs for both development and the packaged application. Redux, server-side rendering, a Node backend, and a client router are unnecessary for the initial two-view interface.

Suggested endpoints: `POST /api/simulate`, `POST /api/compare`, and `GET /api/health`. Serve the UI from the same application. No shared global “current simulation” that could leak state between tabs.

Suggested project layout:

```text
src/vmsim/
  __main__.py              # local launch command
  core/
    models.py             # configuration, normalized access, event, metrics
    validation.py         # reusable domain rules and input normalization
    engine.py             # one reference-processing path
    policies.py           # FIFO, LRU, OPT
    experiments.py        # comparison sweeps and export data
  web/
    app.py                # HTTP adapter and static asset routing
    schemas.py            # request/response contracts
    static/               # generated React build, included in release package
frontend/
  src/
    components/           # reusable simulation views and controls
    hooks/usePlayback.ts  # playback timer and cursor lifecycle
    api/                  # API client and typed request/response models
    state/                # experiment/playback reducer
    App.tsx
  package.json
  package-lock.json
  vite.config.ts          # development API proxy and build configuration
tools/
  stage_frontend.py       # stage frontend/dist into package static assets
examples/                 # versioned JSON workloads
tests/                    # engine, validation, integration, export tests
docs/                     # report, Linux guide, demo script
pyproject.toml
requirements.txt
requirements-dev.txt
README.md
PROJECT_PLAN.md
```

Keep the UI to two main views:

1. **Simulator:** configuration and workload editor; current address split; page table; physical frames; policy queue/recency/next-use evidence; event explanation; counters; playback controls and a bounded history table.
2. **Compare:** policy metrics table, fault counts against frame counts, Belady preset, and CSV/JSON export controls.

Next/Previous/seek select trace positions. Reset returns to step 0 without changing the experiment. Play uses one browser timer; Pause, Reset, configuration edits, and view changes stop that timer. Clean up timers on component unmount/effect cleanup and verify React development Strict Mode does not create duplicate timers. Ignore or cancel stale API responses when another experiment becomes active. Disable controls at trace boundaries. Show metrics for the selected step, with final totals labeled separately if displayed. Use text/icons in addition to color, keyboard-accessible controls, and an overflow-safe table on smaller screens.

## 7. Implementation phases and completion gates

The estimate below is 15 working days, assuming familiarity with Python, React, and basic TypeScript. Allow additional learning time if React/TypeScript is new to the team. Tests are added with the relevant implementation, not left until the final phase.

| Phase | Estimate | Concrete work | Completion gate |
| --- | --- | --- | --- |
| 0 — Requirements and Linux foundation | Day 1 | Confirm course constraints; freeze core scope/rules; create Python package/venv, React/TypeScript/Vite skeleton, dependency locks, API proxy, frontend build/staging, and test commands; bring up Linux development/test environment. | A clean Linux environment can run both development servers and serve the compiled React skeleton through Python. |
| 1 — Domain model and translation | Days 2–3 | Implement config/parser validation, both input modes, derived sizes, address splitting, page/frame records, initial state, free-frame allocation, and event schema. | Boundary cases pass; a simple no-eviction workload produces correct mappings and physical addresses. |
| 2 — Replacement engine | Days 4–6 | Add FIFO, LRU, OPT through the shared engine; capture victim reasons and policy metadata; implement counters and invariants. | Benchmark totals and victim choices pass; engine runs without the web layer; repeated runs are identical. |
| 3 — Trace and HTTP integration | Days 7–8 | Produce immutable snapshots; add stateless simulate/compare contracts, typed React API client, structured validation errors, example files, and JSON round-trip support. | An API result exactly matches a direct engine result and the frontend contract; snapshots remain unchanged after later steps; separate requests start empty. |
| 4 — Interactive simulator | Days 9–10 | Build React configuration, frames, page table, address calculation, explanations, reducer/playback hook, and bounded history rendering; test critical controls. | A user can step to the end, step backward, replay, reset, and change experiments without stale state or duplicate playback timers on Linux. |
| 5 — Comparison and exports | Days 11–12 | Add fresh-run comparison, frame sweeps, local SVG charts, Belady preset, CSV export, and experiment import/export UI. | Comparison totals match standalone runs; anomaly demo shows 9 then 10 FIFO faults; export/import reproduces the experiment. |
| 6 — Linux release verification and report | Days 13–14 | Fresh-install rehearsal for source and packaged builds; verify React assets in installed package without Node; Firefox/Chromium checks; performance measurement; offline runtime; launch/error polish; README, model limits, report, screenshots, viva/demo script. | All required acceptance checks pass on recorded Linux environment; source build and Python-only release runtime work from fresh environments. |
| 7 — Buffer or one extension | Day 15 | Fix remaining defects first. Add the TLB only if the required version is already stable and time remains. | Release stays usable with optional features disabled; any included extension passes its own tests. |

Dependencies: 0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6. Phase 7 must not block the required submission. Maintain a passing Linux baseline at every phase gate. Do not proceed to interface polish while replacement correctness is unresolved.

If only 10 working days are available: keep all three algorithms, translation, basic playback, and a comparison table; reduce chart styling, history-table complexity, and report polish; omit optional features entirely. Re-estimate any required feature that cannot fit rather than silently dropping it.

## 8. Correctness checks and known answers

The following counts were independently checked while preparing this plan. OPT totals were also checked using a small exhaustive, memoized victim-choice oracle, rather than only the intended greedy implementation.

| Page sequence | Frames | FIFO faults | LRU faults | OPT faults |
| --- | ---: | ---: | ---: | ---: |
| `1,2,3,1,4,2,5` | 3 | 5 | 6 | 5 |
| `1,2,3,4,1,2,5,1,2,3,4,5` | 3 | 9 | 10 | 7 |
| `1,2,3,4,1,2,5,1,2,3,4,5` | 4 | 10 | 8 | 6 |

For the first sequence, FIFO has 2 hits and 2 replacements. LRU has 1 hit and 3 replacements. OPT has 2 hits and 2 replacements. The original FIFO table is correct after relabeling its frame columns F0, F1, F2.

Implement meaningful automated checks:

- Translation: with `P=4096`, address `8300` gives page 2, offset 108; when mapped to F1, physical address is `4204`. On an empty engine, page 2 would normally receive F0 first, producing `108`; do not hard-code the example's mapping.
- Boundaries: address 0; `P-1`; `P`; `V*P-1`; reject `V*P`, page `V`, invalid page size, zero frames, malformed numbers, and excessive references. Support page/frame 0 without treating it as “empty.”
- Repetition: `2,2,2,2` with one frame gives 1 fault, 3 hits, 0 replacements.
- Capacity: `F >= distinct referenced pages` gives one fault per distinct page and no replacements. Also test `F > V`.
- FIFO-specific: hits do not move arrival order. LRU-specific: hits do update recency. OPT-specific: never-used-again candidates and equal-score tie handling.
- Consistency after every event: each resident page occupies exactly one frame; forward/reverse mappings agree; nonresident pages have no frame; physical addresses are in range; the requested page is resident after resolution.
- Accounting after every event: hits plus faults equal references; faults minus replacements equal occupied frames; selected-step counters agree with the displayed history position.
- Small exhaustive/property tests: compare OPT to a brute-force oracle on short traces; OPT faults never exceed FIFO/LRU for the same run; increasing frames cannot increase LRU or OPT faults under this model. Do not apply the monotonic-frame assertion to FIFO.
- History: earlier snapshots do not mutate; repeated runs return equal results; backward/forward playback returns the same frames, metadata, and counters.
- Integration: invalid API requests are rejected; fresh requests are independent; JSON save/load preserves workload/configuration/options; comparisons match individual runs; exports match returned metrics.
- React behavior: with controlled/fake timers, verify Play/Pause/Reset, boundary controls, timer cleanup, and selected-step rendering; delayed responses from an old request must not overwrite a newly selected experiment.
- Packaging: build the frontend, install the Python distribution in a fresh environment, and verify the UI and `/api` routes work from outside the repository without Node or Vite running.

Fault totals alone are insufficient: different incorrect victim decisions can sometimes produce the same total. Check important intermediate states and explanations as well.

## 9. Smoothness and release acceptance

These are provisional engineering targets, to be measured and adjusted honestly on the recorded reference laptop:

- A 1,000-reference trace with 32 frames should compute and serialize within 1 second after startup; a sweep of all three policies across frame counts 1–32 should complete within 3 seconds.
- Playback controls should respond within 100 ms for supported workloads. Render the current state plus a bounded history window; do not rebuild a 1,000-row table each tick.
- Loading/comparison has a visible busy state, prevents duplicate submissions, and reports errors without losing the editor contents.
- Pause/Reset stop playback immediately; Play at the final step has explicit behavior (disabled until seeking/resetting).
- The packaged app works offline after installation without Node/Vite, starts without root, handles a busy port, and shuts down cleanly with Ctrl+C.
- No state leaks across runs or tabs; opening another experiment does not change an existing trace.
- A fresh Linux environment passes the suite and full manual demo in Firefox and Chromium. Windows gets a secondary install/test pass after Linux gates are satisfied.

Record engine/API time separately from browser rendering time. If these targets fail, profile the trace serialization, OPT future-use handling, and history rendering before adding infrastructure or increasing workload limits. Do not claim the targets have been achieved until measured on Linux.

## 10. Optional TLB specification

Only implement this after the core release gate. Model one fully associative cache of VPN -> frame translations, initially empty, with fixed LRU replacement and a user-selected capacity of 1–32. Disabled is a separate option. Its capacity may exceed physical-frame count; it will simply contain fewer valid mappings.

- One TLB lookup per input reference. Count the initial lookup only; do not count a fault-handler retry as a second access.
- On a hit, count a TLB hit and a page hit, update TLB recency and the memory-policy access metadata, and translate directly.
- On a miss, count one TLB miss and consult the page table. A resident mapping produces a page hit; a nonresident mapping follows the regular fault path.
- Before reusing an evicted page's frame, invalidate its TLB mapping. After successful translation/resolution, insert/update the incoming mapping.
- For every valid TLB entry, require agreement with the page table and current frame owner.
- Track TLB hits/misses separately; when enabled, they sum to references. When disabled, display “disabled,” not a misleading 0% hit rate.
- Enabling/disabling the TLB must not change page-fault or replacement counts for a fixed policy/workload. Test this explicitly, especially for LRU hits through the TLB.

Do not add effective-access-time formulas unless a separate, explicitly hypothetical timing model is defined. TLB counters alone are enough educational value for this extension.

## 11. Deliverables and demonstration

Release deliverables: Python and React/TypeScript source code; pinned Python dependencies and npm lockfile; Python release package including compiled React assets; tested Linux development and end-user setup guides; engine/API and critical playback tests; example workloads; CSV/JSON export support; report explaining assumptions, data structures, complexity, results, limitations, and references; screenshots and a reproducible demo script.

Suggested 5–7 minute demo:

1. Configure 4 KiB pages and three frames; explain the distinction between virtual capacity and frame capacity.
2. Run `1,2,3,1,4,2,5` under FIFO; show a free-frame fault, a hit, and an eviction with the queue.
3. Navigate backward and forward; show consistent state and selected-step metrics.
4. Switch to byte-address mode and demonstrate offset preservation and a physical-address calculation using the actual current mapping.
5. Compare FIFO/LRU/OPT and explain why this workload makes LRU worse than FIFO.
6. Load the Belady preset; show FIFO's fault count increasing from 9 to 10 as frames increase from 3 to 4.
7. Export the experiment/results and state the model's limits. Show the TLB only if implemented and verified.

The first implementation milestone is a tested Linux-running engine for all three policies, not a polished dashboard. Once that milestone passes, every later view and comparison can use the same trusted results.
