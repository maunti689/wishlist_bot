from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from database.models import AsyncSessionLocal
from database.crud import UserCRUD


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для подключения сессии БД и загрузки пользователя"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # создаём асинхронную сессию через контекстный менеджер
        async with AsyncSessionLocal() as session:
            try:
                # добавляем сессию в data
                data["session"] = session

                # если событие пришло от пользователя
                if hasattr(event, 'from_user') and event.from_user:
                    user = await UserCRUD.get_or_create_user(
                        session=session,
                        telegram_id=event.from_user.id,
                        username=event.from_user.username,
                        first_name=event.from_user.first_name,
                        last_name=event.from_user.last_name
                    )
                    data["user"] = user

                # передаём управление следующему обработчику
                return await handler(event, data)

            except Exception as e:
                # в случае ошибки — откатываем изменения
                await session.rollback()
                raise e
