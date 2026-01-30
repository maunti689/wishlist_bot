from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from keyboards import get_main_keyboard
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from utils.localization import (
    translate as _,
    translate_text,
    get_user_language,
    SUPPORTED_LANGUAGES,
    get_value_variants,
)

router = Router()
logger = logging.getLogger(__name__)


def build_settings_view(current_user, language: str):
    """Compose settings text and inline keyboard for a user."""
    full_name = " ".join(filter(None, [current_user.first_name, current_user.last_name]))
    if not full_name:
        full_name = translate_text(language, "No name", "Без имени")

    notifications_status = translate_text(language, "Enabled", "Включены") if current_user.notifications_enabled else translate_text(language, "Disabled", "Отключены")
    notifications_icon = "🔔" if current_user.notifications_enabled else "🔕"
    notifications_text = f"{notifications_icon} {notifications_status}"

    language_name = SUPPORTED_LANGUAGES.get(language, language.upper())

    kb = InlineKeyboardBuilder()
    kb.button(
        text=translate_text(language, "Notifications: {status}", "Уведомления: {status}").format(status=notifications_text),
        callback_data="toggle_notifications"
    )
    kb.button(
        text=translate_text(language, "Language: {language}", "Язык: {language}").format(language=language_name),
        callback_data="change_language"
    )
    kb.adjust(1)

    text = translate_text(
        language,
        "⚙️ **Settings**\n\n"
        "👤 User: {full_name}\n"
        "🔔 Notifications: {notifications}\n"
        "🌐 Language: {language_name}\n"
        "📅 Registration date: {reg_date}\n\n"
        "Choose an action:",
        "⚙️ **Настройки**\n\n"
        "👤 Пользователь: {full_name}\n"
        "🔔 Уведомления: {notifications}\n"
        "🌐 Язык: {language_name}\n"
        "📅 Дата регистрации: {reg_date}\n\n"
        "Выберите действие:"
    ).format(
        full_name=full_name,
        notifications=notifications_text,
        language_name=language_name,
        reg_date=current_user.created_at.strftime('%d.%m.%Y')
    )

    return text, kb.as_markup()


@router.message(F.text.in_(get_value_variants("buttons.settings")))
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

        language = get_user_language(current_user)
        text, markup = build_settings_view(current_user, language)
        
        await message.answer(
            text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в settings_menu: {e}")
        await message.answer(
            translate_text(
                get_user_language(user),
                "❌ Failed to load settings. Please try again later.",
                "❌ Произошла ошибка при загрузке настроек. Попробуйте позже."
            ),
            reply_markup=get_main_keyboard(language=get_user_language(user))
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
        
        language = get_user_language(current_user)
        status_text = translate_text(language, "enabled", "включены") if new_state else translate_text(language, "disabled", "отключены")
        await callback.answer(
            translate_text(language, "✅ Notifications {status}", "✅ Уведомления {status}").format(status=status_text)
        )

        text, markup = build_settings_view(current_user, language)
        await callback.message.edit_text(
            text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в toggle_notifications: {e}")
        await callback.answer(
            translate_text(get_user_language(user), "❌ Failed to update settings", "❌ Ошибка изменения настроек")
        )


@router.callback_query(F.data == "change_language")
async def change_language(callback: CallbackQuery, user):
    language = get_user_language(user)
    kb = InlineKeyboardBuilder()
    for code, name in SUPPORTED_LANGUAGES.items():
        prefix = "✅ " if code == language else ""
        kb.button(text=f"{prefix}{name}", callback_data=f"set_language_{code}")
    kb.button(text=_("buttons.back", language=language), callback_data="back_to_settings")
    kb.adjust(1)

    await callback.message.edit_text(
        translate_text(language, "🌐 Choose interface language:", "🌐 Выберите язык интерфейса:"),
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery, session: AsyncSession, user):
    current_user = await UserCRUD.get_user_by_telegram_id(session, callback.from_user.id)
    language = get_user_language(current_user)
    text, markup = build_settings_view(current_user, language)
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")


@router.callback_query(F.data.startswith("set_language_"))
async def set_language(callback: CallbackQuery, session: AsyncSession, user):
    new_language = callback.data.split("set_language_")[1]
    if new_language not in SUPPORTED_LANGUAGES:
        await callback.answer("❌")
        return

    await UserCRUD.update_user_language(session, user.id, new_language)
    user.language = new_language
    updated_user = await UserCRUD.get_user_by_telegram_id(session, callback.from_user.id)

    language = get_user_language(updated_user)
    await callback.answer(
        translate_text(language, "✅ Language updated", "✅ Язык обновлен")
    )

    text, markup = build_settings_view(updated_user, language)
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
