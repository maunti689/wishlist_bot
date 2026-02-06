from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from database.crud import CategoryCRUD, ItemCRUD, UserCRUD
from database.models import SharedCategory
from states import ManageCategoryStates
from keyboards import (
    get_main_keyboard, get_back_keyboard, get_categories_list_keyboard,
    get_category_management_keyboard, get_category_sharing_keyboard,
    get_sharing_type_keyboard, get_confirmation_keyboard
)
from utils.helpers import format_item_card, escape_markdown, format_price
from utils.cleanup import schedule_delete_message
from utils.notifications import send_category_shared_notification, send_category_access_revoked_notification
from utils.localization import translate as _, translate_text, get_user_language, get_value_variants, DEFAULT_LANGUAGE

router = Router()
BACK_BUTTONS = get_value_variants("buttons.back")
logger = logging.getLogger(__name__)

@router.message(F.text.in_(get_value_variants("buttons.manage_categories")))
async def manage_categories_menu(message: Message, session: AsyncSession, user, state: FSMContext):
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
        logger.error(f"Error in manage_categories_menu: {e}")
        await message.answer(
            translate_text(language, "❌ Failed to load categories.", "❌ Произошла ошибка при загрузке категорий."),
            reply_markup=get_main_keyboard(language=language)
        )

@router.callback_query(F.data.startswith("category_menu_"))
async def category_menu(callback: CallbackQuery, session: AsyncSession, user):
    try:
        language = get_user_language(user)
        category_id = int(callback.data.split("category_menu_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        
        if not category:
            await callback.answer(translate_text(language, "❌ Category not found", "❌ Категория не найдена"))
            return
        
        is_owner = category.owner_id == user.id
        
        items = await ItemCRUD.get_items_by_category(session, category_id)
        items_count = len(items)
        
        sharing_emoji = {
            "private": _("sharing.private", language=language),
            "view_only": _("sharing.view_only", language=language), 
            "collaborative": _("sharing.collaborative", language=language)
        }
        
        sharing_text = sharing_emoji.get(category.sharing_type, _("sharing.private", language=language))
        owner_text = translate_text(language, "You", "Вы") if is_owner else translate_text(language, "Another user", "Другой пользователь")
        
        safe_category_name = escape_markdown(category.name)
        text = translate_text(
            language,
            f"📂 **{safe_category_name}**\n\n"
            f"🎯 Items: {items_count}\n"
            f"👤 Owner: {owner_text}\n"
            f"🔐 Access: {sharing_text}\n",
            f"📂 **{safe_category_name}**\n\n"
            f"🎯 Элементов: {items_count}\n"
            f"👤 Владелец: {owner_text}\n"
            f"🔐 Тип доступа: {sharing_text}\n"
        )
        
        if category.sharing_type != "private":
            code = category.share_link or await CategoryCRUD.ensure_share_code(session, category.id)
            text += translate_text(language, f"🔑 Access code: `{code}`\n", f"🔑 Код доступа: `{code}`\n")
        
        m = await callback.message.answer(
            text,
            reply_markup=get_category_management_keyboard(category_id, is_owner, language=language),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in category_menu: {e}")
        await callback.answer(translate_text(language, "❌ Something went wrong", "❌ Произошла ошибка"))
    
    await callback.answer()

@router.callback_query(F.data.startswith("category_sharing_"))
async def category_sharing_menu(callback: CallbackQuery, session: AsyncSession, user):
    try:
        language = get_user_language(user)
        category_id = int(callback.data.split("category_sharing_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        
        if not category or category.owner_id != user.id:
            await callback.answer(
                translate_text(language, "❌ Category not found or insufficient rights", "❌ Категория не найдена или нет прав доступа")
            )
            return
        
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

        safe_category_name = escape_markdown(category.name)
        text = translate_text(
            language,
            f"👥 Access management\n"
            f"📂 Category: **{safe_category_name}**\n\n"
            f"Current type: {sharing_text.get(category.sharing_type, 'Unknown')}\n\n"
            f"👥 Users with access: {shared_users_count}\n",
            f"👥 Управление доступом\n"
            f"📂 Категория: **{safe_category_name}**\n\n"
            f"Текущий тип: {sharing_text.get(category.sharing_type, 'Неизвестный')}\n\n"
            f"👥 Пользователей с доступом: {shared_users_count}\n"
        )
        
        if category.sharing_type != "private":
            code = category.share_link or await CategoryCRUD.ensure_share_code(session, category.id)
            text += translate_text(language, f"\n🔑 Access code: `{code}`\n", f"\n🔑 Код для доступа: `{code}`\n")
            text += translate_text(language, "Share it with people who need access.", "Отправьте этот код тем, кому хотите дать доступ.")
        
        m = await callback.message.answer(
            text,
            reply_markup=get_category_sharing_keyboard(category_id, language=language),
            parse_mode="Markdown"
        )
        schedule_delete_message(callback.bot, callback.message.chat.id, m.message_id, delay=30)
        
    except Exception as e:
        logger.error(f"Error in category_sharing_menu: {e}")
        await callback.answer(translate_text(language, "❌ Something went wrong", "❌ Произошла ошибка"))
    
    await callback.answer()

@router.callback_query(F.data.startswith("change_sharing_type_"))
async def change_sharing_type(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
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
        logger.error(f"Error in change_sharing_type: {e}")
        await callback.answer(translate_text(get_user_language(user), "❌ Something went wrong", "❌ Произошла ошибка"))
    
    await callback.answer()

@router.callback_query(F.data.startswith("sharing_"), ManageCategoryStates.change_sharing_type)
async def process_sharing_type_change(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    try:
        language = get_user_language(user)
        sharing_type = callback.data.split("sharing_")[1]
        
        data = await state.get_data()
        category_id = data.get('category_id')
        
        if not category_id:
            await callback.answer(
                translate_text(language, "❌ Category not found", "❌ Категория не найдена")
            )
            return
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        if not category:
            await callback.answer(
                translate_text(language, "❌ Category not found", "❌ Категория не найдена")
            )
            return
        old_type = category.sharing_type

        share_code = None
        if sharing_type in ["view_only", "collaborative"]:
            share_code = category.share_link or await CategoryCRUD.generate_unique_share_code(session)
        await CategoryCRUD.update_category_sharing(session, category_id, sharing_type, share_code)
        
        if old_type in ["view_only", "collaborative"] and sharing_type == "private":
            from sqlalchemy import select
            from database.models import AsyncSessionLocal, User, SharedCategory
            async with AsyncSessionLocal() as s:
                result = await s.execute(select(User).where(User.id.in_(
                    select(SharedCategory.user_id).where(SharedCategory.category_id == category_id)
                )))
                users = list(result.scalars().all())
            await CategoryCRUD.revoke_all_shares(session, category_id)
            for u in users:
                await send_category_access_revoked_notification(callback.bot, category, callback.from_user, u)
        
        sharing_names = {
            "private": translate_text(language, "🔒 Private", "🔒 Личная"),
            "view_only": translate_text(language, "👁 View only", "👁 Только просмотр"),
            "collaborative": translate_text(language, "✍️ Collaborative", "✍️ Общая")
        }
        
        text = translate_text(
            language,
            f"✅ Access type changed to: {sharing_names.get(sharing_type)}",
            f"✅ Тип доступа изменен на: {sharing_names.get(sharing_type)}"
        )
        
        if sharing_type != "private" and share_code:
            text += translate_text(
                language,
                f"\n\n🔑 Access code:\n`{share_code}`\n\nShare this code with people who need access to the category.",
                f"\n\n🔑 Код для доступа:\n`{share_code}`\n\nДайте этот код тем, кому хотите предоставить доступ к категории."
            )
        
        m = await callback.message.answer(text, parse_mode="Markdown")
        schedule_delete_message(callback.bot, callback.message.chat.id, m.message_id, delay=20)
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in process_sharing_type_change: {e}")
        await callback.answer(
            translate_text(language if 'language' in locals() else None, "❌ Something went wrong", "❌ Произошла ошибка")
        )
        await state.clear()
    
    await callback.answer()

@router.callback_query(F.data.startswith("get_share_link_"))
async def get_share_code(callback: CallbackQuery, session: AsyncSession, user):
    try:
        language = get_user_language(user)
        category_id = int(callback.data.split("get_share_link_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        
        if not category:
            await callback.answer(
                translate_text(language, "❌ Category not found", "❌ Категория не найдена")
            )
            return
        
        if category.sharing_type == "private":
            await callback.answer(
                translate_text(language, "❌ Private categories cannot be shared", "❌ Личные категории нельзя расшаривать")
            )
            return
        
        access_type_en = "viewing" if category.sharing_type == "view_only" else "editing"
        access_type_ru = "просмотра" if category.sharing_type == "view_only" else "редактирования"
        code = category.share_link or await CategoryCRUD.ensure_share_code(session, category_id)
        
        safe_category_name = escape_markdown(category.name)
        text = translate_text(
            language,
            (
                f"🔑 **Category access code**\n"
                f"📂 {safe_category_name}\n\n"
                f"Code for {access_type_en}:\n"
                f"`{code}`\n\n"
                f"📋 Instructions:\n"
                f"1. Send this code to another user\n"
                f"2. They must tap '🔑 Enter code' in the main menu\n"
                f"3. Enter the received code\n"
                f"4. Gain access to the category"
            ),
            (
                f"🔑 **Код для доступа к категории**\n"
                f"📂 {safe_category_name}\n\n"
                f"Код для {access_type_ru}:\n"
                f"`{code}`\n\n"
                f"📋 Инструкция:\n"
                f"1. Отправьте этот код другому пользователю\n"
                f"2. Пользователь должен нажать кнопку '🔑 Ввести код' в главном меню\n"
                f"3. Ввести полученный код\n"
                f"4. Получить доступ к категории"
            )
        )
        
        m = await callback.message.answer(text, parse_mode="Markdown")
        schedule_delete_message(callback.bot, callback.message.chat.id, m.message_id, delay=30)
        
    except Exception as e:
        logger.error(f"Error in get_share_code: {e}")
        await callback.answer(
            translate_text(language if 'language' in locals() else None, "❌ Something went wrong", "❌ Произошла ошибка")
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("category_stats_"))
async def category_stats(callback: CallbackQuery, session: AsyncSession, user):
    try:
        language = get_user_language(user)
        category_id = int(callback.data.split("category_stats_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        items = await ItemCRUD.get_items_by_category(session, category_id)
        
        if not category:
            await callback.answer(
                translate_text(language, "❌ Category not found", "❌ Категория не найдена")
            )
            return
        
        total_items = len(items)
        items_with_price = len([item for item in items if item.price])
        items_with_date = len([item for item in items if item.date_from or item.date])
        items_with_photo = len([item for item in items if item.photo_file_id])
        
        total_value = sum(item.price for item in items if item.price)
        avg_price = total_value / items_with_price if items_with_price > 0 else 0
        
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
        
        safe_category_name = escape_markdown(category.name)
        from utils.helpers import format_price
        text_en = (
            f"📊 **Category stats**\n"
            f"📂 {safe_category_name}\n\n"
            f"🎯 Total items: {total_items}\n"
            f"💸 With price: {items_with_price}\n"
            f"📅 With dates: {items_with_date}\n"
            f"📷 With photos: {items_with_photo}\n"
            f"🏷 Unique tags: {unique_tags}\n\n"
        )
        text_ru = (
            f"📊 **Статистика категории**\n"
            f"📂 {safe_category_name}\n\n"
            f"🎯 Всего элементов: {total_items}\n"
            f"💸 С указанной ценой: {items_with_price}\n"
            f"📅 С датами: {items_with_date}\n"
            f"📷 С фото: {items_with_photo}\n"
            f"🏷 Уникальных тегов: {unique_tags}\n\n"
        )
        
        if total_value > 0:
            text_en += f"💰 Total value: {format_price(total_value)}\n"
            text_ru += f"💰 Общая стоимость: {format_price(total_value)}\n"
        
        if avg_price > 0:
            text_en += f"📈 Average price: {format_price(avg_price)}\n"
            text_ru += f"📈 Средняя цена: {format_price(avg_price)}\n"
        
        await callback.message.answer(
            translate_text(language, text_en, text_ru),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in category_stats: {e}")
        await callback.answer(
            translate_text(language if 'language' in locals() else None, "❌ Something went wrong", "❌ Произошла ошибка")
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("category_rename_"))
async def category_rename_start(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    try:
        language = get_user_language(user)
        category_id = int(callback.data.split("category_rename_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        
        if not category:
            await callback.answer(
                translate_text(language, "❌ Category not found", "❌ Категория не найдена")
            )
            return
        
        await state.update_data(category_id=category_id)
        
        safe_category_name = escape_markdown(category.name)
        m = await callback.message.answer(
            translate_text(
                language,
                f"✏️ Category rename\nCurrent name: **{safe_category_name}**\n\nEnter a new name:",
                f"✏️ Переименование категории\nТекущее название: **{safe_category_name}**\n\nВведите новое название:"
            ),
            reply_markup=get_back_keyboard(language=language),
            parse_mode="Markdown"
        )
        await state.set_state(ManageCategoryStates.rename)
        schedule_delete_message(callback.bot, callback.message.chat.id, m.message_id, delay=30)
        
    except Exception as e:
        logger.error(f"Error in category_rename_start: {e}")
        await callback.answer(
            translate_text(language if 'language' in locals() else None, "❌ Something went wrong", "❌ Произошла ошибка")
        )
    
    await callback.answer()

@router.message(ManageCategoryStates.rename)
async def process_category_rename(message: Message, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    if message.text in BACK_BUTTONS:
        await state.clear()
        await message.answer(
            translate_text(language, "🏠 Main menu", "🏠 Главное меню"),
            reply_markup=get_main_keyboard(language=language)
        )
        return
        
    if not message.text or message.text.strip() == "":
        await message.answer(
            translate_text(language, "❌ Name cannot be empty. Try again:", "❌ Название не может быть пустым. Попробуйте еще раз:")
        )
        return
    
    try:
        data = await state.get_data()
        category_id = data.get('category_id')
        
        if not category_id:
            await message.answer(
                translate_text(language, "❌ Category not found.", "❌ Ошибка: категория не найдена."),
                reply_markup=get_main_keyboard(language=language)
            )
            await state.clear()
            return
        
        new_name = message.text.strip()
        
        if len(new_name) > 100:
            await message.answer(
                translate_text(language, "❌ Name is too long (max 100 characters). Try again:", "❌ Название слишком длинное (максимум 100 символов). Попробуйте еще раз:")
            )
            return
        
        if len(new_name) < 2:
            await message.answer(
                translate_text(language, "❌ Name is too short (min 2 characters). Try again:", "❌ Название слишком короткое (минимум 2 символа). Попробуйте еще раз:")
            )
            return
        
        user_categories = await CategoryCRUD.get_user_categories(session, user.id)
        own_categories = [cat for cat in user_categories if cat.owner_id == user.id]
        existing_names = [cat.name.lower() for cat in own_categories if cat.id != category_id]
        
        if new_name.lower() in existing_names:
            await message.answer(
                translate_text(
                    language,
                    f"❌ Category named '{new_name}' already exists.\nEnter a different name:",
                    f"❌ Категория с названием '{new_name}' уже существует.\nВведите другое название:"
                )
            )
            return

        await CategoryCRUD.update_category_name(session, category_id, new_name)
        await state.clear()

        m = await message.answer(
            translate_text(
                language,
                f"✅ Category renamed to: **{escape_markdown(new_name)}**",
                f"✅ Категория переименована в: **{escape_markdown(new_name)}**"
            ),
            reply_markup=get_main_keyboard(language=language),
            parse_mode="Markdown"
        )
        schedule_delete_message(message.bot, message.chat.id, m.message_id, delay=10)
        
    except Exception as e:
        logger.error(f"Error in process_category_rename: {e}")
        await message.answer(
            translate_text(language, "❌ Failed to rename the category.", "❌ Произошла ошибка при переименовании категории."),
            reply_markup=get_main_keyboard(language=language)
        )
        await state.clear()

@router.callback_query(F.data.startswith("category_delete_"))
async def category_delete_confirm(callback: CallbackQuery, session: AsyncSession, user):
    try:
        language = get_user_language(user)
        category_id = int(callback.data.split("category_delete_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        items = await ItemCRUD.get_items_by_category(session, category_id)
        
        if not category:
            await callback.answer(
                translate_text(language, "❌ Category not found", "❌ Категория не найдена")
            )
            return
        
        items_count = len(items)
        warning = ""
        if items_count > 0:
            warning = translate_text(
                language,
                f"\n⚠️ This category contains {items_count} item(s) — they will be deleted!",
                f"\n⚠️ В категории {items_count} элементов — они будут удалены!"
            )
        
        await callback.message.answer(
            translate_text(
                language,
                f"❓ Delete category '{category.name}'?{warning}",
                f"❓ Вы уверены, что хотите удалить категорию '{category.name}'?{warning}"
            ),
            reply_markup=get_confirmation_keyboard("delete_category", category_id, language=language)
        )
        
    except Exception as e:
        logger.error(f"Error in category_delete_confirm: {e}")
        await callback.answer(
            translate_text(language if 'language' in locals() else None, "❌ Something went wrong", "❌ Произошла ошибка")
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_category_"))
async def confirm_delete_category(callback: CallbackQuery, session: AsyncSession, user):
    try:
        language = get_user_language(user)
        category_id = int(callback.data.split("confirm_delete_category_")[1])
        
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        
        if not category:
            await callback.answer(
                translate_text(language, "❌ Category not found", "❌ Категория не найдена")
            )
            return
        
        category_name = escape_markdown(category.name)
        
        items = await ItemCRUD.get_items_by_category(session, category_id)
        for item in items:
            await ItemCRUD.delete_item(session, item.id)
        
        await CategoryCRUD.delete_category(session, category_id)
        
        await callback.message.edit_text(
            translate_text(
                language,
                f"✅ Category '{category_name}' deleted!",
                f"✅ Категория '{category_name}' удалена!"
            ),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in confirm_delete_category: {e}")
        await callback.message.edit_text(
            translate_text(language if 'language' in locals() else None, "❌ Failed to delete the category", "❌ Произошла ошибка при удалении категории")
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("cancel_delete_category_"))
async def cancel_delete_category(callback: CallbackQuery, user):
    language = get_user_language(user)
    await callback.message.edit_text(
        translate_text(language, "❌ Deletion cancelled", "❌ Удаление отменено")
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery, user):
    language = get_user_language(user)
    await callback.message.answer(
        translate_text(language, "🏠 Main menu", "🏠 Главное меню"),
        reply_markup=get_main_keyboard(language=language)
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery, session: AsyncSession, user):
    try:
        language = get_user_language(user)
        categories = await CategoryCRUD.get_user_categories(session, user.id)
        
        await callback.message.answer(
            translate_text(
                language,
                "📂 Category management\n\nChoose a category to manage:",
                "📂 Управление категориями\n\nВыберите категорию для управления:"
            ),
            reply_markup=get_categories_list_keyboard(categories, user.id, language=language)
        )
        
    except Exception as e:
        logger.error(f"Error in back_to_categories: {e}")
        await callback.message.answer(
            translate_text(language if 'language' in locals() else None, "❌ Failed to load categories.", "❌ Произошла ошибка при загрузке категорий."),
            reply_markup=get_main_keyboard(language=language if 'language' in locals() else DEFAULT_LANGUAGE)
        )
    
    await callback.answer()
