from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from typing import Dict, Any, Awaitable, Callable
import logging
from keyboards import get_main_keyboard
from utils.cleanup import cleanup_ephemeral_messages

logger = logging.getLogger(__name__)

class BackButtonMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message) and event.text == "◀️ Назад":
            state: FSMContext = data["state"]
            current_state = await state.get_state()
            
            logger.info(f"Нажата кнопка 'Назад' в состоянии: {current_state}")
            
            # Удаляем временные сообщения, затем очищаем состояние
            try:
                await cleanup_ephemeral_messages(event.bot, state, event.chat.id)
            except Exception:
                pass
            await state.clear()
            
            # Возвращаемся в главное меню
            await event.answer(
                "🏠 Главное меню",
                reply_markup=get_main_keyboard()
            )
            return
        
        return await handler(event, data)
