from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from keyboards import get_main_keyboard
from utils.localization import translate_text, get_user_language, get_value_variants

router = Router()
logger = logging.getLogger(__name__)

@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession, user, state: FSMContext):
    """Обработчик команды /start"""
    # Очищаем состояние
    await state.clear()

    language = get_user_language(user)
    fallback_name = translate_text(language, "friend", "друг")
    name = user.first_name or fallback_name
    
    welcome_text = translate_text(
        language,
        f"👋 Welcome to **Wishlist**, {name}!\n\nChoose an action below:",
        f"👋 Добро пожаловать в бот **Wishlist**, {name}!\n\nВыберите действие из меню ниже:"
    )
    
    await message.answer(
        text=welcome_text,
        reply_markup=get_main_keyboard(language=language),
        parse_mode="Markdown"
    )

@router.message(F.text.in_(get_value_variants("buttons.back")))
async def back_to_main(message: Message, user, state: FSMContext):
    """Возврат в главное меню"""
    current_state = await state.get_state()
    logger.info(f"Нажата кнопка 'Назад' в состоянии: {current_state}")
    
    await state.clear()
    language = get_user_language(user)

    await message.answer(
        translate_text(language, "🏠 Main menu", "🏠 Главное меню"),
        reply_markup=get_main_keyboard(language=language)
    )
