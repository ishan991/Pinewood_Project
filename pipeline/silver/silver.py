"""Run every Silver-layer transformation."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.silver.silver_adp_shifts import transform_adp_shifts
from pipeline.silver.silver_care_history import transform_pcc_care_history
from pipeline.silver.silver_gbp_reviews import transform_gbp_reviews
from pipeline.silver.silver_hubspot_leads import transform_hubspot_leads
from pipeline.silver.silver_incidents import transform_pcc_incidents
from pipeline.silver.silver_residents import transform_pcc_residents
from pipeline.silver.silver_yardi_leases import transform_yardi_leases
from pipeline.silver.silver_yardi_units import transform_yardi_units


TRANSFORMATIONS = (
    ("ADP shifts", transform_adp_shifts),
    ("PCC care history", transform_pcc_care_history),
    ("GBP reviews", transform_gbp_reviews),
    ("HubSpot leads", transform_hubspot_leads),
    ("PCC incidents", transform_pcc_incidents),
    ("PCC residents", transform_pcc_residents),
    ("Yardi leases", transform_yardi_leases),
    ("Yardi units", transform_yardi_units),
)


def run() -> None:
    """Run all Silver transformations in a consistent order."""
    for name, transform in TRANSFORMATIONS:
        print(f"Running Silver transformation: {name}...")
        transform()


if __name__ == "__main__":
    run()
