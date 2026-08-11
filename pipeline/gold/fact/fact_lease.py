"""Create resident fact and dimension tables from Silver data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "yardi_leases.parquet"
FACT_PATH = PROJECT_ROOT / "data" / "gold" / "fact" / "fact_leases.parquet"
dim_residents_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_residents.parquet"
dim_community_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_community.parquet"
dim_unit_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_unit.parquet"


def create_fact_leases() -> None:
    leases_df = pd.read_parquet(SILVER_PATH)
    dim_residents_df = pd.read_parquet(dim_residents_path)
    dim_community_df = pd.read_parquet(dim_community_path)
    dim_unit_df = pd.read_parquet(dim_unit_path)

    fact_leases_df = leases_df[
        [
            "lease_id",
            "resident_id",
            "unit_id",
            "community_id",
            "move_in_date",
            "move_out_date",
            "move_out_reason",
            "monthly_rate"
        ]
    ].copy()

    fact_leases_df = fact_leases_df.merge(
        dim_residents_df[["resident_id", "resident_key"]],
        on="resident_id",
        how="left",
    )

    fact_leases_df = fact_leases_df.merge(
        dim_community_df[["community_id", "community_key"]],
        on="community_id",
        how="left",
    )

    fact_leases_df = fact_leases_df.merge(
            dim_unit_df[["unit_id", "unit_key"]],
            on="unit_id",
            how="left",
        )

    fact_leases_df = fact_leases_df[
            [
                "lease_id",
                "resident_key",
                "unit_key",
                "community_key",
                "move_in_date",
                "move_out_date",
                "move_out_reason",
                "monthly_rate"
            ]
        ]

    FACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fact_leases_df.to_parquet(FACT_PATH, index=False)


def run() -> None:
    print("Creating leases fact table...")
    create_fact_leases()


if __name__ == "__main__":
    run()

