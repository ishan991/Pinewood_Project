"""Pipeline paths and dataset naming configuration."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
BRONZE_DATA_DIR = PROJECT_ROOT / "data" / "bronze"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "pipeline.log"

# Monthly extracts are named like ``pcc_residents_2025_01.csv``.  The
# logical dataset is the portion before the month suffix.
MONTHLY_FILE_PATTERN = r"^(?P<dataset>.+)_\d{4}_\d{2}$"
