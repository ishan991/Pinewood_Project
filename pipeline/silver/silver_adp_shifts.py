"""Simple Silver transformation for the ADP Shifts Bronze dataset."""

import ast
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRONZE_PATH = PROJECT_ROOT / "data" / "bronze" / "adp_shifts.parquet"
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "adp_shifts.parquet"
LOG_PATH = PROJECT_ROOT / "logs" / "Silver_tranformation.log"

METADATA_COLUMNS = {
    "ingestion_timestamp",
    "source_file",
    "source_system",
    "batch_id",
    "row_hash",
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
    """Convert the chosen date column to proper datetime values and send bad dates to NaT."""
    invalid_dates = 0
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


def parse_hourly_rate_dictionary(value):
    """Safely convert the hourly_rate field into a dictionary if possible."""
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        cleaned_value = value.strip()
        if cleaned_value == "":
            return {}

        try:
            return ast.literal_eval(cleaned_value)
        except (ValueError, SyntaxError):
            return {}

    return {}


def create_standard_hourly_rate(dataframe):
    """Use each row's role to look up the correct hourly rate from the dictionary."""
    standard_rate_values = []

    for row_index, row in dataframe.iterrows():
        role = row.get("role")
        hourly_rate_value = row.get("hourly_rate")
        parsed_dictionary = parse_hourly_rate_dictionary(hourly_rate_value)

        if not isinstance(role, str):
            standard_rate_values.append(pd.NA)
            continue

        cleaned_role = role.strip()

        if cleaned_role in parsed_dictionary:
            standard_rate_values.append(parsed_dictionary[cleaned_role])
        else:
            standard_rate_values.append(pd.NA)

    dataframe["Standard_Hourly_Rate"] = pd.Series(standard_rate_values, index=dataframe.index)
    return int(dataframe["Standard_Hourly_Rate"].notna().sum())


def create_total_labor_cost(dataframe):
    """Multiply hours_worked by the standard hourly rate to get total labor cost."""
    total_cost_values = []
    total_cost_created = 0

    for row_index, row in dataframe.iterrows():
        hours_value = row.get("hours_worked")
        rate_value = row.get("Standard_Hourly_Rate")

        try:
            hours_numeric = float(hours_value)
            rate_numeric = float(rate_value)
            total_cost = hours_numeric * rate_numeric
            total_cost_values.append(total_cost)
            total_cost_created += 1
        except (TypeError, ValueError):
            total_cost_values.append(pd.NA)

    dataframe["Total_Labor_Cost"] = pd.Series(total_cost_values, index=dataframe.index)
    return total_cost_created


def remove_exact_duplicates(dataframe):
    """Remove duplicate rows based only on non-metadata columns."""
    rows_before = len(dataframe)
    business_columns = [column for column in dataframe.columns if column not in METADATA_COLUMNS]
    dataframe = dataframe.drop_duplicates(subset=business_columns, keep="first")
    rows_after = len(dataframe)
    duplicates_removed = rows_before - rows_after

    return dataframe, duplicates_removed


def append_summary_log(rows_read, rows_written, duplicates_removed, whitespace_trimmed, standard_hourly_rate_created, total_labor_cost_created, invalid_dates):
    """Append the summary to the shared Silver log file without printing it."""
    log_path = LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = (
        "=========================================================\n"
        "TABLE : ADP_SHIFTS\n"
        "=========================================================\n\n"
        f"Rows Read                  : {rows_read}\n"
        f"Rows Written               : {rows_written}\n"
        f"Duplicates Removed         : {duplicates_removed}\n"
        f"Whitespace Trimmed         : {whitespace_trimmed}\n"
        f"Standard Hourly Rate Created : {standard_hourly_rate_created}\n"
        f"Total Labor Cost Created   : {total_labor_cost_created}\n"
        f"Invalid Dates             : {invalid_dates}\n"
        "Transformation Status      : PASS\n\n"
        f"Completed At              : {timestamp}\n\n"
        "=========================================================\n\n"
    )

    with log_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(summary)


def transform_adp_shifts() -> None:
    """Read Bronze data, clean it, and write the Silver dataset."""
    # Step 1: Read the Bronze parquet file.
    bronze_df = pd.read_parquet(BRONZE_PATH)
    rows_read = len(bronze_df)

    # Step 2: Work on a copy so the raw Bronze data stays intact.
    silver_df = bronze_df.copy()

    # Step 3: Remove leading and trailing spaces from every string column.
    whitespace_trimmed = trim_string_columns(silver_df)

    # Step 4: Convert the shift_date column to a proper datetime dtype.
    invalid_dates = standardize_date_columns(silver_df, "shift_date")

    # Step 5: Extract the hourly rate for each row based on that row's role and the dictionary in hourly_rate.
    standard_hourly_rate_created = create_standard_hourly_rate(silver_df)

    # Step 6: Create the total labor cost by multiplying hours worked by the standard hourly rate.
    total_labor_cost_created = create_total_labor_cost(silver_df)

    # Step 7: Remove the original raw hourly-rate dictionary so the Silver output keeps the cleaned result only.
    if "hourly_rate" in silver_df.columns:
        silver_df = silver_df.drop(columns=["hourly_rate"])

    # Step 8: Remove exact duplicate rows only.
    silver_df, duplicates_removed = remove_exact_duplicates(silver_df)

    # Step 8: Keep metadata columns unchanged.
    # We do not modify ingestion_timestamp, source_file, source_system, batch_id, or row_hash.

    # Step 9: Save the transformed dataset to the Silver parquet file.
    SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    silver_df.to_parquet(SILVER_PATH, index=False)

    rows_written = len(silver_df)

    # Step 10: Append the summary to the shared Silver log file.
    append_summary_log(
        rows_read=rows_read,
        rows_written=rows_written,
        duplicates_removed=duplicates_removed,
        whitespace_trimmed=whitespace_trimmed,
        standard_hourly_rate_created=standard_hourly_rate_created,
        total_labor_cost_created=total_labor_cost_created,
        invalid_dates=invalid_dates,
    )


if __name__ == "__main__":
    transform_adp_shifts()
