"""Simple Silver transformation for the pcc_incidents Bronze dataset."""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRONZE_PATH = PROJECT_ROOT / "data" / "bronze" / "pcc_incidents.parquet"
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "pcc_incidents.parquet"

METADATA_COLUMNS = {
    "ingestion_timestamp",
    "source_file",
    "source_system",
    "batch_id",
    "row_hash",
}


def clean_blank_values(value):
    """Return pandas.NA for blank-like or null-like values."""
    if value is None:
        return pd.NA

    if isinstance(value, str):
        stripped_value = value.strip()
        if stripped_value in {"", "N/A", "NULL", "null", "None", "none"}:
            return pd.NA

    return value


def parse_mixed_date_value(value):
    """Convert a single value to datetime or NaT using the supported date formats."""
    if value is None:
        return pd.NaT

    if isinstance(value, str):
        clean_value = value.strip()
        if clean_value in {"", "N/A", "NULL", "null", "None", "none"}:
            return pd.NaT

        for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return pd.to_datetime(clean_value, format=date_format, errors="raise")
            except (TypeError, ValueError):
                continue

        return pd.NaT

    try:
        return pd.to_datetime(value, errors="raise")
    except (TypeError, ValueError):
        return pd.NaT


def detect_date_columns(dataframe):
    """Find columns that look like dates so we can standardize them."""
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

            stripped_value = value.strip()
            if stripped_value == "":
                continue

            valid_formats = [
                "%Y-%m-%d",
                "%m/%d/%Y",
            ]

            parsed = False
            for date_format in valid_formats:
                try:
                    pd.to_datetime(stripped_value, format=date_format, errors="raise")
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


def transform_pcc_incidents() -> None:
    """Read Bronze incidents, clean, standardize, and write Silver output."""
    # Step 1: Read the Bronze parquet file.
    bronze_df = pd.read_parquet(BRONZE_PATH)
    rows_read = len(bronze_df)

    # Step 2: Work on a copy so the raw Bronze data stays safe.
    silver_df = bronze_df.copy()

    # Step 3: Replace blank values with pandas.NA.
    # This makes missing values consistent before later cleaning and conversion.
    blank_values_replaced = 0

    for column_name in silver_df.columns:
        if column_name in METADATA_COLUMNS:
            continue

        for row_index, value in silver_df[column_name].items():
            cleaned_value = clean_blank_values(value)
            if cleaned_value is pd.NA:
                silver_df.at[row_index, column_name] = pd.NA
                blank_values_replaced += 1
            else:
                silver_df.at[row_index, column_name] = cleaned_value

    # Step 4: Remove leading and trailing spaces from each string column.
    # This avoids values like " 2025-01-01 " and " 123 " being treated differently.
    whitespace_trimmed = 0

    for column_name in silver_df.columns:
        if column_name in METADATA_COLUMNS:
            continue

        for row_index, value in silver_df[column_name].items():
            if isinstance(value, str):
                trimmed_value = value.strip()
                silver_df.at[row_index, column_name] = trimmed_value
                whitespace_trimmed += 1

    # Step 5: Detect date columns automatically.
    # We do this so the code is not hard-coded to a few columns only.
    date_columns = detect_date_columns(silver_df)

    invalid_dates = 0

    for column_name in date_columns:
        converted_values = []

        for value in silver_df[column_name]:
            parsed_value = parse_mixed_date_value(value)

            if pd.isna(parsed_value):
                if value is None:
                    converted_values.append(pd.NaT)
                elif isinstance(value, str) and value.strip() in {"", "N/A", "NULL", "null", "None", "none"}:
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

    # Step 7: Keep all metadata columns unchanged.
    # These columns are used for lineage and traceability, so we do not alter them.

    # Step 8: Save the cleaned DataFrame to the Silver parquet file.
    SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    silver_df.to_parquet(SILVER_PATH, index=False)

    # Step 9: Save the validation summary to the shared log file without printing it.
    rows_written = len(silver_df)
    timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    summary = (
        "=========================================================\n"
        "TABLE : PCC_INCIDENTS\n"
        "=========================================================\n\n"
        f"Rows Read                    : {rows_read}\n"
        f"Rows Written                 : {rows_written}\n"
        f"Duplicates Removed           : {duplicates_removed}\n"
        f"Blank Values Replaced       : {blank_values_replaced}\n"
        f"Whitespace Trimmed           : {whitespace_trimmed}\n"
        f"Invalid Dates               : {invalid_dates}\n"
        "Transformation Status        : PASS\n\n"
        f"Completed At                : {timestamp}\n\n"
        "=========================================================\n\n"
    )

    log_folder = PROJECT_ROOT / "logs"
    log_folder.mkdir(parents=True, exist_ok=True)
    log_file = log_folder / "Silver_tranformation.log"

    with log_file.open("a", encoding="utf-8") as file_handle:
        file_handle.write(summary)


if __name__ == "__main__":
    transform_pcc_incidents()
