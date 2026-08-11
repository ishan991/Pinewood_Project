"""Gold layer orchestration entrypoint."""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

GOLD_ROOT = Path(__file__).resolve().parent
GOLD_LOG_PATH = PROJECT_ROOT / "logs" / "Gold.log"


def _configure_gold_logger() -> logging.Logger:
    """Create the file logger used by the Gold pipeline."""
    GOLD_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("pinewood.gold")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        file_handler = logging.FileHandler(GOLD_LOG_PATH, mode="a", encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        logger.addHandler(file_handler)

    return logger


def _discover_transformations(logger: logging.Logger) -> dict[str, list[tuple[str, object]]]:
    transformations: dict[str, list[tuple[str, object]]] = {"dim": [], "fact": []}

    for folder_name in ("dim", "fact"):
        folder_path = GOLD_ROOT / folder_name
        for script_path in sorted(folder_path.glob("*.py")):
            if script_path.name == "__init__.py":
                continue

            module_name = script_path.stem
            try:
                module = importlib.import_module(f"pipeline.gold.{folder_name}.{module_name}")
                run_fn = getattr(module, "run", None)
                if run_fn is None:
                    raise AttributeError(
                        f"Module '{module_name}' in '{folder_name}' does not define a 'run()' function."
                    )
            except Exception:
                logger.exception("FAILED | %s/%s.py | Import or discovery error", folder_name, module_name)
                raise

            transformations[folder_name].append((module_name, run_fn))

    return transformations


def _run_module(kind: str, module_name: str, run_fn: object, logger: logging.Logger) -> None:
    print(f"Running {module_name}...")
    logger.info("STARTED | %s | %s.py", kind, module_name)
    try:
        run_fn()
    except Exception as exc:  # pragma: no cover - runtime guard for orchestrator
        logger.exception("FAILED | %s | %s.py", kind, module_name)
        print(f"ERROR: {kind} transformation failed: {module_name}")
        print(f"Error: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc
    else:
        logger.info("SUCCESS | %s | %s.py", kind, module_name)


def run_gold() -> None:
    logger = _configure_gold_logger()
    logger.info("GOLD PIPELINE START")

    try:
        transformations = _discover_transformations(logger)

        print("==================================================")
        print("GOLD PIPELINE START")
        print("==================================================")

        for module_name, run_fn in transformations["dim"]:
            _run_module("dimension", module_name, run_fn, logger)

        for module_name, run_fn in transformations["fact"]:
            _run_module("fact", module_name, run_fn, logger)

        print("==================================================")
        print("GOLD PIPELINE SUMMARY")
        print("==================================================")
        print("DIMENSIONS")
        for module_name, _ in transformations["dim"]:
            print(f"{module_name:<20} PASS")

        print()
        print("FACTS")
        for module_name, _ in transformations["fact"]:
            print(f"{module_name:<20} PASS")

        print("==================================================")
        print("Gold pipeline completed successfully.")
        print("==================================================")
    except BaseException:
        logger.error("GOLD PIPELINE FAILED")
        raise
    else:
        logger.info("GOLD PIPELINE COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    run_gold()
