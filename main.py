import asyncio
import contextlib
import logging
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from config import BOT_TOKEN, LOG_LEVEL, USE_PID_LOCK
from utils.redis_client import ensure_redis_connection, close_redis_connection
from database.models import init_db
from handlers import start, add_item, add_category, view_list, filtering, admin, categories
from handlers import setting, access_codes

from middlewares.db import DatabaseMiddleware
from middlewares.back_button import BackButtonMiddleware
from middlewares.chat_cleaner import ChatCleanerMiddleware
from utils.notifications import NotificationScheduler

# Logging setup
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

LOCK_FILE = 'bot.pid'

def acquire_lock() -> bool:
    try:
        if os.path.exists(LOCK_FILE):
            # Lock file exists — check if the process is alive
            try:
                with open(LOCK_FILE, 'r') as f:
                    pid = int(f.read().strip() or '0')
                if pid > 0:
                    # Exit if another process is running
                    try:
                        os.kill(pid, 0)
                        logger.error("Найден запущенный экземпляр (pid=%s). Выход.", pid)
                        return False
                    except OSError:
                        # Lock file is stale
                        pass
            except Exception:
                pass
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except Exception as e:
        logger.error("Не удалось создать lock-файл: %s", e)
        return True  # Do not block launch if lock file cannot be created

def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass

async def _init_storage():
    try:
        redis = await ensure_redis_connection()
        logger.info("Redis FSM storage инициализирован")
        return RedisStorage(redis=redis), True
    except Exception as exc:
        logger.warning("Redis недоступен (%s). Используем MemoryStorage.", exc)
        return MemoryStorage(), False


async def run_bot() -> None:
    """Create bot/dispatcher instances and start polling."""
    storage, uses_redis = await _init_storage()
    async with Bot(token=BOT_TOKEN) as bot:
        dp = Dispatcher(storage=storage)

        # Middleware registration
        db_middleware = DatabaseMiddleware()
        dp.message.middleware(db_middleware)
        dp.callback_query.middleware(db_middleware)
        dp.message.middleware(BackButtonMiddleware())
        dp.message.middleware(ChatCleanerMiddleware())

        # Router registration (order matters)
        dp.include_router(start.router)  # Must be first to handle /start
        dp.include_router(access_codes.router)
        dp.include_router(add_item.router)
        dp.include_router(add_category.router)
        dp.include_router(categories.router)
        dp.include_router(view_list.router)
        dp.include_router(filtering.router)
        dp.include_router(setting.router)
        dp.include_router(admin.router)  # Keep last for admin-only handlers

        # Global error handler
        @dp.errors()
        async def error_handler(event, **kwargs):
            logger.exception("Необработанная ошибка: %s", event.exception)

            try:
                from keyboards import get_main_keyboard
                if event.update.message:
                    await event.update.message.answer(
                        "❌ Произошла ошибка. Попробуйте еще раз или обратитесь к администратору.",
                        reply_markup=get_main_keyboard()
                    )
                elif event.update.callback_query:
                    await event.update.callback_query.message.answer(
                        "❌ Произошла ошибка. Попробуйте еще раз.",
                        reply_markup=get_main_keyboard()
                    )
                    await event.update.callback_query.answer()
            except Exception as e:
                logger.error(f"Ошибка при обработке ошибки: {e}")

            return True

        # Start notification scheduler and keep the task for graceful shutdown
        notification_scheduler = NotificationScheduler(bot)
        scheduler_task = asyncio.create_task(notification_scheduler.start())

        logger.info("Бот запущен и готов к работе")
        try:
            await dp.start_polling(bot)
        finally:
            # Stop scheduler and wait for the task to finish
            await notification_scheduler.stop()
            scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await scheduler_task
            await storage.close()
            if uses_redis:
                await close_redis_connection()


async def main():
    # Guard against running multiple instances when requested
    lock_acquired = False
    if USE_PID_LOCK:
        lock_acquired = acquire_lock()
        if not lock_acquired:
            sys.exit(1)

    try:
        # Initialize database
        logger.info("Инициализация базы данных...")
        await init_db()

        retry_delay = 5
        while True:
            try:
                await run_bot()
                break  # Exit once polling finishes gracefully
            except TelegramNetworkError as e:
                logger.error(
                    "Проблема с подключением к Telegram (%s). Перезапуск через %s секунд...",
                    e,
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
            except Exception as e:
                logger.exception(f"Критическая ошибка при запуске бота: {e}")
                break
    finally:
        if USE_PID_LOCK and lock_acquired:
            release_lock()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")
