"""Shared helpers for logging, metadata, and raw-row hashing."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping
from uuid import uuid4


def configure_logging(log_file: Path) -> logging.Logger:
    """Configure a file and console logger for one pipeline invocation."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Avoid duplicate handlers when the module is invoked repeatedly in tests.
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def new_batch_id() -> str:
    """Return an identifier shared by every record in a pipeline execution."""
    return str(uuid4())


def utc_ingestion_timestamp() -> str:
    """Return a timezone-aware Bronze ingestion timestamp without touching source dates."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def source_system_for(dataset: str) -> str:
    """Derive the source application name from the logical dataset prefix."""
    return dataset.split("_", maxsplit=1)[0]


def row_hash(row: Mapping[str, str]) -> str:
    """Create a deterministic SHA-256 hash from the exact raw column/value pairs."""
    payload = json.dumps(
        list(row.items()), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
