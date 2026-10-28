"""Stage a completed Vite build into the Python package, on Linux or Windows."""

from pathlib import Path
import shutil
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    source = root / "frontend" / "dist"
    target = root / "src" / "vmsim" / "web" / "static"
    if not (source / "index.html").is_file():
        print("Frontend build missing. Run: npm --prefix frontend run build", file=sys.stderr)
        return 1
    # This exact directory is generated output, never hand-authored source.
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    print(f"Staged React build into {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

