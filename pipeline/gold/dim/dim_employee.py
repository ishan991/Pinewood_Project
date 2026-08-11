"""Create the resident dimension table from Silver data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "adp_shifts.parquet"
DIM_PATH = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_employee.parquet"


def create_dim_employee() -> None:
    employee_df = pd.read_parquet(SILVER_PATH)

    dim_employee_df = employee_df[
        ["employee_id", "role"]
    ].drop_duplicates(subset=["employee_id"])

    dim_employee_df["employee_key"] = dim_employee_df["employee_id"].factorize()[0] + 1

    DIM_PATH.parent.mkdir(parents=True, exist_ok=True)
    dim_employee_df.to_parquet(DIM_PATH, index=False)


def run() -> None:
    print("Creating employee dimension table...")
    create_dim_employee()


if __name__ == "__main__":
    run()
