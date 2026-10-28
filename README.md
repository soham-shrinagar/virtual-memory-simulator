# VM Lab — Virtual Memory Simulator

A Linux-first university OS project with a **Python simulation engine/backend** and a **React + JavaScript interface**. React components use JSX. It is an educational model, not a replacement for the host operating system's memory manager.

**Current milestone: Phase 0.** The package, health API, React application shell, development proxy, tests, frontend build, and Python release packaging are available. Memory configuration, translation, replacement algorithms, and playback are scheduled for subsequent phases.

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

Vite builds the JavaScript/JSX frontend. Backend tests cover health responses, missing/frontend assets, API 404 behavior, independence from the working directory, and occupied-port errors. React tests cover backend connection, retry after failure, Strict Mode, and malformed API responses. API responses are validated at runtime before the UI uses them.

## Build and verify an installable release

After building and staging the frontend:

```bash
.venv/bin/python -m build --no-isolation
python3 -m venv .venv-release
.venv-release/bin/python -m pip install -r requirements.txt
.venv-release/bin/python -m pip install --no-deps dist/vmsim_os-0.1.0-py3-none-any.whl
.venv-release/bin/python tools/smoke_release.py
```

The smoke tool launches the installed package from an unrelated temporary directory, checks the API, HTML, and compiled assets over real HTTP, and shuts the server down. It rejects editable/source imports. It needs no Node process. Distribute the wheel and `requirements.txt`; install them into a fresh virtual environment and run that environment's `python -m vmsim`.

`requirements.txt` contains pinned runtime dependencies; `requirements-dev.txt` additionally pins test/build/locking tools. `package-lock.json` locks the frontend. After intentionally changing Python dependencies, regenerate both locks and test on Linux and Windows:

```bash
.venv/bin/python -m piptools compile --strip-extras --no-emit-index-url -o requirements.txt requirements.in
.venv/bin/python -m piptools compile --allow-unsafe --strip-extras --no-emit-index-url -o requirements-dev.txt requirements-dev.in
```

Keep direct Python dependencies in `requirements.in` and `pyproject.toml` synchronized. Build with the locked development environment using `--no-isolation`.

## Layout

```text
src/vmsim/core/          Pure Python simulation logic (begins in Phase 1)
src/vmsim/web/           FastAPI adapter and generated frontend assets
frontend/src/           JavaScript/JSX React UI, API client, and frontend tests
tests/                  Python tests
tools/                  Cross-platform staging and release verification
```

Planning notes, screenshots, and repository instructions are kept locally and ignored by Git. The `docs/` and `doc/` folders are excluded from version control and release packages. `README.md` is the only Markdown file included in version control.

