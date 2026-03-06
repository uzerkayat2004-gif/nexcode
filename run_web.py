#!/usr/bin/env python3
"""
NexCode Web Server — Entry Point
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Starts the FastAPI server that powers the NexCode web interface.

Usage:
    python run_web.py              # default: http://localhost:8000
    python run_web.py --port 3000  # custom port
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="NexCode Web Server")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port number (default: 8000)"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("  ✗ uvicorn not installed. Run: uv add uvicorn[standard]")
        sys.exit(1)

    print(f"""
  ╔══════════════════════════════════════════════╗
  ║         NexCode — Web Interface              ║
  ╠══════════════════════════════════════════════╣
  ║  Server:  http://{args.host}:{args.port}             ║
  ║  API:     http://localhost:{args.port}/api/health    ║
  ║  WebSocket: ws://localhost:{args.port}/api/chat/stream║
  ╚══════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "nexcode.server.api:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
