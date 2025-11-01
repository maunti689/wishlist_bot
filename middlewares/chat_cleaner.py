from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Dict, Any, Awaitable, Callable, Union
import asyncio

class ChatCleanerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        # Обрабатываем событие
        result = await handler(event, data)
        
        # Если это текстовое сообщение пользователя
        if isinstance(event, Message) and event.text and not event.text.startswith('/'):
            try:
                # Удаляем сообщение пользователя через 3 секунды
                await asyncio.sleep(3)
                await event.delete()
            except Exception:
                pass  # Игнорируем ошибки удаления
        
        return result
