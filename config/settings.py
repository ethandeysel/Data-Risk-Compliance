from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data"

RAW_TEXT = DATA / "raw_text"

DATABASE = ROOT / "database"

SQLITE_FILE = DATABASE / "compliance.db"

ACTS = DATA / "acts"