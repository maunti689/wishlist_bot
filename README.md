# Wishlist Bot

A Telegram bot for managing personal and shared wishlists: categories, filters, reminders, and flexible access control.

## Features
- Create personal and shared categories with access codes (view/edit permissions)
- Add and edit wishlist items (price, dates, tags, links, photos, location)
- Filtering by tags, categories, price ranges, item types, and dates
- Reminders for upcoming dates and activity tracking for shared lists
- Multilingual UI (RU/EN) with translated buttons and menus

> **Note:** Certain data in screenshots and code samples is redacted per client agreement.

## Screenshots
- **Main Menu & Category List** – shows multilingual UI, quick actions, and shared categories.
- **Add Item Flow** – demonstrates tagging, pricing, and location steps with inline keyboards.
- **Filters & Results** – illustrates date/price filters and paginated outputs.

*(Add your image links or embedded files here, e.g. `![Main menu](docs/screenshots/main-menu.png)`.)*

## Quick Start
1. Install **Python 3.11+** and create a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and set your bot token and settings.
4. Initialize the database (created automatically on the first run).
5. Run the bot:
   ```bash
   python main.py
   ```

## Environment Variables

| Variable | Default | Description |
|--------|---------|-------------|
| `BOT_TOKEN` | — | **Required.** Telegram bot token from BotFather. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./wishlist.db` | Database connection string (SQLite by default). |
| `TIMEZONE` | `Europe/Moscow` | Time zone used for date formatting and reminders. |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, ...). |
| `USE_PID_LOCK` | `0` | Enable `bot.pid` lock file (`1` / `true`). |
| `REDIS_URL` | `redis://localhost:6379/0` | *(Optional)* Redis URL for persistent FSM storage or rate-limiting. Requires Redis setup and the `redis` Python package if enabled. |
| `ACCESS_CODE_LENGTH` | `10` | Length of generated access codes for shared categories. |
| `ACCESS_CODE_MAX_ATTEMPTS` | `5` | Maximum invalid attempts before temporary blocking. |
| `ACCESS_CODE_BLOCK_SECONDS` | `900` | Block duration in seconds. |

## Database Notes
SQLite is used by default to keep the setup simple, dependency-free, and easy to run locally.  
The database layer is abstracted via SQLAlchemy, so switching to another SQL backend (e.g. PostgreSQL) only requires overriding the `DATABASE_URL` environment variable.

This approach allows the project to stay lightweight for personal use while remaining portable to more production-oriented databases if needed.

## Running Tests
```bash
pytest
```

## Migrations
Schema changes can be applied using SQL files from the `migrations/` directory.

Example (SQLite):
```bash
sqlite3 wishlist.db < migrations/001_add_unique_shared_categories.sql
```

For other SQL engines, adapt the command accordingly (DDL is mostly compatible).

## Notes
- Runtime files (`.env`, `bot.log`, `wishlist.db`) should not be committed to Git.
- Logs are written to stdout, which works well with system loggers and hosting platforms.
- For deployment, you can override `DATABASE_URL` (e.g. PostgreSQL) and disable `USE_PID_LOCK` in ephemeral or no-disk environments.
