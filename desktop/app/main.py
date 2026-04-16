"""Desktop entrypoint for local sync host bootstrap."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import uvicorn

from desktop.app.app_shell import run_desktop_app
from desktop.app.sync.api import create_app


def _install_crash_logging() -> None:
    def _handle_exception(exc_type, exc_value, exc_traceback) -> None:
        logging.getLogger("genesis.crash").exception(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
            extra={"subsystem": "startup"},
        )

    sys.excepthook = _handle_exception


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["desktop", "sync-host"], default="desktop")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[3]
    _install_crash_logging()
    if args.mode == "desktop":
        try:
            return run_desktop_app(project_root)
        except Exception as exc:
            logging.getLogger("genesis.startup").exception(
                "Desktop startup failed",
                extra={"subsystem": "startup"},
            )
            print(f"Startup failed: {exc}", file=sys.stderr)
            return 2
    app = create_app(root=project_root)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

