"""Create the resident dimension table from Silver data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "pcc_residents.parquet"
DIM_PATH = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_residents.parquet"


def create_dim_residents() -> None:
    residents_df = pd.read_parquet(SILVER_PATH)

    dim_residents_df = residents_df[
        ["resident_id", "first_name", "last_name", "dob", "gender"]
    ].drop_duplicates(subset=["resident_id"])

    dim_residents_df["resident_key"] = dim_residents_df["resident_id"].factorize()[0] + 1

    DIM_PATH.parent.mkdir(parents=True, exist_ok=True)
    dim_residents_df.to_parquet(DIM_PATH, index=False)


def run() -> None:
    print("Creating resident dimension table...")
    create_dim_residents()


if __name__ == "__main__":
    run()
