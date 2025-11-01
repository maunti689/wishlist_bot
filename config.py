import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# База данных
DATABASE_URL = "sqlite+aiosqlite:///./wishlist.db"

# Настройки уведомлений
NOTIFICATION_DAYS_BEFORE = [7, 1]  # За сколько дней до даты присылать напоминания

# Часовой пояс
TIMEZONE = "Europe/Moscow"

# Лимиты
MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_ITEMS_PER_USER = 1000
MAX_CATEGORIES_PER_USER = 50

# Форматы
DATE_FORMAT = "%d.%m.%Y"
DATETIME_FORMAT = "%d.%m.%Y %H:%M"