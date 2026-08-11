"""Command-line entry point for the complete Bronze, Silver, and Gold pipeline."""

from __future__ import annotations

import sys
from pathlib import Path


# Find the project root and add it to Python's import path.
# This allows the file to work when it is run directly as pipeline/main.py.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.bronze import build_bronze_table, write_bronze_dataset
from pipeline.config import BRONZE_DATA_DIR, LOG_FILE, RAW_DATA_DIR
from pipeline.extract import discover_source_files
from pipeline.gold.gold import run_gold
from pipeline.silver.silver import run as run_silver
from pipeline.utils import configure_logging, new_batch_id, utc_ingestion_timestamp
from pipeline.validation import validate_bronze


def run_bronze(logger) -> None:
    """Ingest all raw CSVs into one Bronze Parquet file per logical dataset."""
    # Create one batch ID and ingestion timestamp shared by this Bronze run.
    # These values provide consistent lineage metadata across all loaded records.
    batch_id = new_batch_id()
    ingestion_timestamp = utc_ingestion_timestamp()
    logger.info("Bronze ingestion started: batch_id=%s", batch_id)

    # Find the monthly CSV files and group them by logical dataset name.
    # For example, all monthly Yardi lease files belong to one Yardi lease dataset.
    grouped_files = discover_source_files(RAW_DATA_DIR)
    if not grouped_files:
        logger.warning("No CSV files found under %s", RAW_DATA_DIR)
        return

    # Combine each dataset's monthly files and write one Bronze Parquet file.
    # If any dataset fails, record the error and stop the pipeline immediately.
    try:
        for dataset, source_files in grouped_files.items():
            table = build_bronze_table(
                dataset=dataset,
                source_files=source_files,
                raw_data_dir=RAW_DATA_DIR,
                ingestion_timestamp=ingestion_timestamp,
                batch_id=batch_id,
            )
            target = write_bronze_dataset(table, dataset, BRONZE_DATA_DIR)
            logger.info(
                "Wrote dataset=%s rows=%d files=%d target=%s",
                dataset,
                table.num_rows,
                len(source_files),
                target,
            )
    except Exception:
        logger.exception("Bronze ingestion failed: batch_id=%s", batch_id)
        raise

    logger.info("Bronze ingestion completed: batch_id=%s", batch_id)

    # Validate every generated Bronze dataset before the Silver stage begins.
    validate_bronze()


def run_stage(stage_name: str, stage_function, logger) -> None:
    """Run one pipeline stage and record its success or failure."""
    # Log the stage name before calling the function passed into this method.
    logger.info("%s stage started", stage_name)

    # Log the complete exception and pass it upward so later stages do not run.
    try:
        stage_function()
    except BaseException:
        logger.exception("%s stage failed", stage_name)
        raise

    logger.info("%s stage completed successfully", stage_name)


def run() -> None:
    """Run Bronze, Silver, and Gold sequentially and log the full pipeline."""
    # Use the shared pipeline logger so every stage is recorded in pipeline.log.
    logger = configure_logging(LOG_FILE)
    logger.info("Complete pipeline started")

    # Run each layer in dependency order.
    # Silver starts only after Bronze succeeds, and Gold starts only after Silver succeeds.
    try:
        run_stage("Bronze", lambda: run_bronze(logger), logger)
        run_stage("Silver", run_silver, logger)
        run_stage("Gold", run_gold, logger)
    except BaseException:
        logger.error("Complete pipeline failed")
        raise

    logger.info("Complete pipeline completed successfully")


# Start the complete pipeline only when this file is executed directly.
# Importing pipeline.main from another module will not start any transformations.
if __name__ == "__main__":
    run()
