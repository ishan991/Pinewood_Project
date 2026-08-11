"""Bronze dataset assembly and Parquet writing."""

import os
from collections.abc import Iterable
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from pipeline.extract import read_csv_rows
from pipeline.utils import row_hash, source_system_for

METADATA_COLUMNS = (
    "ingestion_timestamp",
    "source_file",
    "source_system",
    "batch_id",
    "row_hash",
)


def build_bronze_table(
    dataset: str,
    source_files: Iterable[Path],
    raw_data_dir: Path,
    ingestion_timestamp: str,
    batch_id: str,
) -> pa.Table:
    """Union source rows, preserving all raw fields as strings and appending metadata."""
    records: list[dict[str, str]] = []
    raw_columns: list[str] = []

    for source_path in source_files:
        relative_source = source_path.relative_to(raw_data_dir).as_posix()
        for raw_row in read_csv_rows(source_path):
            for column in raw_row:
                if column not in raw_columns:
                    raw_columns.append(column)
            record = dict(raw_row)
            record.update(
                {
                    "ingestion_timestamp": ingestion_timestamp,
                    "source_file": relative_source,
                    "source_system": source_system_for(dataset),
                    "batch_id": batch_id,
                    "row_hash": row_hash(raw_row),
                }
            )
            records.append(record)

    collisions = set(raw_columns).intersection(METADATA_COLUMNS)
    if collisions:
        raise ValueError(f"Source column collides with Bronze metadata: {sorted(collisions)}")

    column_order = [*raw_columns, *METADATA_COLUMNS]
    arrays = [
        pa.array([record.get(column) for record in records], type=pa.string())
        for column in column_order
    ]
    return pa.Table.from_arrays(arrays, names=column_order)


def write_bronze_dataset(table: pa.Table, dataset: str, bronze_data_dir: Path) -> Path:
    """Write exactly one Parquet file for a logical Bronze dataset."""
    bronze_data_dir.mkdir(parents=True, exist_ok=True)
    target = bronze_data_dir / f"{dataset}.parquet"
    temporary_target = bronze_data_dir / f".{dataset}.parquet.tmp"
    pq.write_table(table, temporary_target, compression="snappy")
    os.replace(temporary_target, target)
    return target
