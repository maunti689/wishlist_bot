import asyncio
import contextlib
import logging
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database.models import init_db
from handlers import start, add_item, add_category, view_list, filtering, admin, categories
from handlers import setting, access_codes
# from handlers import errors  # Создать если нужен отдельный файл с обработчиками ошибок

from middlewares.db import DatabaseMiddleware
from middlewares.back_button import BackButtonMiddleware
from middlewares.chat_cleaner import ChatCleanerMiddleware
# from middlewares.antispam import AntiSpamMiddleware  # Создать если нужно
from utils.notifications import NotificationScheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

LOCK_FILE = 'bot.pid'

def acquire_lock() -> bool:
    try:
        if os.path.exists(LOCK_FILE):
            # Файл существует — проверим, жив ли процесс
            try:
                with open(LOCK_FILE, 'r') as f:
                    pid = int(f.read().strip() or '0')
                if pid > 0:
                    # Если процесс жив, выходим
                    try:
                        os.kill(pid, 0)
                        logger.error("Найден запущенный экземпляр (pid=%s). Выход.", pid)
                        return False
                    except OSError:
                        # Пид-файл устарел
                        pass
            except Exception:
                pass
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except Exception as e:
        logger.error("Не удалось создать lock-файл: %s", e)
        return True  # Не блокируем запуск, если что-то пошло не так

def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass

async def run_bot() -> None:
    """Создает экземпляры бота/диспетчера и запускает polling."""
    async with Bot(token=BOT_TOKEN) as bot:
        dp = Dispatcher(storage=MemoryStorage())

        # Подключение middleware
        db_middleware = DatabaseMiddleware()
        dp.message.middleware(db_middleware)
        dp.callback_query.middleware(db_middleware)
        dp.message.middleware(BackButtonMiddleware())
        dp.message.middleware(ChatCleanerMiddleware())

        # Регистрация роутеров (порядок важен!)
        dp.include_router(start.router)  # Должен быть первым для обработки /start
        dp.include_router(access_codes.router)
        dp.include_router(add_item.router)
        dp.include_router(add_category.router)
        dp.include_router(categories.router)
        dp.include_router(view_list.router)
        dp.include_router(filtering.router)
        dp.include_router(setting.router)
        dp.include_router(admin.router)  # Должен быть последним

        # Глобальный обработчик ошибок
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

        # Запуск планировщика уведомлений и сохранение таска, чтобы его корректно остановить
        notification_scheduler = NotificationScheduler(bot)
        scheduler_task = asyncio.create_task(notification_scheduler.start())

        logger.info("Бот запущен и готов к работе")
        try:
            await dp.start_polling(bot)
        finally:
            # Останавливаем планировщик и дожидаемся завершения таска
            await notification_scheduler.stop()
            scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await scheduler_task


async def main():
    # Guard от второго экземпляра
    if not acquire_lock():
        sys.exit(1)

    try:
        # Инициализация базы данных
        logger.info("Инициализация базы данных...")
        await init_db()

        retry_delay = 5
        while True:
            try:
                await run_bot()
                break  # Корректное завершение polling — выходим
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
        release_lock()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")
