"""CSV discovery and text-only extraction for the Bronze layer."""

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterator

from pipeline.config import MONTHLY_FILE_PATTERN


def dataset_name_for(file_path: Path) -> str:
    """Return the logical dataset name, removing a monthly file suffix when present."""
    match = re.match(MONTHLY_FILE_PATTERN, file_path.stem)
    return match.group("dataset") if match else file_path.stem


def discover_source_files(raw_data_dir: Path) -> dict[str, list[Path]]:
    """Recursively discover every CSV and group monthly extracts by logical dataset."""
    grouped: dict[str, list[Path]] = defaultdict(list)
    for file_path in raw_data_dir.rglob("*.csv"):
        dataset = dataset_name_for(file_path)
        grouped[dataset].append(file_path)
    return {dataset: sorted(files) for dataset, files in sorted(grouped.items())}


def read_csv_rows(file_path: Path) -> Iterator[dict[str, str]]:
    """Yield CSV rows as strings only; no values are parsed, cleaned, or cast."""
    with file_path.open("r", encoding="utf-8-sig", newline="") as source_file:
        reader = csv.DictReader(source_file, restval="")
        if reader.fieldnames is None:
            raise ValueError(f"CSV file has no header: {file_path}")
        for row in reader:
            # DictReader returns None for a missing field, while restval handles
            # absent values. Convert only that parser sentinel to an empty raw value.
            yield {column: "" if value is None else value for column, value in row.items()}
