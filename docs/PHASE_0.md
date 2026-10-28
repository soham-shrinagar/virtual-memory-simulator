# Phase 0 — completed

Verified on 28 October 2026. The application foundation is ready for Phase 1.

## Delivered

- Python `src` package with a pure-domain `core/` boundary and separate web adapter.
- React + TypeScript + Vite application shell with a real backend connection check, failure state, and retry.
- Typed and validated `GET /api/health` response; unknown API routes return JSON 404.
- Development API proxy, bound to local addresses.
- A single `python -m vmsim` / `vmsim` release launcher, configurable host/port, occupied-port diagnostics, and clean Linux Ctrl+C handling.
- Cross-platform React build staging and Python wheel/source distribution including compiled assets.
- Pinned Python runtime/development dependencies, npm lockfile, Node baseline, and platform-safe repository ignores/line endings.
- Backend and frontend smoke tests, plus an actual installed-wheel HTTP verification tool.
- Setup/build/run instructions and recorded architecture decisions.

## Environments and results

| Check | Ubuntu 24.04.3 LTS, WSL2 | Windows host |
| --- | --- | --- |
| Python | 3.12.3 | 3.13.1 |
| Node / npm | 22.23.2 / 10.9.8 | 22.23.2 / 10.9.8 |
| Python foundation tests | 3 passed | 3 passed |
| React connection/error/retry/contract tests | 3 passed | 3 passed |
| TypeScript check + Vite production build | Passed | Passed |
| Live Python API and Vite `/api` proxy | Passed | Passed |
| Source archive and wheel build | Passed | Passed |
| Fresh wheel install; HTTP checks from unrelated directory | Passed | Passed |
| Linux launcher SIGINT exit | Exit 0, no traceback | Not applicable to the Linux signal check |

The release check fetches the real health endpoint, React HTML, JavaScript and CSS assets, and an unknown API route. It verifies that the package is imported from the release environment rather than the source/editable installation. No Node/Vite server runs for this check.

Linux installs/builds used their own virtual environment and `node_modules` directory in an independent Linux filesystem workspace. The isolated Node runtime came from the official Node distribution, verified against its published SHA-256 checksum. The system's existing Node installation was not replaced. The final Linux verification workspace/runtime are in persistent home directories, not `/tmp`.

The interface was also opened in the desktop app's browser: the production React page rendered, showed the connected Python backend, and its connection button worked. [Saved preview](phase0-preview.png). Native Linux desktop Firefox/Chromium visual acceptance remains part of Phase 6; Phase 0's Linux checks cover installation, execution, builds, tests, serving, and the development proxy.

## Issue caught and fixed during Linux verification

The first Linux release smoke check found that Uvicorn completed shutdown and then Python's asyncio runner re-raised `KeyboardInterrupt`, causing a traceback and nonzero exit. The launcher now handles that final interruption while always closing its listening socket. The installed-wheel check passed after rebuilding, including the required zero exit on SIGINT.

## Scope boundary

This milestone establishes a working application foundation. The page table, address translation, replacement policies, workload controls, metrics, and playback are not implemented yet. Their reviewed behavior is specified in `PROJECT_PLAN.md` and begins in Phase 1.

Python and React are the project owner's selected stack. The team must still compare its university's administrative/report/submission requirements against its course rubric; no rubric was provided in this workspace.

## Reproduce

Follow `README.md` for a fresh setup, then run:

```bash
.venv/bin/python -m pytest
npm --prefix frontend run test -- --run
npm --prefix frontend run build
.venv/bin/python tools/stage_frontend.py
.venv/bin/python -m build --no-isolation
```

Install the wheel into the separate release environment as documented in the README and run `tools/smoke_release.py` using that environment's Python. Recreate environments separately on each operating system.

