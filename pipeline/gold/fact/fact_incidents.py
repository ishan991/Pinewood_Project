"""Create resident fact and dimension tables from Silver data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "pcc_incidents.parquet"
FACT_PATH = PROJECT_ROOT / "data" / "gold" / "fact" / "fact_incidents.parquet"
dim_community_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_community.parquet"
dim_residents_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_residents.parquet"


def create_fact_incidents() -> None:
    incidents_df = pd.read_parquet(SILVER_PATH)
    dim_community_df = pd.read_parquet(dim_community_path)
    dim_residents_df = pd.read_parquet(dim_residents_path)

    fact_incidents_df = incidents_df[
        [
            "incident_id",
            "resident_id",
            "community_id",
            "incident_date",
            "incident_type",
            "severity",
            "reported_by"
        ]
    ].copy()

    fact_incidents_df = fact_incidents_df.merge(
        dim_community_df[["community_id", "community_key"]],
        on="community_id",
        how="left",
    )

    fact_incidents_df = fact_incidents_df.merge(
                dim_residents_df[["resident_id", "resident_key"]],
                on="resident_id",
                how="left",
            )

    fact_incidents_df = fact_incidents_df[
        [
            "incident_id",
            "resident_key",
            "community_key",
            "incident_date",
            "incident_type",
            "severity",
            "reported_by"
        ]
    ]

    FACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fact_incidents_df.to_parquet(FACT_PATH, index=False)


def run() -> None:
    print("Creating Incidents fact table...")
    create_fact_incidents()


if __name__ == "__main__":
    run()

