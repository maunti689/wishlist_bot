from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import hashlib
import random
import string
import logging

from database.crud import CategoryCRUD, ItemCRUD, UserCRUD
from database.models import SharedCategory
from states import ManageCategoryStates
from keyboards import (
    get_main_keyboard, get_back_keyboard, get_categories_list_keyboard,
    get_category_management_keyboard, get_category_sharing_keyboard,
    get_sharing_type_keyboard, get_confirmation_keyboard
)
from utils.helpers import format_item_card
from utils.cleanup import schedule_delete_message
from utils.notifications import send_category_shared_notification, send_category_access_revoked_notification
from utils.localization import translate as _, translate_text, get_user_language, get_value_variants

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text.in_(get_value_variants("buttons.manage_categories")))
async def manage_categories_menu(message: Message, session: AsyncSession, user, state: FSMContext):
    """Главное меню управления категориями"""
    await state.clear()
    
    try:
        language = get_user_language(user)
        categories = await CategoryCRUD.get_user_categories(session, user.id)
        
        if not categories:
            await message.answer(
                translate_text(
                    language,
                    "❌ You don't have any categories yet.\nCreate one via '📁 Add category'",
                    "❌ У вас пока нет категорий.\nСоздайте первую категорию нажав '📁 Добавить категорию'"
                ),
                reply_markup=get_main_keyboard(language=language)
            )
            return
        
        await message.answer(
            translate_text(
                language,
                "📂 Category management\n\nChoose a category to manage:",
                "📂 Управление категориями\n\nВыберите категорию для управления:"
            ),
            reply_markup=get_categories_list_keyboard(categories, user.id, language=language)
        )
    except Exception as e:
        logger.error(f"Ошибка в manage_categories_menu: {e}")
        await message.answer(
            translate_text(language, "❌ Failed to load categories.", "❌ Произошла ошибка при загрузке категорий."),
            reply_markup=get_main_keyboard(language=language)
        )

@router.callback_query(F.data.startswith("category_menu_"))
async def category_menu(callback: CallbackQuery, session: AsyncSession, user):
    """Меню конкретной категории"""
    try:
        language = get_user_language(user)
        category_id = int(callback.data.split("category_menu_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        
        if not category:
            await callback.answer(translate_text(language, "❌ Category not found", "❌ Категория не найдена"))
            return
        
        # Проверяем права доступа
        is_owner = category.owner_id == user.id
        
        # Получаем количество элементов
        items = await ItemCRUD.get_items_by_category(session, category_id)
        items_count = len(items)
        
        # Определяем тип доступа
        sharing_emoji = {
            "private": _("sharing.private", language=language),
            "view_only": _("sharing.view_only", language=language), 
            "collaborative": _("sharing.collaborative", language=language)
        }
        
        sharing_text = sharing_emoji.get(category.sharing_type, _("sharing.private", language=language))
        owner_text = translate_text(language, "You", "Вы") if is_owner else translate_text(language, "Another user", "Другой пользователь")
        
        text = translate_text(
            language,
            f"📂 **{category.name}**\n\n"
            f"🎯 Items: {items_count}\n"
            f"👤 Owner: {owner_text}\n"
            f"🔐 Access: {sharing_text}\n",
            f"📂 **{category.name}**\n\n"
            f"🎯 Элементов: {items_count}\n"
            f"👤 Владелец: {owner_text}\n"
            f"🔐 Тип доступа: {sharing_text}\n"
        )
        
        if category.sharing_type != "private":
            code = generate_access_code(category.id)
            text += translate_text(language, f"🔑 Access code: `{code}`\n", f"🔑 Код доступа: `{code}`\n")
        
        m = await callback.message.answer(
            text,
            reply_markup=get_category_management_keyboard(category_id, is_owner, language=language),
            parse_mode="Markdown"
        )
        # Это меню управления категорией можно оставить, поэтому без авто-удаления
        
    except Exception as e:
        logger.error(f"Ошибка в category_menu: {e}")
        await callback.answer(translate_text(language, "❌ Something went wrong", "❌ Произошла ошибка"))
    
    await callback.answer()

@router.callback_query(F.data.startswith("category_sharing_"))
async def category_sharing_menu(callback: CallbackQuery, session: AsyncSession, user):
    """Меню настроек доступа к категории"""
    try:
        language = get_user_language(user)
        category_id = int(callback.data.split("category_sharing_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        
        if not category or category.owner_id != user.id:
            await callback.answer(
                translate_text(language, "❌ Category not found or insufficient rights", "❌ Категория не найдена или нет прав доступа")
            )
            return
        
        # Получаем список пользователей с доступом
        shared_users_count = await CategoryCRUD.get_shared_users_count(session, category_id)
        
        sharing_text = {
            "private": translate_text(
                language,
                "🔒 **Private** - only you can view and edit",
                "🔒 **Личная** - только вы можете видеть и редактировать"
            ),
            "view_only": translate_text(
                language,
                "👁 **View only** - others can view via code",
                "👁 **Только просмотр** - другие могут просматривать по коду"
            ),
            "collaborative": translate_text(
                language,
                "✍️ **Collaborative** - others can add and edit items",
                "✍️ **Общая** - другие могут добавлять и редактировать элементы"
            )
        }

        text = translate_text(
            language,
            f"👥 Access management\n"
            f"📂 Category: **{category.name}**\n\n"
            f"Current type: {sharing_text.get(category.sharing_type, 'Unknown')}\n\n"
            f"👥 Users with access: {shared_users_count}\n",
            f"👥 Управление доступом\n"
            f"📂 Категория: **{category.name}**\n\n"
            f"Текущий тип: {sharing_text.get(category.sharing_type, 'Неизвестный')}\n\n"
            f"👥 Пользователей с доступом: {shared_users_count}\n"
        )
        
        if category.sharing_type != "private":
            code = generate_access_code(category.id)
            text += translate_text(language, f"\n🔑 Access code: `{code}`\n", f"\n🔑 Код для доступа: `{code}`\n")
            text += translate_text(language, "Share it with people who need access.", "Отправьте этот код тем, кому хотите дать доступ.")
        
        m = await callback.message.answer(
            text,
            reply_markup=get_category_sharing_keyboard(category_id, language=language),
            parse_mode="Markdown"
        )
        schedule_delete_message(callback.bot, callback.message.chat.id, m.message_id, delay=30)
        
    except Exception as e:
        logger.error(f"Ошибка в category_sharing_menu: {e}")
        await callback.answer(translate_text(language, "❌ Something went wrong", "❌ Произошла ошибка"))
    
    await callback.answer()

@router.callback_query(F.data.startswith("change_sharing_type_"))
async def change_sharing_type(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    """Изменение типа доступа к категории"""
    try:
        language = get_user_language(user)
        category_id = int(callback.data.split("change_sharing_type_")[1])
        
        await state.update_data(category_id=category_id)
        
        await callback.message.answer(
            translate_text(language, "🔐 Choose a new access type:", "🔐 Выберите новый тип доступа к категории:"),
            reply_markup=get_sharing_type_keyboard(language=language)
        )
        await state.set_state(ManageCategoryStates.change_sharing_type)
        
    except Exception as e:
        logger.error(f"Ошибка в change_sharing_type: {e}")
        await callback.answer(translate_text(get_user_language(user), "❌ Something went wrong", "❌ Произошла ошибка"))
    
    await callback.answer()

@router.callback_query(F.data.startswith("sharing_"), ManageCategoryStates.change_sharing_type)
async def process_sharing_type_change(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Обработка изменения типа доступа"""
    try:
        sharing_type = callback.data.split("sharing_")[1]
        
        data = await state.get_data()
        category_id = data.get('category_id')
        
        if not category_id:
            await callback.answer("❌ Ошибка: категория не найдена")
            return
        
        # Узнаём текущий тип доступа
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        if not category:
            await callback.answer("❌ Категория не найдена")
            return
        old_type = category.sharing_type

        # Генерируем share_link для любого типа кроме private
        share_link = None
        if sharing_type in ["view_only", "collaborative"]:
            share_link = generate_share_link(category_id)
        
        await CategoryCRUD.update_category_sharing(session, category_id, sharing_type, share_link)
        
        # Уведомить при смене доступа: если было shared и стало private -> всем сообщить об отзыве и убрать доступ
        # Если стало shared -> уведомлять при раздаче доступа через код (уже реализовано в access_codes/join_shared)
        if old_type in ["view_only", "collaborative"] and sharing_type == "private":
            from sqlalchemy import select
            from database.models import AsyncSessionLocal, User, SharedCategory
            # Сначала соберём список пользователей для уведомления
            async with AsyncSessionLocal() as s:
                result = await s.execute(select(User).where(User.id.in_(
                    select(SharedCategory.user_id).where(SharedCategory.category_id == category_id)
                )))
                users = list(result.scalars().all())
            # Удалим доступы
            await CategoryCRUD.revoke_all_shares(session, category_id)
            # Отправим уведомления
            for u in users:
                await send_category_access_revoked_notification(callback.bot, category, callback.from_user, u)
        
        sharing_names = {
            "private": "🔒 Личная",
            "view_only": "👁 Только просмотр",
            "collaborative": "✍️ Общая"
        }
        
        text = f"✅ Тип доступа изменен на: {sharing_names.get(sharing_type)}"
        
        if sharing_type != "private":
            code = generate_access_code(category_id)
            text += f"\n\n🔑 Код для доступа:\n`{code}`\n\nДайте этот код тем, кому хотите предоставить доступ к категории."
        
        m = await callback.message.answer(text, parse_mode="Markdown")
        schedule_delete_message(callback.bot, callback.message.chat.id, m.message_id, delay=20)
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в process_sharing_type_change: {e}")
        await callback.answer("❌ Произошла ошибка")
        await state.clear()
    
    await callback.answer()

@router.callback_query(F.data.startswith("get_share_link_"))
async def get_share_code(callback: CallbackQuery, session: AsyncSession):
    """Получение кода для доступа к категории"""
    try:
        category_id = int(callback.data.split("get_share_link_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        
        if not category:
            await callback.answer("❌ Категория не найдена")
            return
        
        if category.sharing_type == "private":
            await callback.answer("❌ Личные категории нельзя расшаривать")
            return
        
        access_type = "просмотра" if category.sharing_type == "view_only" else "редактирования"
        code = generate_access_code(category_id)
        
        text = (
            f"🔑 **Код для доступа к категории**\n"
            f"📂 {category.name}\n\n"
            f"Код для {access_type}:\n"
            f"`{code}`\n\n"
            f"📋 Инструкция:\n"
            f"1. Отправьте этот код другому пользователю\n"
            f"2. Пользователь должен нажать кнопку '🔑 Ввести код' в главном меню\n"
            f"3. Ввести полученный код\n"
            f"4. Получить доступ к категории"
        )
        
        m = await callback.message.answer(text, parse_mode="Markdown")
        schedule_delete_message(callback.bot, callback.message.chat.id, m.message_id, delay=30)
        
    except Exception as e:
        logger.error(f"Ошибка в get_share_code: {e}")
        await callback.answer("❌ Произошла ошибка")
    
    await callback.answer()

@router.callback_query(F.data.startswith("category_stats_"))
async def category_stats(callback: CallbackQuery, session: AsyncSession):
    """Статистика категории"""
    try:
        category_id = int(callback.data.split("category_stats_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        items = await ItemCRUD.get_items_by_category(session, category_id)
        
        if not category:
            await callback.answer("❌ Категория не найдена")
            return
        
        # Собираем статистику
        total_items = len(items)
        items_with_price = len([item for item in items if item.price])
        items_with_date = len([item for item in items if item.date_from or item.date])
        items_with_photo = len([item for item in items if item.photo_file_id])
        
        total_value = sum(item.price for item in items if item.price)
        avg_price = total_value / items_with_price if items_with_price > 0 else 0
        
        # Собираем теги
        all_tags = []
        for item in items:
            if item.tags:
                try:
                    import json
                    tags = json.loads(item.tags) if isinstance(item.tags, str) else item.tags
                    all_tags.extend(tags)
                except:
                    pass
        
        unique_tags = len(set(all_tags))
        
        text = (
            f"📊 **Статистика категории**\n"
            f"📂 {category.name}\n\n"
            f"🎯 Всего элементов: {total_items}\n"
            f"💸 С указанной ценой: {items_with_price}\n"
            f"📅 С датами: {items_with_date}\n"
            f"📷 С фото: {items_with_photo}\n"
            f"🏷 Уникальных тегов: {unique_tags}\n\n"
        )
        
        if total_value > 0:
            from utils.helpers import format_price
            text += f"💰 Общая стоимость: {format_price(total_value)}\n"
        
        if avg_price > 0:
            text += f"📈 Средняя цена: {format_price(avg_price)}\n"
        
        await callback.message.answer(text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка в category_stats: {e}")
        await callback.answer("❌ Произошла ошибка")
    
    await callback.answer()

@router.callback_query(F.data.startswith("category_rename_"))
async def category_rename_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало переименования категории"""
    try:
        category_id = int(callback.data.split("category_rename_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        
        if not category:
            await callback.answer("❌ Категория не найдена")
            return
        
        await state.update_data(category_id=category_id)
        
        m = await callback.message.answer(
            f"✏️ Переименование категории\n"
            f"Текущее название: **{category.name}**\n\n"
            f"Введите новое название:",
            reply_markup=get_back_keyboard(),
            parse_mode="Markdown"
        )
        await state.set_state(ManageCategoryStates.rename)
        schedule_delete_message(callback.bot, callback.message.chat.id, m.message_id, delay=30)
        
    except Exception as e:
        logger.error(f"Ошибка в category_rename_start: {e}")
        await callback.answer("❌ Произошла ошибка")
    
    await callback.answer()

@router.message(ManageCategoryStates.rename)
async def process_category_rename(message: Message, session: AsyncSession, user, state: FSMContext):
    """Обработка переименования категории"""
    if message.text == "◀️ Назад":
        await state.clear()
        await message.answer(
            "🏠 Главное меню",
            reply_markup=get_main_keyboard()
        )
        return
        
    if not message.text or message.text.strip() == "":
        await message.answer("❌ Название не может быть пустым. Попробуйте еще раз:")
        return
    
    try:
        data = await state.get_data()
        category_id = data.get('category_id')
        
        if not category_id:
            await message.answer(
                "❌ Ошибка: категория не найдена.",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            return
        
        new_name = message.text.strip()
        
        # Валидация названия
        if len(new_name) > 100:
            await message.answer("❌ Название слишком длинное (максимум 100 символов). Попробуйте еще раз:")
            return
        
        if len(new_name) < 2:
            await message.answer("❌ Название слишком короткое (минимум 2 символа). Попробуйте еще раз:")
            return
        
        # Проверяем, нет ли уже такой категории у пользователя
        user_categories = await CategoryCRUD.get_user_categories(session, user.id)
        own_categories = [cat for cat in user_categories if cat.owner_id == user.id]
        existing_names = [cat.name.lower() for cat in own_categories if cat.id != category_id]
        
        if new_name.lower() in existing_names:
            await message.answer(
                f"❌ Категория с названием '{new_name}' уже существует. "
                f"Введите другое название:"
            )
            return
        
        await CategoryCRUD.update_category_name(session, category_id, new_name)
        await state.clear()
        
        m = await message.answer(
            f"✅ Категория переименована в: **{new_name}**",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
        schedule_delete_message(message.bot, message.chat.id, m.message_id, delay=10)
        
    except Exception as e:
        logger.error(f"Ошибка в process_category_rename: {e}")
        await message.answer(
            "❌ Произошла ошибка при переименовании категории.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()

@router.callback_query(F.data.startswith("category_delete_"))
async def category_delete_confirm(callback: CallbackQuery, session: AsyncSession):
    """Подтверждение удаления категории"""
    try:
        category_id = int(callback.data.split("category_delete_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        items = await ItemCRUD.get_items_by_category(session, category_id)
        
        if not category:
            await callback.answer("❌ Категория не найдена")
            return
        
        items_count = len(items)
        warning = f"\n⚠️ В категории {items_count} элементов - они будут удалены!" if items_count > 0 else ""
        
        await callback.message.answer(
            f"❓ Вы уверены, что хотите удалить категорию '{category.name}'?{warning}",
            reply_markup=get_confirmation_keyboard("delete_category", category_id)
        )
        
    except Exception as e:
        logger.error(f"Ошибка в category_delete_confirm: {e}")
        await callback.answer("❌ Произошла ошибка")
    
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_category_"))
async def confirm_delete_category(callback: CallbackQuery, session: AsyncSession):
    """Подтверждение удаления категории"""
    try:
        category_id = int(callback.data.split("confirm_delete_category_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        
        if not category:
            await callback.answer("❌ Категория не найдена")
            return
        
        category_name = category.name
        
        # Удаляем все элементы в категории
        items = await ItemCRUD.get_items_by_category(session, category_id)
        for item in items:
            await ItemCRUD.delete_item(session, item.id)
        
        # Удаляем категорию
        await CategoryCRUD.delete_category(session, category_id)
        
        await callback.message.edit_text(f"✅ Категория '{category_name}' удалена!")
        
    except Exception as e:
        logger.error(f"Ошибка в confirm_delete_category: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при удалении категории")
    
    await callback.answer()

@router.callback_query(F.data.startswith("cancel_delete_category_"))
async def cancel_delete_category(callback: CallbackQuery):
    """Отмена удаления категории"""
    await callback.message.edit_text("❌ Удаление отменено")
    await callback.answer()

@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.answer(
        "🏠 Главное меню",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery, session: AsyncSession, user):
    """Возврат к списку категорий"""
    try:
        categories = await CategoryCRUD.get_user_categories(session, user.id)
        
        await callback.message.answer(
            "📂 Управление категориями\n\n"
            "Выберите категорию для управления:",
            reply_markup=get_categories_list_keyboard(categories, user.id)
        )
        
    except Exception as e:
        logger.error(f"Ошибка в back_to_categories: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка при загрузке категорий.",
            reply_markup=get_main_keyboard()
        )
    
    await callback.answer()

# Вспомогательные функции
def generate_share_link(category_id: int) -> str:
    """Генерация ссылки для доступа к категории"""
    random_part = str(uuid.uuid4())[:8]
    return f"share_{category_id}_{random_part}"

def generate_access_code(category_id: int) -> str:
    """Генерация кода доступа (6-значный)"""
    # Создаем 6-значный код на основе ID категории и случайного числа
    random_num = random.randint(100000, 999999)
    return f"{category_id:03d}{random_num % 1000:03d}"
