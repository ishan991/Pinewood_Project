"""Create resident fact and dimension tables from Silver data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "hubspot_leads.parquet"
FACT_PATH = PROJECT_ROOT / "data" / "gold" / "fact" / "fact_hubspot_leads.parquet"
dim_community_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_community.parquet"


def create_fact_hubspot_leads() -> None:
    leads_df = pd.read_parquet(SILVER_PATH)
    dim_community_df = pd.read_parquet(dim_community_path)

    fact_hubspot_leads_df = leads_df[
        [
            "lead_id",
            "community_id",
            "lead_source",
            "created_date",
            "tour_date",
            "deposit_date",
            "move_in_date",
            "status",
            "lost_reason"

        ]
    ].copy()

    fact_hubspot_leads_df = fact_hubspot_leads_df.merge(
        dim_community_df[["community_id", "community_key"]],
        on="community_id",
        how="left",
    )

    fact_hubspot_leads_df = fact_hubspot_leads_df[
        [
            "lead_id",
            "community_key",
            "lead_source",
            "created_date",
            "tour_date",
            "deposit_date",
            "move_in_date",
            "status",
            "lost_reason"

        ]
    ]

    FACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fact_hubspot_leads_df.to_parquet(FACT_PATH, index=False)


def run() -> None:
    print("Creating HubSpot leads fact table...")
    create_fact_hubspot_leads()


if __name__ == "__main__":
    run()

