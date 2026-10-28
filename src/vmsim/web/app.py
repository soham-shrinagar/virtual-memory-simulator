"""Serve the local API and the packaged React application from one origin."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from vmsim import __version__
from vmsim.web.schemas import HealthResponse


def create_app(static_dir: Path | None = None) -> FastAPI:
    assets = static_dir if static_dir is not None else Path(__file__).parent / "static"
    application = FastAPI(
        title="Virtual Memory Simulator",
        version=__version__,
        # The app is offline-capable; default docs pages load assets from CDNs.
        docs_url=None,
        redoc_url=None,
    )

    @application.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            version=__version__, frontend_ready=(assets / "index.html").is_file()
        )

    @application.api_route(
        "/api/{unmatched:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]
    )
    def unknown_api(unmatched: str) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "API route not found"})

    if (assets / "index.html").is_file():
        application.mount("/", StaticFiles(directory=assets, html=True), name="frontend")
    else:

        @application.get("/")
        def missing_frontend() -> JSONResponse:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Frontend build missing. Build and stage the React frontend "
                    "using the README instructions, or use the Vite development server."
                },
            )

    return application


app = create_app()

