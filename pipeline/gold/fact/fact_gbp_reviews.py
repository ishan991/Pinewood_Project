"""Create resident fact and dimension tables from Silver data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "gbp_reviews.parquet"
FACT_PATH = PROJECT_ROOT / "data" / "gold" / "fact" / "fact_gbp_reviews.parquet"
dim_community_path = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_community.parquet"


def create_fact_gbp_reviews() -> None:
    reviews_df = pd.read_parquet(SILVER_PATH)
    dim_community_df = pd.read_parquet(dim_community_path)

    fact_gbp_reviews_df = reviews_df[
        [
            "review_id",
            "community_id",
            "review_date",
            "rating",
            "review_text",
            "response_text",
            "responded_at",

        ]
    ].copy()

    fact_gbp_reviews_df = fact_gbp_reviews_df.merge(
        dim_community_df[["community_id", "community_key"]],
        on="community_id",
        how="left",
    )

    fact_gbp_reviews_df = fact_gbp_reviews_df[
            [
                "review_id",
                "community_key",
                "review_date",
                "rating",
                "review_text",
                "response_text",
                "responded_at",
    
            ]
        ]

    FACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fact_gbp_reviews_df.to_parquet(FACT_PATH, index=False)


def run() -> None:
    print("Creating GBP reviews fact table...")
    create_fact_gbp_reviews()


if __name__ == "__main__":
    run()

