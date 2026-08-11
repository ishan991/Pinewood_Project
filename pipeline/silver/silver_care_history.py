"""Simple Silver transformation for the pcc_care_history Bronze dataset."""

from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRONZE_PATH = PROJECT_ROOT / "data" / "bronze" / "pcc_care_history.parquet"
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "pcc_care_history.parquet"
LOG_PATH = PROJECT_ROOT / "logs" / "Silver_tranformation.log"

METADATA_COLUMNS = {
    "ingestion_timestamp",
    "source_file",
    "source_system",
    "batch_id",
    "row_hash",
}

CARE_LEVEL_MAP = {
    "AL": "Assisted Living",
    "Assisted": "Assisted Living",
    "Assisted Living": "Assisted Living",
    "IL": "Independent Living",
    "Independent": "Independent Living",
    "Independent Living": "Independent Living",
    "MC": "Memory Care",
    "Memory": "Memory Care",
    "Memory Care": "Memory Care",
}


def parse_mixed_date_value(value):
    """Convert a date value to datetime or NaT using either YYYY-MM-DD or MM/DD/YYYY."""
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


def identify_date_columns(dataframe):
    """Detect columns that appear to store dates so we can standardize them."""
    date_columns = []

    for column_name in dataframe.columns:
        if column_name in METADATA_COLUMNS:
            continue

        sample_values = dataframe[column_name].dropna().head(10)
        if sample_values.empty:
            continue

        is_date_like = True

        for value in sample_values:
            if pd.isna(value):
                continue

            if not isinstance(value, str):
                continue

            cleaned_value = value.strip()
            if cleaned_value == "":
                continue

            parsed = False
            for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
                try:
                    pd.to_datetime(cleaned_value, format=date_format, errors="raise")
                    parsed = True
                    break
                except (TypeError, ValueError):
                    continue

            if not parsed:
                is_date_like = False
                break

        if is_date_like:
            date_columns.append(column_name)

    return date_columns


def trim_string_columns(dataframe):
    """Remove leading and trailing spaces from every string column."""
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


def standardize_care_level_column(dataframe, column_name):
    """Apply the care-level mapping to a single column and count how many values changed."""
    if column_name not in dataframe.columns:
        return 0

    updated_count = 0

    for row_index, value in dataframe[column_name].items():
        if pd.isna(value):
            continue

        if not isinstance(value, str):
            continue

        cleaned_value = value.strip()
        if cleaned_value in CARE_LEVEL_MAP:
            dataframe.at[row_index, column_name] = CARE_LEVEL_MAP[cleaned_value]
            updated_count += 1

    return updated_count


def append_summary_log(rows_read, rows_written, duplicates_removed, whitespace_trimmed, previous_level_updated, new_level_updated, invalid_dates):
    """Append the summary to the shared Silver log file without printing to the console."""
    log_path = LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = (
        "=========================================================\n"
        "TABLE : PCC_CARE_HISTORY\n"
        "=========================================================\n\n"
        f"Rows Read                    : {rows_read}\n"
        f"Rows Written                 : {rows_written}\n"
        f"Duplicates Removed           : {duplicates_removed}\n"
        f"Whitespace Trimmed           : {whitespace_trimmed}\n"
        f"Previous Level Standardized  : {previous_level_updated}\n"
        f"New Level Standardized       : {new_level_updated}\n"
        f"Invalid Dates               : {invalid_dates}\n"
        "Transformation Status        : PASS\n\n"
        f"Completed At                : {timestamp}\n\n"
        "=========================================================\n\n"
    )

    with log_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(summary)


def transform_pcc_care_history() -> None:
    """Read Bronze care history, clean it, and write the Silver dataset."""
    # Step 1: Read the Bronze parquet file.
    bronze_df = pd.read_parquet(BRONZE_PATH)
    rows_read = len(bronze_df)

    # Step 2: Work on a copy so the original Bronze data stays intact.
    silver_df = bronze_df.copy()

    # Step 3: Remove leading and trailing spaces from every string column.
    whitespace_trimmed = trim_string_columns(silver_df)

    # Step 4: Standardize both care level columns using the mapping provided.
    previous_level_updated = standardize_care_level_column(silver_df, "previous_level")
    new_level_updated = standardize_care_level_column(silver_df, "new_level")

    # Step 5: Standardize date columns to dd/MM/yyyy.
    invalid_dates = 0
    date_columns = identify_date_columns(silver_df)

    for column_name in date_columns:
        converted_values = []

        for value in silver_df[column_name]:
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
                formatted_value = pd.to_datetime(parsed_value).strftime("%d/%m/%Y")
                converted_values.append(pd.to_datetime(formatted_value, format="%d/%m/%Y"))

        silver_df[column_name] = pd.Series(converted_values, index=silver_df.index)

    # Step 6: Remove duplicates using business columns only.
    # Metadata columns are excluded because they describe file ingestion, not the business record.
    rows_before_dedupe = len(silver_df)
    business_columns = [column for column in silver_df.columns if column not in METADATA_COLUMNS]
    silver_df = silver_df.drop_duplicates(subset=business_columns, keep="first")
    rows_after_dedupe = len(silver_df)
    duplicates_removed = rows_before_dedupe - rows_after_dedupe

    # Step 7: Keep metadata columns unchanged.
    # We are not modifying ingestion_timestamp, source_file, source_system, batch_id, or row_hash.

    # Step 8: Save the cleaned DataFrame to the Silver parquet file.
    SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    silver_df.to_parquet(SILVER_PATH, index=False)

    rows_written = len(silver_df)

    # Step 9: Append the summary to the shared Silver log file.
    append_summary_log(
        rows_read=rows_read,
        rows_written=rows_written,
        duplicates_removed=duplicates_removed,
        whitespace_trimmed=whitespace_trimmed,
        previous_level_updated=previous_level_updated,
        new_level_updated=new_level_updated,
        invalid_dates=invalid_dates,
    )


if __name__ == "__main__":
    transform_pcc_care_history()
