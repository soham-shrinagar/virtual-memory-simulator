"""Rehearse fresh wheel/source installations; run with the development Python."""

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import tarfile
import venv
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True, help='Built .tar.gz source archive')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    wheel, source = args.wheel.resolve(), args.source.resolve()
    if not wheel.is_file() or not source.is_file():
        parser.error('Build both the wheel and source archive first.')
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
    with tarfile.open(source) as archive:
        source_names = archive.getnames()
    for names in (wheel_names, source_names):
        assert any('/web/static/assets/' in name and name.endswith('.js') for name in names), 'Built frontend missing'
        for name in names:
            path = Path(name)
            assert not {'docs', 'doc', '.tools', 'node_modules'} & set(path.parts), f'Local artifact leaked: {name}'
            assert path.suffix not in {'.ts', '.tsx'}, f'Unexpected TypeScript source: {name}'
            assert path.suffix.lower() not in {'.md', '.markdown'} or path.name == 'README.md', f'Local notes leaked: {name}'
    assert any(name.endswith('/frontend/package-lock.json') for name in source_names)
    assert any(name.endswith('/tests/test_api.py') for name in source_names)
    print('PASS: release archives contain source/assets and exclude local artifacts', flush=True)
    with tempfile.TemporaryDirectory(prefix='vmsim-fresh-') as directory:
        temp = Path(directory)
        for name, archive in [('wheel', wheel), ('source', source)]:
            env = temp / name
            venv.create(env, with_pip=True)
            python = env / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
            def run(*arguments):
                subprocess.run([str(python), *map(str, arguments)], cwd=temp, check=True)
            # The source install also needs the pinned build backend. No frontend build
            # tool is used: the source archive must contain the staged local assets.
            requirements = 'requirements-dev.txt' if name == 'source' else 'requirements.txt'
            run('-m', 'pip', 'install', '-r', root / requirements)
            run('-m', 'pip', 'install', '--no-deps', '--no-build-isolation', archive)
            run(root / 'tools/smoke_release.py')
            print(f'PASS: fresh {name} installation outside repository, no Node runtime', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
