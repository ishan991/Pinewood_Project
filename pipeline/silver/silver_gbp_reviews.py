"""Simple Silver transformation for the GBP Reviews Bronze dataset."""

from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRONZE_PATH = PROJECT_ROOT / "data" / "bronze" / "gbp_reviews.parquet"
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "gbp_reviews.parquet"
LOG_PATH = PROJECT_ROOT / "logs" / "silver_transformation.log"

METADATA_COLUMNS = {
    "ingestion_timestamp",
    "source_file",
    "source_system",
    "batch_id",
    "row_hash",
}


def is_blank_like(value):
    """Return True when the value is blank, null-like, or missing."""
    if value is None:
        return True

    if pd.isna(value):
        return True

    if isinstance(value, str):
        cleaned_value = value.strip()
        if cleaned_value == "":
            return True

        if cleaned_value.lower() in {"null", "n/a", "nan", "pd.na", "none"}:
            return True

    return False


def parse_mixed_date_value(value):
    """Convert a date value to pandas datetime or NaT using the supported formats."""
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
    """Find columns that look like date columns and should be standardized."""
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
    """Remove leading and trailing whitespace from every string column using .str.strip()."""
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


def replace_response_text_blank_values(dataframe):
    """Replace blank and null-like values in response_text with the string N/A."""
    updated_to_na = 0

    if "response_text" not in dataframe.columns:
        return updated_to_na

    for row_index, value in dataframe["response_text"].items():
        if is_blank_like(value):
            dataframe.at[row_index, "response_text"] = "N/A"
            updated_to_na += 1

    return updated_to_na


def standardize_date_columns(dataframe):
    """Convert valid date values to dd/MM/yyyy and invalid values to NaT."""
    invalid_dates = 0
    date_columns = identify_date_columns(dataframe)

    for column_name in date_columns:
        converted_values = []

        for value in dataframe[column_name]:
            parsed_value = parse_mixed_date_value(value)

            if pd.isna(parsed_value):
                if is_blank_like(value):
                    converted_values.append(pd.NaT)
                else:
                    invalid_dates += 1
                    converted_values.append(pd.NaT)
            else:
                formatted_value = pd.to_datetime(parsed_value).strftime("%d/%m/%Y")
                converted_values.append(pd.to_datetime(formatted_value, format="%d/%m/%Y"))

        dataframe[column_name] = pd.Series(converted_values, index=dataframe.index)

    return invalid_dates


def append_summary_log(rows_read, rows_written, duplicates_removed, whitespace_trimmed, response_text_updated, invalid_dates):
    """Append the transformation summary to the shared Silver log file."""
    log_path = LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    summary = (
        "=========================================================\n"
        "TABLE : GBP_REVIEWS\n"
        "=========================================================\n\n"
        f"Rows Read                    : {rows_read}\n"
        f"Rows Written                 : {rows_written}\n"
        f"Duplicates Removed           : {duplicates_removed}\n"
        f"Whitespace Trimmed           : {whitespace_trimmed}\n"
        f"response_text Updated to N/A : {response_text_updated}\n"
        f"Invalid Dates               : {invalid_dates}\n"
        "Transformation Status        : PASS\n\n"
        f"Completed At                : {timestamp}\n\n"
        "=========================================================\n\n"
    )

    log_path = log_path.with_name("Silver_tranformation.log")

    with log_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(summary)


def transform_gbp_reviews() -> None:
    """Read Bronze data, clean it, and write the Silver dataset."""
    bronze_df = pd.read_parquet(BRONZE_PATH)
    rows_read = len(bronze_df)

    silver_df = bronze_df.copy()

    # 1) Remove leading and trailing spaces from every string column.
    whitespace_trimmed = trim_string_columns(silver_df)

    # 2) Replace blank values in response_text only with the string "N/A".
    response_text_updated = replace_response_text_blank_values(silver_df)

    # 3) Standardize all date columns to valid pandas date values.
    invalid_dates = standardize_date_columns(silver_df)

    # 4) Remove duplicates using business columns only.
    # Metadata columns are excluded because they describe file ingestion, not the business record.
    rows_before_dedupe = len(silver_df)
    business_columns = [column for column in silver_df.columns if column not in METADATA_COLUMNS]
    silver_df = silver_df.drop_duplicates(subset=business_columns, keep="first")
    rows_after_dedupe = len(silver_df)
    duplicates_removed = rows_before_dedupe - rows_after_dedupe


    # 5) Keep metadata columns unchanged.
    # No metadata columns are being edited in this transformation.

    # 6) Save the transformed dataset to the Silver parquet file.
    SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    silver_df.to_parquet(SILVER_PATH, index=False)

    rows_written = len(silver_df)

    # 7) Append the summary to the shared Silver transformation log file.
    append_summary_log(
        rows_read=rows_read,
        rows_written=rows_written,
        duplicates_removed=duplicates_removed,
        whitespace_trimmed=whitespace_trimmed,
        response_text_updated=response_text_updated,
        invalid_dates=invalid_dates,
    )


if __name__ == "__main__":
    transform_gbp_reviews()
