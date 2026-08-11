"""Create resident fact and dimension tables from Silver data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "adp_shifts.parquet"
FACT_PATH = PROJECT_ROOT / "data" / "gold" / "fact" / "fact_adp_shifts.parquet"
dim_employee_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_employee.parquet"
dim_community_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_community.parquet"


def create_fact_adp_shifts() -> None:
    shifts_df = pd.read_parquet(SILVER_PATH)
    dim_employee_df = pd.read_parquet(dim_employee_path)
    dim_community_df = pd.read_parquet(dim_community_path)

    fact_adp_shifts_df = shifts_df[
        [
            "shift_id",
            "employee_id",
            "community_id",
            "role",
            "shift_date",
            "hours_worked",
            "Standard_Hourly_Rate",
            "Total_Labor_Cost"
        ]
    ].copy()

    fact_adp_shifts_df = fact_adp_shifts_df.merge(
        dim_employee_df[["employee_id", "employee_key"]],
        on="employee_id",
        how="left",
    )

    fact_adp_shifts_df = fact_adp_shifts_df.merge(
        dim_community_df[["community_id", "community_key"]],
        on="community_id",
        how="left",
    )

    fact_adp_shifts_df = fact_adp_shifts_df[
            [
                "shift_id",
                "employee_key",
                "community_key",
                "shift_date",
                "hours_worked",
                "Standard_Hourly_Rate",
                "Total_Labor_Cost"
            ]
        ]

    FACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fact_adp_shifts_df.to_parquet(FACT_PATH, index=False)


def run() -> None:
    print("Creating ADP shifts fact table...")
    create_fact_adp_shifts()


if __name__ == "__main__":
    run()

