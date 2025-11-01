from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from keyboards import get_main_keyboard
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message, session: AsyncSession, user, state: FSMContext):
    """Главное меню настроек"""
    await state.clear()
    
    try:
        # Используем правильный метод CRUD
        current_user = await UserCRUD.get_user_by_telegram_id(session, message.from_user.id)
        
        if not current_user:
            # Создаем пользователя, если его нет
            current_user = await UserCRUD.get_or_create_user(
                session, 
                message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )

        notifications_text = "🔔 Включены" if current_user.notifications_enabled else "🔕 Отключены"

        kb = InlineKeyboardBuilder()
        kb.button(text=f"Уведомления: {notifications_text}", callback_data="toggle_notifications")
        kb.adjust(1)

        full_name = " ".join(filter(None, [current_user.first_name, current_user.last_name])) or "Без имени"
        
        await message.answer(
            "⚙️ **Настройки**\n\n"
            f"👤 Пользователь: {full_name}\n"
            f"🔔 Уведомления: {notifications_text}\n"
            f"📅 Дата регистрации: {current_user.created_at.strftime('%d.%m.%Y')}\n\n"
            "Выберите действие:",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в settings_menu: {e}")
        await message.answer(
            "❌ Произошла ошибка при загрузке настроек. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )

@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery, session: AsyncSession, user):
    """Переключение уведомлений"""
    try:
        current_user = await UserCRUD.get_user_by_telegram_id(session, callback.from_user.id)
        
        if not current_user:
            await callback.answer("❌ Пользователь не найден")
            return

        new_state = not current_user.notifications_enabled
        
        # Используем правильный метод CRUD
        await UserCRUD.update_user_notifications(session, current_user.id, new_state)
        
        status_text = "включены" if new_state else "отключены"
        await callback.answer(f"✅ Уведомления {status_text}")

        # Обновляем интерфейс
        notifications_text = "🔔 Включены" if new_state else "🔕 Отключены"

        kb = InlineKeyboardBuilder()
        kb.button(text=f"Уведомления: {notifications_text}", callback_data="toggle_notifications")
        kb.adjust(1)

        full_name = " ".join(filter(None, [current_user.first_name, current_user.last_name])) or "Без имени"

        await callback.message.edit_text(
            "⚙️ **Настройки**\n\n"
            f"👤 Пользователь: {full_name}\n"
            f"🔔 Уведомления: {notifications_text}\n"
            f"📅 Дата регистрации: {current_user.created_at.strftime('%d.%m.%Y')}\n\n"
            "Выберите действие:",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в toggle_notifications: {e}")
        await callback.answer("❌ Ошибка изменения настроек")