"""Phase 0 contracts: API, offline static serving, and launcher errors."""

from pathlib import Path
import socket

from fastapi.testclient import TestClient

from vmsim import IMPLEMENTATION_PHASE, __version__
from vmsim.__main__ import main
from vmsim.web.app import create_app


def test_api_stays_usable_before_frontend_is_built(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "not-built")) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok", "application": "vmsim", "version": __version__,
            "phase": IMPLEMENTATION_PHASE, "frontend_ready": False,
        }
        assert client.get("/").status_code == 503
        assert "Frontend build missing" in client.get("/").json()["detail"]


def test_packaged_assets_do_not_depend_on_working_directory(
    tmp_path: Path, monkeypatch
) -> None:
    assets = tmp_path / "packaged"
    (assets / "assets").mkdir(parents=True)
    (assets / "index.html").write_text('<h1>React shell</h1>', encoding="utf-8")
    (assets / "assets" / "app.js").write_text('console.log("local asset")', encoding="utf-8")
    elsewhere = tmp_path / "unrelated"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with TestClient(create_app(assets)) as client:
        assert client.get("/").text == '<h1>React shell</h1>'
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/api/health").json()["frontend_ready"] is True
        assert client.get("/api/does-not-exist").status_code == 404
        assert client.post("/api/simulate", json={}).status_code == 404
        assert client.get("/assets/missing.js").status_code == 404


def test_busy_port_reports_actionable_error(capsys) -> None:
    with socket.create_server(("127.0.0.1", 0)) as occupied:
        port = occupied.getsockname()[1]
        assert main(["--port", str(port)]) == 1
    assert "choose another --port" in capsys.readouterr().err

