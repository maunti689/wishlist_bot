from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import ItemCRUD, CategoryCRUD
from keyboards import get_main_keyboard, get_item_actions_keyboard, get_confirmation_keyboard
from utils.helpers import format_item_card
from utils.notifications import send_item_updated_notification
from utils.localization import translate_text, get_user_language, get_value_variants

router = Router()

@router.message(F.text.in_(get_value_variants("buttons.view_list")))
async def view_list(message: Message, session: AsyncSession, user, state: FSMContext):
    """Просмотр списка элементов"""
    await state.clear()
    
    try:
        language = get_user_language(user)
        items = await ItemCRUD.get_user_items(session, user.id)
        
        if not items:
            await message.answer(
                translate_text(
                    language,
                    "ℹ️ Your list is empty.\nAdd your first item with '➕ Add item'",
                    "ℹ️ Ваш список пока пуст.\nДобавьте первый элемент нажав '➕ Добавить элемент'"
                ),
                reply_markup=get_main_keyboard(language=language)
            )
            return
        
        await message.answer(
            translate_text(language, f"📃 Your items ({len(items)}):", f"📃 Ваши элементы ({len(items)}):")
        )
        
        for item in items:
            try:
                card_text = await format_item_card(session, item)
                # Определяем право редактирования
                can_edit = False
                if item.category and item.category.owner_id == user.id:
                    can_edit = True
                else:
                    access = await CategoryCRUD.check_user_access(session, item.category_id, user.id)
                    can_edit = bool(access and getattr(access, 'can_edit', False))
                
                if item.photo_file_id:
                    await message.answer_photo(
                        photo=item.photo_file_id,
                        caption=card_text,
                        reply_markup=get_item_actions_keyboard(item.id, can_edit=can_edit, language=language),
                        parse_mode="Markdown"
                    )
                else:
                    await message.answer(
                        card_text,
                        reply_markup=get_item_actions_keyboard(item.id, can_edit=can_edit, language=language),
                        parse_mode="Markdown"
                    )
            except Exception as e:
                # Если ошибка с конкретным элементом, пропускаем его
                await message.answer(
                    translate_text(language, f"⚠️ Failed to display item: {item.name}", f"⚠️ Ошибка отображения элемента: {item.name}")
                )
                continue
        
        await message.answer(
            translate_text(language, "That's all your items! 👆", "Это все ваши элементы! 👆"),
            reply_markup=get_main_keyboard(language=language)
        )
        
    except Exception as e:
        await message.answer(
            translate_text(language, "❌ Failed to load the list", "❌ Произошла ошибка при загрузке списка"),
            reply_markup=get_main_keyboard(language=language)
        )

@router.callback_query(F.data.startswith("delete_item_"))
async def delete_item_confirm(callback: CallbackQuery, session: AsyncSession, user):
    """Подтверждение удаления элемента"""
    item_id = int(callback.data.split("delete_item_")[1])
    language = get_user_language(user)
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    
    if not item:
        await callback.answer(translate_text(language, "❌ Item not found", "❌ Элемент не найден"))
        return
    
    # Проверяем права
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    allowed = category and (category.owner_id == user.id)
    if not allowed:
        access = await CategoryCRUD.check_user_access(session, item.category_id, user.id)
        allowed = bool(access and getattr(access, 'can_edit', False))
    if not allowed:
        await callback.answer(
            translate_text(language, "❌ You don't have permission to delete", "❌ У вас нет прав на удаление"),
            show_alert=True
        )
        return

    await callback.message.answer(
        translate_text(
            language,
            f"❓ Delete item '{item.name}'?",
            f"❓ Вы уверены, что хотите удалить элемент '{item.name}'?"
        ),
        reply_markup=get_confirmation_keyboard("delete", item_id, language=language)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_item(callback: CallbackQuery, session: AsyncSession, user):
    """Подтверждение удаления элемента"""
    item_id = int(callback.data.split("confirm_delete_")[1])
    language = get_user_language(user)
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    
    if not item:
        await callback.answer(translate_text(language, "❌ Item not found", "❌ Элемент не найден"))
        return
    
    # Проверка прав
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    allowed = category and (category.owner_id == user.id)
    if not allowed:
        access = await CategoryCRUD.check_user_access(session, item.category_id, user.id)
        allowed = bool(access and getattr(access, 'can_edit', False))
    if not allowed:
        await callback.answer(
            translate_text(language, "❌ You don't have permission to delete", "❌ У вас нет прав на удаление"),
            show_alert=True
        )
        return

    # Сохраняем данные для уведомления до удаления
    item_name = item.name
    # category уже загружена выше

    await ItemCRUD.delete_item(session, item_id)
    
    # Уведомляем участников общей категории (кроме инициатора)
    if category:
        await send_item_updated_notification(callback.bot, category, item, user, "delete")
    
    await callback.message.edit_text(
        translate_text(language, f"✅ Item '{item_name}' deleted!", f"✅ Элемент '{item_name}' удален!")
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cancel_delete_"))
async def cancel_delete_item(callback: CallbackQuery, user):
    """Отмена удаления элемента"""
    language = get_user_language(user)
    await callback.message.edit_text(
        translate_text(language, "❌ Deletion cancelled", "❌ Удаление отменено")
    )
    await callback.answer()

@router.callback_query(F.data.startswith("edit_item_"))
async def edit_item_menu(callback: CallbackQuery, session: AsyncSession, user):
    """Меню редактирования элемента"""
    item_id = int(callback.data.split("edit_item_")[1])
    language = get_user_language(user)
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    
    if not item:
        await callback.answer(translate_text(language, "❌ Item not found", "❌ Элемент не найден"))
        return
    
    # Проверяем права
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    allowed = category and (category.owner_id == user.id)
    if not allowed:
        access = await CategoryCRUD.check_user_access(session, item.category_id, user.id)
        allowed = bool(access and getattr(access, 'can_edit', False))
    if not allowed:
        await callback.answer(
            translate_text(language, "❌ You don't have permission to edit", "❌ У вас нет прав на редактирование"),
            show_alert=True
        )
        return

    from keyboards import get_edit_fields_keyboard
    
    await callback.message.answer(
        translate_text(
            language,
            f"✏️ Editing item '{item.name}'\n\nChoose a field to update:",
            f"✏️ Редактирование элемента '{item.name}'\n\nВыберите поле для изменения:"
        ),
        reply_markup=get_edit_fields_keyboard(item_id, language=language)
    )
    await callback.answer()

# Обработчики редактирования полей удалены из этого модуля,
# чтобы избежать дублирования с handlers/admin.py и конфликтов состояний.
# Все callback'и вида `edit_field_*` обрабатываются в handlers/admin.py.
