from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from keyboards import get_main_keyboard

router = Router()
logger = logging.getLogger(__name__)

@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession, user, state: FSMContext):
    """Обработчик команды /start"""
    # Очищаем состояние
    await state.clear()
    
    welcome_text = (
        f"👋 Добро пожаловать в бот **Wishlist**, {user.first_name or 'друг'}!\n\n"
        "Выберите действие из меню ниже:"
    )
    
    await message.answer(
        text=welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

@router.message(F.text == "◀️ Назад")
async def back_to_main(message: Message, state: FSMContext):
    """Возврат в главное меню"""
    current_state = await state.get_state()
    logger.info(f"Нажата кнопка 'Назад' в состоянии: {current_state}")
    
    await state.clear()
    
    await message.answer(
        "🏠 Главное меню",
        reply_markup=get_main_keyboard()
    )