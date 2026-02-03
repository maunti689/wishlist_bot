import os
from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    """Read boolean values from environment variables."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./wishlist.db")

# Notification settings
NOTIFICATION_DAYS_BEFORE = [7, 1]  # Days before date when reminders are sent

# Time zone
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

# Logging level and optional settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
USE_PID_LOCK = _get_bool("USE_PID_LOCK", default=False)

# Access code / sharing settings
ACCESS_CODE_LENGTH = int(os.getenv("ACCESS_CODE_LENGTH", "10"))
ACCESS_CODE_MAX_ATTEMPTS = int(os.getenv("ACCESS_CODE_MAX_ATTEMPTS", "5"))
ACCESS_CODE_BLOCK_SECONDS = int(os.getenv("ACCESS_CODE_BLOCK_SECONDS", "900"))

# Limits
MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_ITEMS_PER_USER = 1000
MAX_CATEGORIES_PER_USER = 50

# Date/time formats
DATE_FORMAT = "%d.%m.%Y"
DATETIME_FORMAT = "%d.%m.%Y %H:%M"
