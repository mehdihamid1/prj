from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = ROOT / "data" / "policies"
DATA_DIR = ROOT / "data"
INDEX_PATH = DATA_DIR / "index.json"
TOP_K = 4
