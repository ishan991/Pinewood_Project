"""Bronze validation checks for raw-to-Bronze parity."""

import csv
from pathlib import Path

import pyarrow.parquet as pq

from pipeline.config import BRONZE_DATA_DIR, LOG_DIR, RAW_DATA_DIR
from pipeline.extract import discover_source_files, read_csv_rows

METADATA_COLUMNS = {
    "ingestion_timestamp",
    "source_file",
    "source_system",
    "batch_id",
    "row_hash",
}


def _count_raw_rows_and_columns(source_files: list[Path]) -> tuple[int, set[str]]:
    """Count total raw rows and collect all source columns for a dataset."""
    total_rows = 0
    raw_columns: set[str] = set()

    for source_path in source_files:
        with source_path.open("r", encoding="utf-8-sig", newline="") as source_file:
            reader = csv.DictReader(source_file, restval="")
            if reader.fieldnames is None:
                raise ValueError(f"CSV file has no header: {source_path}")

            raw_columns.update(column for column in reader.fieldnames if column is not None)
            for _ in reader:
                total_rows += 1

    return total_rows, raw_columns


def _bronze_table_for(dataset: str):
    """Read the Bronze Parquet table for a dataset."""
    bronze_path = BRONZE_DATA_DIR / f"{dataset}.parquet"
    if not bronze_path.exists():
        raise FileNotFoundError(f"Missing Bronze dataset file: {bronze_path}")
    return pq.read_table(bronze_path)


def _build_dataset_report(dataset: str, source_files: list[Path]) -> tuple[list[str], bool]:
    """Run the row and column checks for a single dataset and return the report lines."""
    raw_rows, raw_columns = _count_raw_rows_and_columns(source_files)
    bronze_table = _bronze_table_for(dataset)
    bronze_rows = bronze_table.num_rows
    bronze_columns = set(bronze_table.column_names)

    row_count_pass = raw_rows == bronze_rows
    bronze_source_columns = bronze_columns - METADATA_COLUMNS
    column_check_pass = raw_columns.issubset(bronze_source_columns)

    lines = [
        "==================================",
        f"Dataset : {dataset}",
        f"Raw Rows      : {raw_rows}",
        f"Bronze Rows   : {bronze_rows}",
        f"Row Count     : {'PASS' if row_count_pass else 'FAIL'}",
        f"Raw Columns   : {len(raw_columns)}",
        f"Bronze Columns: {len(bronze_columns)}",
        f"Column Check  : {'PASS' if column_check_pass else 'FAIL'}",
        "==================================",
    ]

    dataset_pass = row_count_pass and column_check_pass
    return lines, dataset_pass


def validate_bronze() -> None:
    """Validate every Bronze dataset against the corresponding raw monthly files."""
    grouped_files = discover_source_files(RAW_DATA_DIR)
    if not grouped_files:
        print("==================================")
        print("BRONZE VALIDATION SUMMARY")
        print("Datasets Processed : 0")
        print("Passed             : 0")
        print("Failed             : 0")
        print("==================================")

        log_path = LOG_DIR / "bronze_validation.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "==================================\n"
            "BRONZE VALIDATION SUMMARY\n"
            "Datasets Processed : 0\n"
            "Passed             : 0\n"
            "Failed             : 0\n"
            "==================================\n",
            encoding="utf-8",
        )
        return

    report_lines: list[str] = []
    datasets_processed = 0
    passed_count = 0
    failed_count = 0

    for dataset, source_files in sorted(grouped_files.items()):
        datasets_processed += 1
        dataset_lines, dataset_pass = _build_dataset_report(dataset, sorted(source_files))

        report_lines.extend(dataset_lines)
        for line in dataset_lines:
            print(line)

        if dataset_pass:
            passed_count += 1
        else:
            failed_count += 1

    summary_lines = [
        "==================================",
        "BRONZE VALIDATION SUMMARY",
        f"Datasets Processed : {datasets_processed}",
        f"Passed             : {passed_count}",
        f"Failed             : {failed_count}",
        "==================================",
    ]

    report_lines.extend(summary_lines)
    for line in summary_lines:
        print(line)

    log_path = LOG_DIR / "bronze_validation.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
