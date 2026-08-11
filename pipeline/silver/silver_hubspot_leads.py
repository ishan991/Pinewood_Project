"""Simple Silver transformation for the HubSpot Leads Bronze dataset."""

from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRONZE_PATH = PROJECT_ROOT / "data" / "bronze" / "hubspot_leads.parquet"
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "hubspot_leads.parquet"
LOG_PATH = PROJECT_ROOT / "logs" / "Silver_tranformation.log"

METADATA_COLUMNS = {
    "ingestion_timestamp",
    "source_file",
    "source_system",
    "batch_id",
    "row_hash",
}

DATE_COLUMNS = [
    "created_date",
    "tour_date",
    "deposit_date",
    "move_in_date",
]


def is_blank_like(value):
    """Return True when a value is blank, null, or missing."""
    if value is None:
        return True

    if pd.isna(value):
        return True

    if isinstance(value, str):
        cleaned_value = value.strip()
        if cleaned_value == "":
            return True
        if cleaned_value.lower() in {"null", "nan", "n/a", "pd.na", "none"}:
            return True

    return False


def trim_string_columns(dataframe):
    """Remove leading and trailing spaces from every string column using .str.strip()."""
    whitespace_trimmed = 0

    # Loop through every column in the dataset.
    for column_name in dataframe.columns:
        # Skip metadata columns because we are told to preserve them.
        if column_name in METADATA_COLUMNS:
            continue

        # Only work on object/string columns.
        if dataframe[column_name].dtype == "object":
            original_series = dataframe[column_name]
            trimmed_series = original_series.str.strip()
            changed_mask = original_series.notna() & trimmed_series.notna() & (trimmed_series != original_series)
            whitespace_trimmed += int(changed_mask.sum())
            dataframe[column_name] = trimmed_series

    return whitespace_trimmed


def parse_mixed_date_value(value):
    """Convert a single date value to datetime or NaT using either YYYY-MM-DD or MM/DD/YYYY."""
    if value is None:
        return pd.NaT

    if isinstance(value, str):
        cleaned_value = value.strip()
        if cleaned_value == "":
            return pd.NaT

        # Try the ISO date format first.
        for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return pd.to_datetime(cleaned_value, format=date_format, errors="raise")
            except (TypeError, ValueError):
                continue

        # If neither pattern matches, let pandas decide.
        try:
            return pd.to_datetime(cleaned_value, errors="raise")
        except (TypeError, ValueError):
            return pd.NaT

    try:
        return pd.to_datetime(value, errors="raise")
    except (TypeError, ValueError):
        return pd.NaT


def standardize_date_columns(dataframe, date_columns):
    """Convert valid date values to pandas datetime and send invalid or blank values to NaT."""
    invalid_dates = 0

    # Loop through each date column in the list provided.
    for column_name in date_columns:
        if column_name not in dataframe.columns:
            continue

        converted_values = []

        # Read one value at a time and convert it safely.
        for value in dataframe[column_name]:
            parsed_value = parse_mixed_date_value(value)

            if pd.isna(parsed_value):
                # Blank values and invalid values must both become NaT.
                if is_blank_like(value):
                    converted_values.append(pd.NaT)
                else:
                    invalid_dates += 1
                    converted_values.append(pd.NaT)
            else:
                converted_values.append(pd.to_datetime(parsed_value))

        dataframe[column_name] = pd.Series(converted_values, index=dataframe.index)

    return invalid_dates


def replace_blank_lost_reasons(dataframe):
    """Replace blank or missing lost_reason values with the string 'N/A'."""
    updated_count = 0

    if "lost_reason" not in dataframe.columns:
        return updated_count

    # Loop through each value in the column.
    for row_index, current_value in dataframe["lost_reason"].items():
        if is_blank_like(current_value):
            dataframe.at[row_index, "lost_reason"] = "N/A"
            updated_count += 1

    return updated_count


def remove_exact_duplicates(dataframe):
    """Remove duplicate rows based only on non-metadata columns."""
    rows_before = len(dataframe)
    business_columns = [column for column in dataframe.columns if column not in METADATA_COLUMNS]
    dataframe = dataframe.drop_duplicates(subset=business_columns, keep="first")
    rows_after = len(dataframe)
    duplicates_removed = rows_before - rows_after

    return dataframe, duplicates_removed


def log_silver_transformation(rows_read, rows_written, duplicates_removed, whitespace_trimmed, lost_reasons_updated, invalid_dates):
    """Append a clean summary to the Silver transformation log without printing to the console."""
    log_path = LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    summary = (
        "=========================================================\n"
        "TABLE : HUBSPOT_LEADS\n"
        "=========================================================\n\n"
        f"Rows Read                  : {rows_read}\n"
        f"Rows Written               : {rows_written}\n"
        f"Duplicates Removed         : {duplicates_removed}\n"
        f"Whitespace Trimmed         : {whitespace_trimmed}\n"
        f"Lost Reasons Updated       : {lost_reasons_updated}\n"
        f"Invalid Dates             : {invalid_dates}\n"
        "Transformation Status      : PASS\n\n"
        f"Completed At              : {timestamp}\n\n"
        "=========================================================\n\n"
    )

    with log_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(summary)


def transform_hubspot_leads() -> None:
    """Read the Bronze data, clean it, and save the Silver dataset."""
    # Step 1: Read the Bronze parquet file.
    bronze_df = pd.read_parquet(BRONZE_PATH)
    rows_read = len(bronze_df)

    # Step 2: Work on a copy so the original Bronze data remains untouched.
    silver_df = bronze_df.copy()

    # Step 3: Trim leading and trailing spaces from every string column.
    whitespace_trimmed = trim_string_columns(silver_df)

    # Step 4: Standardize the required date columns and convert invalid values to NaT.
    invalid_dates = standardize_date_columns(silver_df, DATE_COLUMNS)

    # Step 5: Replace blank or null lost_reason values with 'N/A'.
    lost_reasons_updated = replace_blank_lost_reasons(silver_df)

    # Step 6: Remove only fully identical rows.
    silver_df, duplicates_removed = remove_exact_duplicates(silver_df)

    # Step 7: Preserve metadata columns as they are.
    # We do not change ingestion_timestamp, source_file, source_system, batch_id, or row_hash.

    # Step 8: Save the cleaned data to the Silver parquet file.
    SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    silver_df.to_parquet(SILVER_PATH, index=False)

    rows_written = len(silver_df)

    # Step 9: Append the summary to the Silver log without printing anything.
    log_silver_transformation(
        rows_read=rows_read,
        rows_written=rows_written,
        duplicates_removed=duplicates_removed,
        whitespace_trimmed=whitespace_trimmed,
        lost_reasons_updated=lost_reasons_updated,
        invalid_dates=invalid_dates,
    )


if __name__ == "__main__":
    transform_hubspot_leads()
