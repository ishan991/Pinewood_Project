"""Simple Silver transformation for the pcc_residents Bronze dataset."""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRONZE_PATH = PROJECT_ROOT / "data" / "bronze" / "pcc_residents.parquet"
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "pcc_residents.parquet"

METADATA_COLUMNS = {
    "ingestion_timestamp",
    "source_file",
    "source_system",
    "batch_id",
    "row_hash",
}

CARE_LEVEL_MAP = {
    "al": "Assisted Living",
    "assisted": "Assisted Living",
    "assisted living": "Assisted Living",
    "il": "Independent Living",
    "independent": "Independent Living",
    "independent living": "Independent Living",
    "mc": "Memory Care",
    "memory": "Memory Care",
    "memory care": "Memory Care",
}

DATE_COLUMNS = ["dob", "admit_date", "discharge_date"]


def parse_mixed_date_value(value):
    """Convert a single value to a pandas datetime or NaT using the supported date formats."""
    if value is None:
        return pd.NaT

    if isinstance(value, str):
        clean_value = value.strip()
        if clean_value == "" or clean_value.lower() in {"n/a", "null", "none"}:
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


def transform_pcc_residents() -> None:
    """Read Bronze data, clean it, and write the Silver dataset."""
    # Step 1: Read the Bronze parquet file.
    # We start from the raw Bronze layer so the Silver layer can clean and standardize it.
    bronze_df = pd.read_parquet(BRONZE_PATH)
    rows_read = len(bronze_df)

    # Step 2: Make a copy before changing anything.
    # This keeps the original Bronze data intact and makes debugging much easier.
    silver_df = bronze_df.copy()

    # Step 2: Replace blank and null-like values in non-metadata columns with pandas.NA.
    # This makes missing values consistent before trimming and date conversion.
    for column_name in silver_df.columns:
        if column_name in METADATA_COLUMNS:
            continue

        for row_index, value in silver_df[column_name].items():
            if pd.isna(value):
                silver_df.at[row_index, column_name] = pd.NA
                continue

            if isinstance(value, str):
                trimmed_value = value.strip()
                if trimmed_value in ["", "N/A", "NULL", "null", "None", "none"]:
                    silver_df.at[row_index, column_name] = pd.NA

    # Step 3: Trim any leading and trailing spaces from string values.
    # This avoids problems like values being stored as " Assisted Living " instead of "Assisted Living".
    for column_name in silver_df.columns:
        if column_name in METADATA_COLUMNS:
            continue

        for row_index, value in silver_df[column_name].items():
            if isinstance(value, str):
                updated_value = value.strip()
                silver_df.at[row_index, column_name] = updated_value

    # Step 4: Standardize the care_level column to the required labels.
    # This keeps values consistent across the dataset and avoids mixed labels like AL and Assisted Living.
    unknown_care_levels = []
    care_levels_standardized = 0

    if "care_level" in silver_df.columns:
        for row_index, value in silver_df["care_level"].items():
            if pd.isna(value):
                continue

            if not isinstance(value, str):
                continue

            normalized_value = value.strip().lower()

            if normalized_value in CARE_LEVEL_MAP:
                silver_df.at[row_index, "care_level"] = CARE_LEVEL_MAP[normalized_value]
                care_levels_standardized += 1
            else:
                unknown_care_levels.append(value)

    # Step 5: Convert the required date columns to pandas datetime values.
    # We parse both YYYY-MM-DD and MM/DD/YYYY, then format every valid value as dd/MM/yyyy.
    # Blank values should stay blank, and invalid values should become NaT.
    date_summary = {}

    for column_name in DATE_COLUMNS:
        if column_name not in silver_df.columns:
            continue

        blank_count = 0
        invalid_count = 0
        successful_count = 0
        converted_values = []

        for value in silver_df[column_name]:
            parsed_value = parse_mixed_date_value(value)

            if pd.isna(parsed_value):
                if value is None:
                    blank_count += 1
                elif isinstance(value, str) and value.strip() in {"", "N/A", "NULL", "null", "None", "none"}:
                    blank_count += 1
                else:
                    invalid_count += 1

                converted_values.append(pd.NaT)
            else:
                formatted_value = pd.to_datetime(parsed_value).strftime("%d-%m-%Y")
                converted_values.append(pd.to_datetime(formatted_value, format="%d-%m-%Y"))
                successful_count += 1

        silver_df[column_name] = pd.Series(converted_values, index=silver_df.index)
        date_summary[column_name] = {
            "Blank Dates": blank_count,
            "Invalid Date Formats": invalid_count,
            "Successfully Converted Dates": successful_count,
        }

    # Step 6: Add the last date of the source file month.
    # Example: pcc_residents_2025_02.csv becomes 2025-02-28.
    source_month = silver_df["source_file"].str.extract(r"_(\d{4})_(\d{2})\.csv$")
    month_first_date = pd.to_datetime(
        source_month[0] + "-" + source_month[1] + "-01",
        errors="coerce",
    )
    silver_df["last_date"] = month_first_date + pd.offsets.MonthEnd(0)

    # Step 7: Add a status column based on the snapshot month from source_file.
    # This tells us whether each resident was active during the monthly snapshot period.
    status_values = []
    active_count = 0
    not_active_count = 0

    for row_index, row in silver_df.iterrows():
        source_file = row.get("source_file")
        admit_date = row.get("admit_date")
        discharge_date = row.get("discharge_date")

        status = "Not Active"

        if isinstance(source_file, str):
            file_name = source_file.split("/")[-1]
            if file_name.endswith(".csv"):
                file_name_without_ext = file_name[:-4]
                parts = file_name_without_ext.split("_")
                if len(parts) >= 3:
                    year = int(parts[-2])
                    month = int(parts[-1])
                    snapshot_first_day = pd.Timestamp(year=year, month=month, day=1)
                    snapshot_last_day = snapshot_first_day + pd.offsets.MonthEnd(0)

                    admit_is_before_month_end = pd.notna(admit_date) and admit_date <= snapshot_last_day
                    discharge_is_blank = pd.isna(discharge_date)
                    discharge_is_in_month = pd.notna(discharge_date) and discharge_date >= snapshot_first_day

                    if admit_is_before_month_end and (discharge_is_blank or discharge_is_in_month):
                        status = "Active"
                    elif admit_date is not pd.NaT and admit_date > snapshot_last_day:
                        status = "Not Active"
                    elif pd.notna(discharge_date) and discharge_date < snapshot_first_day:
                        status = "Not Active"

        status_values.append(status)

        if status == "Active":
            active_count += 1
        else:
            not_active_count += 1

    silver_df["status"] = status_values

    # Step 8: Remove duplicates using business columns only.
    # Metadata is excluded, while last_date keeps valid monthly snapshots separate.
    rows_before_dedupe = len(silver_df)
    business_columns = [column for column in silver_df.columns if column not in METADATA_COLUMNS]
    silver_df = silver_df.drop_duplicates(subset=business_columns, keep="first")
    rows_after_dedupe = len(silver_df)
    duplicates_removed = rows_before_dedupe - rows_after_dedupe

    # Step 9: Keep metadata columns unchanged.
    # These columns are tracking metadata and should remain exactly as they were loaded from Bronze.

    # Step 10: Write the cleaned dataframe to parquet.
    # We store the date columns as actual datetime values so Power BI can recognize them as dates.
    SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    silver_df.to_parquet(SILVER_PATH, index=False)

    # Step 11: Write a readable summary to the shared Silver log file.
    rows_written = len(silver_df)

    timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = (
        "=========================================================\n"
        "TABLE : PCC_RESIDENTS\n"
        "=========================================================\n\n"
        f"Rows Read                    : {rows_read}\n"
        f"Rows Written                 : {rows_written}\n"
        f"Duplicates Removed           : {duplicates_removed}\n"
        f"Care Levels Standardized     : {care_levels_standardized}\n"
        f"Unknown Care Levels          : {len(unknown_care_levels)}\n"
        f"Active Residents            : {active_count}\n"
        f"Not Active Residents        : {not_active_count}\n"
    )

    for column_name in DATE_COLUMNS:
        if column_name not in silver_df.columns:
            continue

        summary += (
            f"{column_name} Blank Dates            : {date_summary[column_name]['Blank Dates']}\n"
            f"{column_name} Invalid Date Formats    : {date_summary[column_name]['Invalid Date Formats']}\n"
            f"{column_name} Successfully Converted : {date_summary[column_name]['Successfully Converted Dates']}\n"
        )

    summary += (
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
    transform_pcc_residents()
