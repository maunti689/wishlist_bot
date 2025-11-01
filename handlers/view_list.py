from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import ItemCRUD, CategoryCRUD
from keyboards import get_main_keyboard, get_item_actions_keyboard, get_confirmation_keyboard
from utils.helpers import format_item_card
from utils.notifications import send_item_updated_notification

router = Router()

@router.message(F.text == "📃 Посмотреть список")
async def view_list(message: Message, session: AsyncSession, user, state: FSMContext):
    """Просмотр списка элементов"""
    await state.clear()
    
    try:
        items = await ItemCRUD.get_user_items(session, user.id)
        
        if not items:
            await message.answer(
                "ℹ️ Ваш список пока пуст.\n"
                "Добавьте первый элемент нажав '➕ Добавить элемент'",
                reply_markup=get_main_keyboard()
            )
            return
        
        await message.answer(f"📃 Ваши элементы ({len(items)}):")
        
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
                        reply_markup=get_item_actions_keyboard(item.id, can_edit=can_edit),
                        parse_mode="Markdown"
                    )
                else:
                    await message.answer(
                        card_text,
                        reply_markup=get_item_actions_keyboard(item.id, can_edit=can_edit),
                        parse_mode="Markdown"
                    )
            except Exception as e:
                # Если ошибка с конкретным элементом, пропускаем его
                await message.answer(f"⚠️ Ошибка отображения элемента: {item.name}")
                continue
        
        await message.answer(
            "Это все ваши элементы! 👆",
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        await message.answer(
            "❌ Произошла ошибка при загрузке списка",
            reply_markup=get_main_keyboard()
        )

@router.callback_query(F.data.startswith("delete_item_"))
async def delete_item_confirm(callback: CallbackQuery, session: AsyncSession, user):
    """Подтверждение удаления элемента"""
    item_id = int(callback.data.split("delete_item_")[1])
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    
    if not item:
        await callback.answer("❌ Элемент не найден")
        return
    
    # Проверяем права
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    allowed = category and (category.owner_id == user.id)
    if not allowed:
        access = await CategoryCRUD.check_user_access(session, item.category_id, user.id)
        allowed = bool(access and getattr(access, 'can_edit', False))
    if not allowed:
        await callback.answer("❌ У вас нет прав на удаление", show_alert=True)
        return

    await callback.message.answer(
        f"❓ Вы уверены, что хотите удалить элемент '{item.name}'?",
        reply_markup=get_confirmation_keyboard("delete", item_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_item(callback: CallbackQuery, session: AsyncSession, user):
    """Подтверждение удаления элемента"""
    item_id = int(callback.data.split("confirm_delete_")[1])
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    
    if not item:
        await callback.answer("❌ Элемент не найден")
        return
    
    # Проверка прав
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    allowed = category and (category.owner_id == user.id)
    if not allowed:
        access = await CategoryCRUD.check_user_access(session, item.category_id, user.id)
        allowed = bool(access and getattr(access, 'can_edit', False))
    if not allowed:
        await callback.answer("❌ У вас нет прав на удаление", show_alert=True)
        return

    # Сохраняем данные для уведомления до удаления
    item_name = item.name
    # category уже загружена выше

    await ItemCRUD.delete_item(session, item_id)
    
    # Уведомляем участников общей категории (кроме инициатора)
    if category:
        await send_item_updated_notification(callback.bot, category, item, user, "delete")
    
    await callback.message.edit_text(f"✅ Элемент '{item_name}' удален!")
    await callback.answer()

@router.callback_query(F.data.startswith("cancel_delete_"))
async def cancel_delete_item(callback: CallbackQuery):
    """Отмена удаления элемента"""
    await callback.message.edit_text("❌ Удаление отменено")
    await callback.answer()

@router.callback_query(F.data.startswith("edit_item_"))
async def edit_item_menu(callback: CallbackQuery, session: AsyncSession, user):
    """Меню редактирования элемента"""
    item_id = int(callback.data.split("edit_item_")[1])
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    
    if not item:
        await callback.answer("❌ Элемент не найден")
        return
    
    # Проверяем права
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    allowed = category and (category.owner_id == user.id)
    if not allowed:
        access = await CategoryCRUD.check_user_access(session, item.category_id, user.id)
        allowed = bool(access and getattr(access, 'can_edit', False))
    if not allowed:
        await callback.answer("❌ У вас нет прав на редактирование", show_alert=True)
        return

    from keyboards import get_edit_fields_keyboard
    
    await callback.message.answer(
        f"✏️ Редактирование элемента '{item.name}'\n\n"
        "Выберите поле для изменения:",
        reply_markup=get_edit_fields_keyboard(item_id)
    )
    await callback.answer()

# Обработчики редактирования полей удалены из этого модуля,
# чтобы избежать дублирования с handlers/admin.py и конфликтов состояний.
# Все callback'и вида `edit_field_*` обрабатываются в handlers/admin.py.
