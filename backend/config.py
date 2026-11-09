from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("OFFTEC_HUB_DATA", ROOT / "backend" / "data")).expanduser()
LOG_DIR = ROOT / "backend" / "logs"
UPLOAD_DIR = DATA_DIR / "uploads"
TRANSLATION_DIR = DATA_DIR / "translation_sessions"
DB_PATH = DATA_DIR / "hub.sqlite3"
TOKEN_PATH = DATA_DIR / "session.token"
AI_CONFIG_PATH = DATA_DIR / "ai-provider.json"
FRONTEND_DIR = ROOT / "frontend"
READROID_PATH = Path(os.environ.get("OFFTEC_READROID_PATH", Path.home() / "ReaDroid")).expanduser()
PORTAI_PATH = Path(os.environ.get("OFFTEC_PORTAI_PATH", Path.home() / "OffTec-PortAI")).expanduser()
MAX_UPLOAD_BYTES = 250 * 1024 * 1024

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
TRANSLATION_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
