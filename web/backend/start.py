#!/usr/bin/env python3
"""Start the Hermes Web Backend server."""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
log_dir = project_root / ".hermes" / "logs"
backend_log = log_dir / "web-backend.log"

try:
    import uvicorn
except ImportError:
    print("Error: uvicorn is not installed. Run 'pip install uvicorn'")
    sys.exit(1)


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(backend_log, encoding="utf-8"),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="Hermes Web Backend Server")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    setup_logging(args.log_level)

    logger = logging.getLogger(__name__)
    logger.info(f"Starting Hermes Web Backend on {args.host}:{args.port}")
    logger.info("Backend log file: %s", backend_log)

    # Run the server
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level.lower(),
    )


if __name__ == "__main__":
    main()
