"""Simple Silver transformation for the Yardi Units Bronze dataset."""

from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRONZE_PATH = PROJECT_ROOT / "data" / "bronze" / "yardi_units.parquet"
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "yardi_units.parquet"
LOG_PATH = PROJECT_ROOT / "logs" / "Silver_tranformation.log"

METADATA_COLUMNS = {
    "ingestion_timestamp",
    "source_file",
    "source_system",
    "batch_id",
    "row_hash",
}

UNIT_TYPE_MAP = {
    "IL": "Independent Living",
    "Independent": "Independent Living",
    "Independent Living": "Independent Living",
    "AL": "Assisted Living",
    "Assisted": "Assisted Living",
    "Assisted Living": "Assisted Living",
    "MC": "Memory Care",
    "Memory": "Memory Care",
    "Memory Care": "Memory Care",
}


def trim_string_columns(dataframe):
    """Remove leading and trailing spaces from every string column using .str.strip()."""
    whitespace_trimmed = 0

    for column_name in dataframe.columns:
        if column_name in METADATA_COLUMNS:
            continue

        if dataframe[column_name].dtype == "object":
            original_series = dataframe[column_name]
            trimmed_series = original_series.str.strip()
            changed_mask = original_series.notna() & trimmed_series.notna() & (trimmed_series != original_series)
            whitespace_trimmed += int(changed_mask.sum())
            dataframe[column_name] = trimmed_series

    return whitespace_trimmed


def parse_mixed_date_value(value):
    """Convert a single value to datetime or NaT using YYYY-MM-DD or MM/DD/YYYY."""
    if value is None:
        return pd.NaT

    if isinstance(value, str):
        cleaned_value = value.strip()
        if cleaned_value == "":
            return pd.NaT

        for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return pd.to_datetime(cleaned_value, format=date_format, errors="raise")
            except (TypeError, ValueError):
                continue

        try:
            return pd.to_datetime(cleaned_value, errors="raise")
        except (TypeError, ValueError):
            return pd.NaT

    try:
        return pd.to_datetime(value, errors="raise")
    except (TypeError, ValueError):
        return pd.NaT


def standardize_date_columns(dataframe, column_name):
    """Convert a date column to datetime and send invalid values to NaT."""
    converted_values = []
    invalid_dates = 0

    for value in dataframe[column_name]:
        parsed_value = parse_mixed_date_value(value)

        if pd.isna(parsed_value):
            if value is None:
                converted_values.append(pd.NaT)
            elif isinstance(value, str) and value.strip() == "":
                converted_values.append(pd.NaT)
            else:
                invalid_dates += 1
                converted_values.append(pd.NaT)
        else:
            converted_values.append(pd.to_datetime(parsed_value))

    dataframe[column_name] = pd.Series(converted_values, index=dataframe.index)
    return invalid_dates


def standardize_unit_type(dataframe):
    """Apply the standard unit type mapping to the unit_type column."""
    updated_count = 0

    for row_index, value in dataframe["unit_type"].items():
        if pd.isna(value):
            continue

        if not isinstance(value, str):
            continue

        cleaned_value = value.strip()
        if cleaned_value in UNIT_TYPE_MAP:
            dataframe.at[row_index, "unit_type"] = UNIT_TYPE_MAP[cleaned_value]
            updated_count += 1

    return updated_count


def append_summary_log(rows_read, rows_written, duplicates_removed, whitespace_trimmed, unit_types_standardized, invalid_dates):
    """Append the transformation summary to the shared Silver log file without printing."""
    log_path = LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = (
        "=========================================================\n"
        "TABLE : YARDI_UNITS\n"
        "=========================================================\n\n"
        f"Rows Read                    : {rows_read}\n"
        f"Rows Written                 : {rows_written}\n"
        f"Duplicates Removed           : {duplicates_removed}\n"
        f"Whitespace Trimmed           : {whitespace_trimmed}\n"
        f"Unit Types Standardized      : {unit_types_standardized}\n"
        f"Invalid Dates               : {invalid_dates}\n"
        "Transformation Status        : PASS\n\n"
        f"Completed At                : {timestamp}\n\n"
        "=========================================================\n\n"
    )

    with log_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(summary)


def transform_yardi_units() -> None:
    """Read Bronze data, clean it, and write the Silver dataset."""
    # Step 1: Read the Bronze parquet file.
    bronze_df = pd.read_parquet(BRONZE_PATH)
    rows_read = len(bronze_df)

    # Step 2: Work on a copy so the original Bronze data stays safe.
    silver_df = bronze_df.copy()

    # Step 3: Trim any leading and trailing spaces from string columns.
    whitespace_trimmed = trim_string_columns(silver_df)

    # Step 4: Standardize unit_type values.
    unit_types_standardized = standardize_unit_type(silver_df)

    # Step 5: Convert snapshot_date to a real datetime column.
    invalid_dates = standardize_date_columns(silver_df, "snapshot_date")

    # Step 6: Remove duplicates using business columns only.
    # Metadata columns are excluded because they describe file ingestion, not the business record.
    rows_before_dedupe = len(silver_df)
    business_columns = [column for column in silver_df.columns if column not in METADATA_COLUMNS]
    silver_df = silver_df.drop_duplicates(subset=business_columns, keep="first")
    rows_after_dedupe = len(silver_df)
    duplicates_removed = rows_before_dedupe - rows_after_dedupe

    # Step 7: Keep metadata columns unchanged.
    # We do not modify ingestion_timestamp, source_file, source_system, batch_id, or row_hash.

    # Step 8: Save the sanitized dataset to the Silver parquet file.
    SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    silver_df.to_parquet(SILVER_PATH, index=False)

    rows_written = len(silver_df)

    # Step 9: Append the summary to the shared Silver log file.
    append_summary_log(
        rows_read=rows_read,
        rows_written=rows_written,
        duplicates_removed=duplicates_removed,
        whitespace_trimmed=whitespace_trimmed,
        unit_types_standardized=unit_types_standardized,
        invalid_dates=invalid_dates,
    )


if __name__ == "__main__":
    transform_yardi_units()
