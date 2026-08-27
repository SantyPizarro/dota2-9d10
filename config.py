import os
from pathlib import Path
from typing import List, Set
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Discord Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()

_raw_channel_id = os.getenv("DISCORD_CHANNEL_ID", "").strip()
DISCORD_CHANNEL_ID = int(_raw_channel_id) if _raw_channel_id.isdigit() else None

_raw_user_id = os.getenv("DISCORD_USER_ID", "").strip()
DISCORD_USER_ID = int(_raw_user_id) if _raw_user_id.isdigit() else None

# Parse allowed user IDs whitelist
_raw_allowed = os.getenv("ALLOWED_USER_IDS", "").strip()
ALLOWED_USER_IDS: Set[int] = set()

if _raw_allowed:
    for uid_str in _raw_allowed.split(","):
        uid_clean = uid_str.strip()
        if uid_clean.isdigit():
            ALLOWED_USER_IDS.add(int(uid_clean))

# If ALLOWED_USER_IDS is empty but DISCORD_USER_ID is provided, whitelist DISCORD_USER_ID
if not ALLOWED_USER_IDS and DISCORD_USER_ID:
    ALLOWED_USER_IDS.add(DISCORD_USER_ID)

# Monitoring and Detection Configuration
CHECK_INTERVAL = float(os.getenv("CHECK_INTERVAL", "2.0"))
AUTO_PAUSE_MINUTES = int(os.getenv("AUTO_PAUSE_MINUTES", "50"))
DOTA2_WINDOW_TITLE = os.getenv("DOTA2_WINDOW_TITLE", "Dota 2")
ACCEPT_TIMEOUT = float(os.getenv("ACCEPT_TIMEOUT", "40.0"))

# Path to assets
ASSETS_DIR = BASE_DIR / "src" / "assets"
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)


def validate_config() -> tuple[bool, str]:
    """Validates that necessary configuration is present."""
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "tu_token_de_discord_aqui":
        return False, "Falta configurar DISCORD_BOT_TOKEN en el archivo .env"
    if not DISCORD_CHANNEL_ID:
        return False, "Falta configurar DISCORD_CHANNEL_ID en el archivo .env"
    return True, "Configuración válida"
