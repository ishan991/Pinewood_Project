"""Simple Silver transformation for the Yardi Leases Bronze dataset."""

from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRONZE_PATH = PROJECT_ROOT / "data" / "bronze" / "yardi_leases.parquet"
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "yardi_leases.parquet"
LOG_PATH = PROJECT_ROOT / "logs" / "Silver_tranformation.log"

METADATA_COLUMNS = {
    "ingestion_timestamp",
    "source_file",
    "source_system",
    "batch_id",
    "row_hash",
}

DATE_COLUMNS = ["move_in_date", "move_out_date"]


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
    """Convert a single value to datetime or NaT using the valid date formats."""
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


def standardize_date_columns(dataframe, date_columns):
    """Convert the selected date columns to datetime values and send invalid values to NaT."""
    invalid_dates = 0

    for column_name in date_columns:
        if column_name not in dataframe.columns:
            continue

        converted_values = []

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


def remove_exact_duplicates(dataframe):
    """Remove duplicate rows based only on non-metadata columns."""
    rows_before = len(dataframe)
    business_columns = [column for column in dataframe.columns if column not in METADATA_COLUMNS]
    dataframe = dataframe.drop_duplicates(subset=business_columns, keep="first")
    rows_after = len(dataframe)
    duplicates_removed = rows_before - rows_after

    return dataframe, duplicates_removed


def append_summary_log(rows_read, rows_written, duplicates_removed, whitespace_trimmed, invalid_dates):
    """Append the summary to the shared Silver log file without printing."""
    log_path = LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = (
        "=========================================================\n"
        "TABLE : YARDI_LEASES\n"
        "=========================================================\n\n"
        f"Rows Read                    : {rows_read}\n"
        f"Rows Written                 : {rows_written}\n"
        f"Duplicates Removed           : {duplicates_removed}\n"
        f"Whitespace Trimmed           : {whitespace_trimmed}\n"
        f"Invalid Dates               : {invalid_dates}\n"
        "Transformation Status        : PASS\n\n"
        f"Completed At                : {timestamp}\n\n"
        "=========================================================\n\n"
    )

    with log_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(summary)


def transform_yardi_leases() -> None:
    """Read Bronze data, clean it, and write the Silver dataset."""
    # Step 1: Read the Bronze parquet file.
    bronze_df = pd.read_parquet(BRONZE_PATH)
    rows_read = len(bronze_df)

    # Step 2: Work on a copy so the raw Bronze data stays intact.
    silver_df = bronze_df.copy()

    # Step 3: Remove leading and trailing spaces from every string column.
    whitespace_trimmed = trim_string_columns(silver_df)

    # Step 4: Convert date columns to proper datetime data types.
    invalid_dates = standardize_date_columns(silver_df, DATE_COLUMNS)

    # Step 5: Remove exact duplicate rows only.
    silver_df, duplicates_removed = remove_exact_duplicates(silver_df)

    # Step 6: Preserve metadata columns exactly as they were loaded.
    # We do not modify ingestion_timestamp, source_file, source_system, batch_id, or row_hash.

    # Step 7: Save the cleaned dataset to the Silver parquet file.
    SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    silver_df.to_parquet(SILVER_PATH, index=False)

    rows_written = len(silver_df)

    # Step 8: Append the transformation summary to the shared Silver log.
    append_summary_log(
        rows_read=rows_read,
        rows_written=rows_written,
        duplicates_removed=duplicates_removed,
        whitespace_trimmed=whitespace_trimmed,
        invalid_dates=invalid_dates,
    )


if __name__ == "__main__":
    transform_yardi_leases()
