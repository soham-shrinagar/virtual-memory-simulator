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
from urllib.request import Request, urlopen

import vmsim


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.assets: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        for name, value in attrs:
            if name in {"src", "href"} and value:
                assert not value.startswith(("http:", "https:", "//")), "Runtime assets must be local"
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
        # Block outbound connections in this child only, without changing machine
        # networking. The runtime must function using loopback and local assets.
        offline_launch = '''
import ipaddress, runpy, socket
original_connect = socket.socket.connect
def local_connect(sock, address):
    if sock.family in (socket.AF_INET, socket.AF_INET6):
        try:
            local = ipaddress.ip_address(address[0]).is_loopback
        except ValueError:
            local = address[0] == 'localhost'
        if not local:
            raise OSError('Release check blocks outbound network access')
    return original_connect(sock, address)
socket.socket.connect = local_connect
runpy.run_module('vmsim', run_name='__main__')
'''
        server = subprocess.Popen(
            [sys.executable, "-c", offline_launch, "--port", str(port)],
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
            conflict = subprocess.run([sys.executable, '-m', 'vmsim', '--port', str(port)],
                                      cwd=unrelated, capture_output=True, text=True, timeout=10)
            assert conflict.returncode == 1 and 'choose another --port' in conflict.stderr
            with urlopen(base, timeout=5) as response:
                html = response.read().decode()
            assert "VM Lab" in html
            parser = AssetParser()
            parser.feed(html)
            assert parser.assets, "Compiled frontend assets missing from installed HTML"
            for asset in parser.assets:
                with urlopen(base + asset, timeout=5) as response:
                    assert response.status == 200 and response.read()

            def post(path, payload):
                request = Request(base + path, data=json.dumps(payload).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(request, timeout=10) as response:
                    return json.load(response)

            for policy, faults in (("fifo", 5), ("lru", 6), ("optimal", 5)):
                result = post("/api/simulate", {"workload": [1, 2, 3, 1, 4, 2, 5], "policy": policy})
                assert result["metrics"]["faults"] == faults
                assert len(result["events"]) == 7
            comparison = post("/api/compare", {"workload": [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5],
                                               "policies": ["fifo"], "frame_counts": [3, 4]})
            assert [row["metrics"]["faults"] for row in comparison["rows"]] == [9, 10]
            cached = post('/api/simulate', {'workload': [0, 1, 0], 'tlb_capacity': 2, 'policy': 'lru'})
            assert cached['tlb']['hits'] == 1 and cached['tlb']['misses'] == 2
            assert cached['metrics']['faults'] == 2 and cached['events'][2]['tlb_result'] == 'hit'
            recipe = {'seed': 42, 'length': 5, 'profile': 'uniform'}
            generated = post('/api/workloads/generate', recipe)
            assert generated['workload'] == [0, 2, 1, 5, 5]
            assert generated == post('/api/workloads/generate', recipe)
            clock = post('/api/simulate', {'workload': [0, 1, 2, 0, 3, 1, 4], 'policy': 'clock', 'tlb_capacity': 2})
            assert [event['victim_page'] for event in clock['events'] if event['victim_page'] is not None] == [0, 2]
            experiment = post("/api/experiments/export", {"workload": "4096,8300,4097", "input_mode": "addresses"})
            assert post("/api/experiments/import", experiment) == experiment
            duplicate = '{"policy":"lru",' + json.dumps(experiment)[1:]
            try:
                urlopen(Request(base + '/api/experiments/import', data=duplicate.encode(),
                                headers={'Content-Type': 'application/json'}), timeout=5)
            except HTTPError as error:
                assert error.code == 422 and 'Duplicate JSON key' in error.read().decode()
            else:
                raise AssertionError('Import accepted duplicate JSON keys')
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
        print(f"PASS: installed package, outbound connections blocked, health API, React HTML, {len(parser.assets)} local assets, simulation/comparison/experiment APIs, API 404")
        print(f"Package location: {Path(vmsim.__file__).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
