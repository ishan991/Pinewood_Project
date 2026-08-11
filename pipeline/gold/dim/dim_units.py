"""Create the resident dimension table from Silver data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SILVER_PATH = PROJECT_ROOT / "data" / "silver" / "yardi_units.parquet"
DIM_PATH = PROJECT_ROOT / "data" / "gold" / "dim" / "dim_unit.parquet"


def create_dim_units() -> None:
    units_df = pd.read_parquet(SILVER_PATH)

    dim_units_df = units_df[
        ["unit_id", "unit_type"]
    ].drop_duplicates(subset=["unit_id"])

    dim_units_df["unit_key"] = dim_units_df["unit_id"].factorize()[0] + 1

    DIM_PATH.parent.mkdir(parents=True, exist_ok=True)
    dim_units_df.to_parquet(DIM_PATH, index=False)


def run() -> None:
    print("Creating unit dimension table...")
    create_dim_units()


if __name__ == "__main__":
    run()
