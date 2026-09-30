"""HelixDB development entry point.

Lets the service be started from the repository root without knowing the
module path, which is the form most people try first:

    python main.py                 # serve on 127.0.0.1:8123
    python main.py --port 9000
    python main.py --reload

The application itself is `backend.main:app` -- this module only resolves it
and hands it to uvicorn, so there is a single FastAPI app instance and no
second copy of the wiring.
"""
from __future__ import annotations

import argparse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8123


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="main.py", description="Run the HelixDB API server."
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind address")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="bind port")
    parser.add_argument(
        "--reload", action="store_true", help="restart on source changes"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    import uvicorn

    from backend.main import app

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
