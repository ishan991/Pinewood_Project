"""Create resident fact and dimension tables from Silver data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "pcc_residents.parquet"
FACT_PATH = PROJECT_ROOT / "data" / "gold" / "fact" / "fact_residents.parquet"
dim_residents_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_residents.parquet"
dim_community_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_community.parquet"


def create_fact_residents() -> None:
    residents_df = pd.read_parquet(SILVER_PATH)
    dim_residents_df = pd.read_parquet(dim_residents_path)
    dim_community_df = pd.read_parquet(dim_community_path)

    fact_residents_df = residents_df[
        [
            "resident_id",
            "community_id",
            "admit_date",
            "discharge_date",
            "care_level",
            "acuity_score",
            "mobility_status",
            "status",
            "last_date"
        ]
    ].copy()

    fact_residents_df = fact_residents_df.merge(
        dim_residents_df[["resident_id", "resident_key"]],
        on="resident_id",
        how="left",
    )

    fact_residents_df["discharged_resident_count"] = (
        fact_residents_df["discharge_date"].notna().astype(int)
    )

    fact_residents_df = fact_residents_df.merge(
            dim_community_df[["community_id", "community_key"]],
            on="community_id",
            how="left",
        )

    fact_residents_df = fact_residents_df[
        [
            "resident_key",
            "community_key",
            "admit_date",
            "discharge_date",
            "care_level",
            "acuity_score",
            "mobility_status",
            "status",
            "discharged_resident_count",
            "last_date"
        ]
    ]


    FACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fact_residents_df.to_parquet(FACT_PATH, index=False)


def run() -> None:
    print("Creating resident fact table...")
    create_fact_residents()


if __name__ == "__main__":
    run()
