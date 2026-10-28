# Architecture decisions — Phase 0

## Selected stack

Python owns every authoritative simulation decision and metric. The core package must not import React, FastAPI, or web/file infrastructure. React + TypeScript owns visualization and playback. FastAPI is a thin HTTP adapter. Vite is a development/build tool; the release has one local Python server and compiled frontend files.

Use npm's committed lockfile and exact direct frontend versions. Use separate pinned Python runtime/development requirement sets. Target Python 3.12/3.13, Ubuntu 24.04, and Node 22.23.2 for the initial build baseline. Windows is secondary.

## Simulation contract to implement next

Single process, flat page table, initially empty frames, complete fixed workload, abstract successful page loads, and zero-based page/frame IDs. Separate page-number and byte-address input modes. Faults and evictions have distinct counters. One engine processes references; FIFO/LRU/OPT select victims through a shared policy boundary. Deterministic free-frame and tie selection. Exact rules and limits are in `PROJECT_PLAN.md`.

The backend will return immutable traces. React will navigate those traces without recomputing policy decisions or maintaining a separate mutable memory model. TLB simulation remains optional after the required project is stable.

## Local serving and packaging

During development, Vite forwards relative `/api` requests to port 8000. In a release, Python handles `/api` first and serves local compiled assets afterward. Unknown API routes return JSON 404, never the React document. Missing frontend files produce a readable setup error; the health API still works. Paths resolve from the package, not the user's working directory.

No database, Node backend, server-side rendering, authentication, WebSockets, or external runtime assets are required for the initial local application. The Phase 0 UI shows connection status and planned work; it does not pretend to run a simulation.

## Course requirements

The project owner's selected technologies are Python and React. Any institutional language, report, or submission-format requirements still need to be checked by the team against its course rubric. No C/C++ implementation is planned. This administrative check does not block establishing the selected development environment.

