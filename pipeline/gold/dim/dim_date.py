from pathlib import Path

import pandas as pd


# Create the path used to save the date dimension.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DIM_PATH = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_date.parquet"


def create_dim_date() -> None:
    # Set the fixed start and end dates for the date dimension.
    start_date = pd.Timestamp("2025-01-01")
    end_date = pd.Timestamp("2025-06-30")

    # Create one row for every calendar day between the start and end dates.
    all_dates = pd.date_range(
        start=start_date,
        end=end_date,
        freq="D"
    )
    dim_date_df = pd.DataFrame({"date": all_dates})

    # Create the numeric month and day columns from the date column.
    dim_date_df["month"] = dim_date_df["date"].dt.month
    dim_date_df["day"] = dim_date_df["date"].dt.day

    # Remove duplicate dates if any are present.
    dim_date_df = dim_date_df.drop_duplicates(subset=["date"])

    # Create the output folder if it does not already exist.
    DIM_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Save the completed date dimension as a Parquet file.
    dim_date_df.to_parquet(DIM_PATH, index=False)


def run() -> None:
    # Display pipeline progress and create the date dimension.
    print("Creating date dimension table...")
    create_dim_date()


if __name__ == "__main__":
    # Run this transformation when the file is executed directly.
    run()
