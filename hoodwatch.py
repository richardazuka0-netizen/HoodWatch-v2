#!/usr/bin/env python3
"""Hoodwatch v2 - fixed launcher for local + Render.

Cloud mode starts the web server immediately so Render health checks pass,
then indexes in the background.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQ = ROOT / "requirements.txt"
DB = ROOT / "hoodwatch.db"


def python_bin() -> str:
    return sys.executable


def ensure_dependencies() -> None:
    try:
        import web3  # noqa: F401
    except ImportError:
        print("Installing packages from requirements.txt...\n")
        subprocess.check_call([python_bin(), "-m", "pip", "install", "-r", str(REQ)])


def run(module: str, *args: str) -> None:
    cmd = [python_bin(), str(ROOT / module), *args]
    subprocess.check_call(cmd, cwd=ROOT)


def background_index_and_score(blocks: int | None) -> None:
    """Run indexing + scoring after the server is already up."""
    try:
        time.sleep(2)  # give the server a moment to bind
        print("[bg] Starting background indexing...")
        index_args = []
        if blocks is not None:
            index_args += ["--blocks", str(blocks)]
        run("indexer.py", *index_args)
        print("[bg] Scoring tags...")
        run("score.py")
        print("[bg] Building clusters...")
        run("cluster.py")
        print("[bg] Background pipeline finished.")
    except Exception as exc:
        print(f"[bg] Background pipeline failed (service continues): {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Hoodwatch v2")
    parser.add_argument("--no-index", action="store_true", help="skip live RPC indexing")
    parser.add_argument("--blocks", type=int, help="override the recent block window")
    parser.add_argument("--start", type=int, help="explicit starting block")
    parser.add_argument("--end", type=int, help="explicit ending block")
    parser.add_argument("--host", default=os.getenv("HOODWATCH_HOST", "127.0.0.1"), help="web host")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8787")), help="web port")
    parser.add_argument("--cloud", action="store_true", help="cloud mode: bind 0.0.0.0 and background indexing")
    args = parser.parse_args()

    ensure_dependencies()

    if args.cloud:
        args.host = "0.0.0.0"
        args.port = int(os.getenv("PORT", str(args.port)))
        if args.blocks is None:
            args.blocks = int(os.getenv("HOODWATCH_RECENT_BLOCKS", "2000"))

    # Ensure schema exists even before first index
    if not DB.exists():
        import sqlite3
        schema = (ROOT / "schema.sql").read_text()
        c = sqlite3.connect(DB)
        c.executescript(schema)
        c.close()
        print("Created empty hoodwatch.db")

    if args.cloud and not args.no_index:
        # Start indexing in background so the server can respond to health checks immediately
        t = threading.Thread(target=background_index_and_score, args=(args.blocks,), daemon=True)
        t.start()
        print(f"Hoodwatch (cloud) starting on http://{args.host}:{args.port}")
        print("Indexing is running in the background. Dashboard will populate shortly.\n")
        run("web.py", "--host", args.host, "--port", str(args.port))
    else:
        # Local / blocking mode (original behavior)
        if not args.no_index:
            index_args = []
            if args.blocks is not None:
                index_args += ["--blocks", str(args.blocks)]
            if args.start is not None:
                index_args += ["--start", str(args.start)]
            if args.end is not None:
                index_args += ["--end", str(args.end)]
            print("\n[1/3] Reading public chain logs (read-only)...")
            run("indexer.py", *index_args)
        else:
            print("\n[1/3] Skipping live indexing (--no-index).")

        print("\n[2/3] Calculating deterministic wallet tags...")
        run("score.py")
        print("\n[3/3] Building evidence-backed likely-related clusters...")
        run("cluster.py")

        print(f"\nHoodwatch is ready: http://{args.host}:{args.port}")
        run("web.py", "--host", args.host, "--port", str(args.port))


if __name__ == "__main__":
    main()
