"""Create resident fact and dimension tables from Silver data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "yardi_units.parquet"
FACT_PATH = PROJECT_ROOT / "data" / "gold" / "fact" / "fact_units.parquet"
dim_units_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_unit.parquet"
dim_community_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_community.parquet"


def create_fact_yardi_units() -> None:
    units_df = pd.read_parquet(SILVER_PATH)
    dim_units_df = pd.read_parquet(dim_units_path)
    dim_community_df = pd.read_parquet(dim_community_path)

    fact_yardi_units_df = units_df[
        [
            "unit_id",
            "community_id",
            "unit_type",
            "monthly_rent",
            "snapshot_date"
        ]
    ].copy()

    fact_yardi_units_df = fact_yardi_units_df.merge(
        dim_units_df[["unit_id", "unit_key"]],
        on="unit_id",
        how="left",
    )

    fact_yardi_units_df = fact_yardi_units_df.merge(
        dim_community_df[["community_id", "community_key"]],
        on="community_id",
        how="left",
    )

    fact_yardi_units_df = fact_yardi_units_df[
            [
                "unit_key",
                "community_key",
                "unit_type",
                "monthly_rent",
                "snapshot_date"
            ]
        ]

    FACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fact_yardi_units_df.to_parquet(FACT_PATH, index=False)


def run() -> None:
    print("Creating Yardi units fact table...")
    create_fact_yardi_units()


if __name__ == "__main__":
    run()

