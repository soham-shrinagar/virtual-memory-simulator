"""Verify a wheel installation through real HTTP, outside the source directory."""

from html.parser import HTMLParser
from pathlib import Path
import json
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import vmsim


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.assets: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        for name, value in attrs:
            if name in {"src", "href"} and value and value.startswith("/assets/"):
                self.assets.append(value)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if Path(vmsim.__file__).resolve().is_relative_to(root / "src"):
        raise RuntimeError("Use a fresh environment with the built wheel, not an editable install")
    with socket.create_server(("127.0.0.1", 0)) as probe:
        port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="vmsim-release-") as unrelated:
        server = subprocess.Popen(
            [sys.executable, "-m", "vmsim", "--port", str(port)],
            cwd=unrelated,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Installed server exited before becoming ready")
                try:
                    with urlopen(base + "/api/health", timeout=1) as response:
                        health = json.load(response)
                    break
                except (URLError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("Installed server did not become ready")
            assert health["status"] == "ok" and health["frontend_ready"] is True
            with urlopen(base, timeout=5) as response:
                html = response.read().decode()
            assert "VM Lab" in html
            parser = AssetParser()
            parser.feed(html)
            assert parser.assets, "Compiled frontend assets missing from installed HTML"
            for asset in parser.assets:
                with urlopen(base + asset, timeout=5) as response:
                    assert response.status == 200 and response.read()
            try:
                urlopen(base + "/api/unknown", timeout=5)
            except HTTPError as error:
                assert error.code == 404
            else:
                raise AssertionError("Unknown API path did not return 404")
        finally:
            if server.poll() is None:
                if sys.platform == "win32":
                    server.terminate()
                else:
                    server.send_signal(signal.SIGINT)
            try:
                output, _ = server.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                output, _ = server.communicate()
            print(output.strip())
        if sys.platform != "win32":
            assert server.returncode == 0, "Server did not shut down cleanly on SIGINT"
        print(f"PASS: installed wheel, health API, React HTML, {len(parser.assets)} local assets, API 404")
        print(f"Package location: {Path(vmsim.__file__).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
