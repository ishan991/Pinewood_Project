"""Create the community dimension table from all Silver data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SILVER_DIR = PROJECT_ROOT / "data" / "silver"
DIM_PATH = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_community.parquet"


def create_dim_community() -> None:
    community_data = []

    for path in SILVER_DIR.glob("*.parquet"):
        silver_df = pd.read_parquet(path)
        if "community_id" in silver_df.columns:
            community_data.append(silver_df[["community_id"]])

    dim_community_df = pd.concat(community_data, ignore_index=True).drop_duplicates()

    dim_community_df["community_key"] = dim_community_df["community_id"].factorize()[0] + 1

    DIM_PATH.parent.mkdir(parents=True, exist_ok=True)
    dim_community_df.to_parquet(DIM_PATH, index=False)


def run() -> None:
    print("Creating community dimension table...")
    create_dim_community()


if __name__ == "__main__":
    run()
