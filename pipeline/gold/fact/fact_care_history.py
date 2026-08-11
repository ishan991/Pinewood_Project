"""Create resident fact and dimension tables from Silver data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "pcc_care_history.parquet"
FACT_PATH = PROJECT_ROOT / "data" / "gold" / "fact" / "fact_care_history.parquet"
dim_residents_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_residents.parquet"


def create_fact_care_history() -> None:
    care_history_df = pd.read_parquet(SILVER_PATH)
    dim_residents_df = pd.read_parquet(dim_residents_path)

    fact_care_history_df = care_history_df[
        [
            "resident_id",
            "change_date",
            "previous_level",
            "new_level",
            "reason"
        ]
    ].copy()

    fact_care_history_df = fact_care_history_df.merge(
        dim_residents_df[["resident_id", "resident_key"]],
        on="resident_id",
        how="left",
    )

    fact_care_history_df = fact_care_history_df[
        [
            "resident_key",
            "change_date",
            "previous_level",
            "new_level",
            "reason"
        ]
    ]

    FACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fact_care_history_df.to_parquet(FACT_PATH, index=False)


def run() -> None:
    print("Creating Care History fact table...")
    create_fact_care_history()


if __name__ == "__main__":
    run()
