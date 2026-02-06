from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from typing import Dict, Any, Awaitable, Callable
import logging
from keyboards import get_main_keyboard
from utils.cleanup import cleanup_ephemeral_messages
from utils.localization import translate_text, get_user_language, get_value_variants

logger = logging.getLogger(__name__)

class BackButtonMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message) and event.text in get_value_variants("buttons.back"):
            state: FSMContext = data["state"]
            current_state = await state.get_state()
            
            logger.info(f"'Back' button pressed in state: {current_state}")
            
            try:
                await cleanup_ephemeral_messages(event.bot, state, event.chat.id)
            except Exception:
                pass
            await state.clear()
            
            user = data.get("user")
            language = get_user_language(user)

            await event.answer(
                translate_text(language, "🏠 Main menu", "🏠 Главное меню"),
                reply_markup=get_main_keyboard(language=language)
            )
            return
        
        return await handler(event, data)
