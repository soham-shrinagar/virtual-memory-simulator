"""Cross-platform local launcher: python -m vmsim."""

import argparse
import socket
import sys

import uvicorn

from vmsim import __version__
from vmsim.web.app import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local Virtual Memory Simulator")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: local only)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    family = socket.AF_INET6 if ":" in args.host else socket.AF_INET
    try:
        listener = socket.create_server((args.host, args.port), family=family)
    except OSError as error:
        print(
            f"Cannot listen on {args.host}:{args.port}: {error}. "
            "Close the other server or choose another --port.",
            file=sys.stderr,
        )
        return 1

    display_host = f"[{args.host}]" if family == socket.AF_INET6 else args.host
    print(f"Virtual Memory Simulator: http://{display_host}:{args.port}", flush=True)
    server = uvicorn.Server(uvicorn.Config(create_app(), host=args.host, port=args.port))
    try:
        server.run(sockets=[listener])
    except KeyboardInterrupt:
        # Uvicorn completes graceful shutdown, then asyncio may re-raise SIGINT.
        pass
    finally:
        listener.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

