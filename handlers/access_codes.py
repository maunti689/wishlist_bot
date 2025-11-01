from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from keyboards import get_main_keyboard, get_back_keyboard
from states import ManageCategoryStates
from database.crud import CategoryCRUD
from utils.cleanup import add_ephemeral_message, cleanup_ephemeral_messages, schedule_delete_message

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "🔑 Ввести код")
async def enter_code_start(message: Message, state: FSMContext):
    """Начало ввода кода доступа"""
    logger.info(f"Пользователь {message.from_user.id} нажал 'Ввести код'")
    
    msg = await message.answer(
        "🔑 Введите 6-значный код доступа к категории:\n\n"
        "Код должен выглядеть примерно так: `123456`",
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(ManageCategoryStates.enter_access_code)
    await add_ephemeral_message(state, msg.message_id)

@router.message(ManageCategoryStates.enter_access_code)
async def process_access_code(message: Message, session: AsyncSession, user, state: FSMContext):
    """Обработка кода доступа"""
    logger.info(f"Обработка кода доступа: {message.text}")
    
    # Обработка кнопки "Назад"
    if message.text == "◀️ Назад":
        await state.clear()
        await message.answer(
            "🏠 Главное меню",
            reply_markup=get_main_keyboard()
        )
        return
    
    if not message.text:
        msg = await message.answer(
            "❌ Код не может быть пустым. Попробуйте еще раз:",
            reply_markup=get_back_keyboard()
        )
        await add_ephemeral_message(state, msg.message_id)
        return
    
    code = message.text.strip()
    
    if len(code) != 6 or not code.isdigit():
        await message.answer(
            "❌ Код должен состоять из 6 цифр. Попробуйте еще раз:",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Извлекаем ID категории из кода
    try:
        category_id = int(code[:3])
    except ValueError:
        msg = await message.answer(
            "❌ Некорректный код. Попробуйте еще раз:",
            reply_markup=get_back_keyboard()
        )
        await add_ephemeral_message(state, msg.message_id)
        return
    
    # Получаем категорию
    try:
        category = await CategoryCRUD.get_category_by_id(session, category_id)
    except Exception as e:
        logger.error(f"Ошибка получения категории: {e}")
        msg = await message.answer(
            "❌ Произошла ошибка при поиске категории. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
        return
    
    if not category:
        msg = await message.answer(
            "❌ Категория с таким кодом не найдена.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
        return
    
    if category.sharing_type == "private":
        msg = await message.answer(
            "❌ Эта категория является личной и недоступна для доступа.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
        return
    
    if category.owner_id == user.id:
        msg = await message.answer(
            f"ℹ️ Это ваша собственная категория '{category.name}'.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
        return
    
    # Проверяем, не добавлен ли уже пользователь
    try:
        existing_access = await CategoryCRUD.check_user_access(session, category.id, user.id)
    except Exception as e:
        logger.error(f"Ошибка проверки доступа: {e}")
        await message.answer(
            "❌ Произошла ошибка при проверке доступа.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    if existing_access:
        # Очистка временных сообщений
        await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
        await state.clear()
        msg = await message.answer(
            f"ℹ️ У вас уже есть доступ к категории '{category.name}'.",
            reply_markup=get_main_keyboard()
        )
        schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
        return
    
    # Добавляем доступ
    try:
        can_edit = category.sharing_type == "collaborative"
        await CategoryCRUD.add_user_access(session, category.id, user.id, can_edit)
        
        access_type = "редактирования" if can_edit else "просмотра"
        
        # Очистка временных сообщений
        await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
        await state.clear()
        msg = await message.answer(
            f"✅ Вы получили доступ для {access_type} к категории:\n"
            f"📁 **{category.name}**\n\n"
            f"Теперь вы можете {'добавлять и редактировать элементы' if can_edit else 'просматривать элементы'} в этой категории.",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
        schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
        
    except Exception as e:
        logger.error(f"Ошибка добавления доступа: {e}")
        msg = await message.answer(
            "❌ Произошла ошибка при добавлении доступа. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
