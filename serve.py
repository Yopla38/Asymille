#!/usr/bin/env python3
"""Asymille for one person, on their own machine: no accounts, a SQLite file.

    uv sync
    uv run python serve.py                    # http://localhost:8780
    uv run python serve.py --port 8781 --database /tmp/asymille.db

To serve several people, with accounts: plug asymille.web into Ondelette's
server (integration/ondelette). This one listens on 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Asymille, standalone: one person, no accounts.")
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--database", default=str(HERE / "data" / "asymille.db"), help="the SQLite file the projects are kept in")
    args = parser.parse_args()

    import uvicorn

    from asymille.web.standalone import create_app

    print(f"http://localhost:{args.port}")
    print(f"projects  {args.database}")
    uvicorn.run(create_app(args.database, args.port), host="127.0.0.1", port=args.port, server_header=False, log_level="warning")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
