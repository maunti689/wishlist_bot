from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import json

from database.crud import ItemCRUD, TagCRUD, LocationCRUD, CategoryCRUD
from states import EditItemStates
from keyboards import (
    get_main_keyboard, get_back_keyboard, get_skip_keyboard,
    get_tags_keyboard, get_location_type_keyboard, get_locations_keyboard,
    get_date_input_keyboard
)
from utils.helpers import (
    parse_tags, validate_price, parse_date, format_item_card, escape_markdown
)
from utils.notifications import send_item_updated_notification
from utils.cleanup import add_ephemeral_message, cleanup_ephemeral_messages, schedule_delete_message
from utils.localization import get_value_variants

router = Router()

BACK_BUTTONS = get_value_variants("buttons.back")
SKIP_BUTTONS = get_value_variants("buttons.skip")

async def _can_edit(session: AsyncSession, category_id: int, user) -> bool:
    category = await CategoryCRUD.get_category_by_id(session, category_id)
    if not category:
        return False
    if category.owner_id == user.id:
        return True
    shared = await CategoryCRUD.check_user_access(session, category_id, user.id)
    return bool(shared and getattr(shared, 'can_edit', False))

@router.callback_query(F.data.startswith("edit_field_name_"))
async def edit_item_name(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    item_id = int(callback.data.split("edit_field_name_")[1])
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    if not item:
        await callback.answer("❌ Элемент не найден")
        return
    
    if not await _can_edit(session, item.category_id, user):
        await callback.answer("❌ Нет прав на редактирование", show_alert=True)
        return
    await state.update_data(editing_item_id=item_id, editing_field="name")
    
    safe_name = escape_markdown(item.name) if item.name else "—"
    msg = await callback.message.answer(
        f"✏️ Редактирование названия элемента\n"
        f"Текущее название: **{safe_name}**\n\n"
        f"Введите новое название:",
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )
    await add_ephemeral_message(state, msg.message_id)
    await state.set_state(EditItemStates.name)
    await callback.answer()

@router.message(EditItemStates.name)
async def process_edit_name(message: Message, session: AsyncSession, user, state: FSMContext):
    if not message.text or message.text.strip() == "":
        await message.answer("❌ Название не может быть пустым. Попробуйте еще раз:")
        return
    
    data = await state.get_data()
    item_id = data.get('editing_item_id')
    
    new_name_plain = message.text.strip()
    await ItemCRUD.update_item(session, item_id, name=new_name_plain)
    item = await ItemCRUD.get_item_by_id(session, item_id)
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    await send_item_updated_notification(message.bot, category, item, user, "edit")
    
    await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
    await state.clear()
    ok = await message.answer(
        f"✅ Название элемента обновлено на: **{escape_markdown(new_name_plain)}**",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
    schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)

@router.callback_query(F.data.startswith("edit_field_price_"))
async def edit_item_price(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    item_id = int(callback.data.split("edit_field_price_")[1])
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    if not item:
        await callback.answer("❌ Элемент не найден")
        return
    
    if not await _can_edit(session, item.category_id, user):
        await callback.answer("❌ Нет прав на редактирование", show_alert=True)
        return
    await state.update_data(editing_item_id=item_id, editing_field="price")
    
    current_price = f"{item.price} ₽" if item.price else "не указана"
    
    msg = await callback.message.answer(
        f"💸 Редактирование цены элемента\n"
        f"Текущая цена: **{current_price}**\n\n"
        f"Введите новую цену:",
        reply_markup=get_skip_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(EditItemStates.price)
    await callback.answer()
    await add_ephemeral_message(state, msg.message_id)

@router.message(EditItemStates.price)
async def process_edit_price(message: Message, session: AsyncSession, user, state: FSMContext):
    if message.text in SKIP_BUTTONS:
        data = await state.get_data()
        item_id = data.get('editing_item_id')
        
        await ItemCRUD.update_item(session, item_id, price=None)
        # notify
        item = await ItemCRUD.get_item_by_id(session, item_id)
        category = await CategoryCRUD.get_category_by_id(session, item.category_id)
        await send_item_updated_notification(message.bot, category, item, user, "edit")
        
        await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
        await state.clear()
        ok = await message.answer("✅ Цена элемента удалена", reply_markup=get_main_keyboard())
        schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)
        return
    
    price = validate_price(message.text)
    
    if price is not None:
        data = await state.get_data()
        item_id = data.get('editing_item_id')
        
        await ItemCRUD.update_item(session, item_id, price=price)
        # notify
        item = await ItemCRUD.get_item_by_id(session, item_id)
        category = await CategoryCRUD.get_category_by_id(session, item.category_id)
        await send_item_updated_notification(message.bot, category, item, user, "edit")
        
        await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
        await state.clear()
        ok = await message.answer(
            f"✅ Цена элемента обновлена на: **{price} ₽**",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
        schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)
    else:
        await message.answer(
            "❌ Некорректная цена. Введите число или нажмите 'Пропустить':",
            reply_markup=get_skip_keyboard()
        )

@router.callback_query(F.data.startswith("edit_field_date_"))
async def edit_item_date(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    item_id = int(callback.data.split("edit_field_date_")[1])
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    if not item:
        await callback.answer("❌ Элемент не найден")
        return
    
    if not await _can_edit(session, item.category_id, user):
        await callback.answer("❌ Нет прав на редактирование", show_alert=True)
        return
    await state.update_data(editing_item_id=item_id, editing_field="date")
    
    current_date_text = "не указана"
    if item.date_from:
        if item.date_to and item.date_to != item.date_from:
            current_date_text = f"{item.date_from.strftime('%d.%m.%Y')} - {item.date_to.strftime('%d.%m.%Y')}"
        else:
            current_date_text = item.date_from.strftime('%d.%m.%Y')
    elif item.date:  # Backward compatibility with legacy field
        current_date_text = item.date.strftime('%d.%m.%Y')
    
    msg = await callback.message.answer(
        f"📅 Редактирование даты элемента\n"
        f"Текущая дата: **{current_date_text}**\n\n"
        f"Выберите тип даты:",
        reply_markup=get_date_input_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(EditItemStates.date_type)
    await callback.answer()
    await add_ephemeral_message(state, msg.message_id)

@router.callback_query(F.data == "date_single", EditItemStates.date_type)
async def edit_single_date_choice(callback: CallbackQuery, state: FSMContext):
    msg = await callback.message.answer(
        "📅 Введите новую дату в формате ДД.ММ.ГГГГ:",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(EditItemStates.date_single)
    await callback.answer()
    await add_ephemeral_message(state, msg.message_id)

@router.callback_query(F.data == "date_range", EditItemStates.date_type)
async def edit_date_range_choice(callback: CallbackQuery, state: FSMContext):
    msg = await callback.message.answer(
        "📅 Введите дату начала в формате ДД.ММ.ГГГГ:",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(EditItemStates.date_from)
    await callback.answer()
    await add_ephemeral_message(state, msg.message_id)

@router.callback_query(F.data == "skip_date", EditItemStates.date_type)
async def edit_skip_date(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    data = await state.get_data()
    item_id = data.get('editing_item_id')
    
    await ItemCRUD.update_item(session, item_id, date=None, date_from=None, date_to=None)
    # notify
    item = await ItemCRUD.get_item_by_id(session, item_id)
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    await send_item_updated_notification(callback.bot, category, item, user, "edit")
    await cleanup_ephemeral_messages(callback.bot, state, callback.message.chat.id)
    await state.clear()
    ok = await callback.message.answer("✅ Дата элемента удалена", reply_markup=get_main_keyboard())
    schedule_delete_message(callback.bot, callback.message.chat.id, ok.message_id, delay=8)
    await callback.answer()

@router.message(EditItemStates.date_single)
async def process_edit_single_date(message: Message, session: AsyncSession, user, state: FSMContext):
    if message.text in SKIP_BUTTONS:
        data = await state.get_data()
        item_id = data.get('editing_item_id')
        
        await ItemCRUD.update_item(session, item_id, date=None, date_from=None, date_to=None)
        # notify
        item = await ItemCRUD.get_item_by_id(session, item_id)
        category = await CategoryCRUD.get_category_by_id(session, item.category_id)
        await send_item_updated_notification(message.bot, category, item, user, "edit")
        
        await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
        await state.clear()
        ok = await message.answer("✅ Дата элемента удалена", reply_markup=get_main_keyboard())
        schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)
        return
    
    date_obj = parse_date(message.text)
    
    if date_obj:
        data = await state.get_data()
        item_id = data.get('editing_item_id')
        
        await ItemCRUD.update_item(session, item_id, date=date_obj, date_from=date_obj, date_to=None)
        # notify
        item = await ItemCRUD.get_item_by_id(session, item_id)
        category = await CategoryCRUD.get_category_by_id(session, item.category_id)
        await send_item_updated_notification(message.bot, category, item, user, "edit")
        
        await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
        await state.clear()
        ok = await message.answer(
            f"✅ Дата элемента обновлена на: **{date_obj.strftime('%d.%m.%Y')}**",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
        schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)
    else:
        await message.answer(
            "❌ Некорректная дата. Используйте формат ДД.ММ.ГГГГ или нажмите 'Пропустить':",
            reply_markup=get_skip_keyboard()
        )

@router.message(EditItemStates.date_from)
async def process_edit_date_from(message: Message, state: FSMContext):
    date_from = parse_date(message.text)
    
    if date_from:
        await state.update_data(date_from=date_from)
        msg = await message.answer(
            "📅 Введите дату окончания в формате ДД.ММ.ГГГГ:",
            reply_markup=get_back_keyboard()
        )
        await state.set_state(EditItemStates.date_to)
        await add_ephemeral_message(state, msg.message_id)
    else:
        await message.answer("❌ Некорректная дата. Используйте формат ДД.ММ.ГГГГ:")

@router.message(EditItemStates.date_to)
async def process_edit_date_to(message: Message, session: AsyncSession, user, state: FSMContext):
    date_to = parse_date(message.text)
    
    if date_to:
        data = await state.get_data()
        date_from = data.get('date_from')
        item_id = data.get('editing_item_id')
        
        if date_from and date_to >= date_from:
            await ItemCRUD.update_item(
                session, 
                item_id, 
                date=date_from,  # Backward compatibility field
                date_from=date_from, 
                date_to=date_to
            )
            # notify
            item = await ItemCRUD.get_item_by_id(session, item_id)
            category = await CategoryCRUD.get_category_by_id(session, item.category_id)
            await send_item_updated_notification(message.bot, category, item, user, "edit")
            
            await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
            await state.clear()
            ok = await message.answer(
                f"✅ Период элемента обновлен: **{date_from.strftime('%d.%m.%Y')} - {date_to.strftime('%d.%m.%Y')}**",
                reply_markup=get_main_keyboard(),
                parse_mode="Markdown"
            )
            schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)
        else:
            await message.answer("❌ Дата окончания должна быть не раньше даты начала:")
    else:
        await message.answer("❌ Некорректная дата. Используйте формат ДД.ММ.ГГГГ:")

@router.callback_query(F.data.startswith("edit_field_comment_"))
async def edit_item_comment(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    item_id = int(callback.data.split("edit_field_comment_")[1])
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    if not item:
        await callback.answer("❌ Элемент не найден")
        return
    
    if not await _can_edit(session, item.category_id, user):
        await callback.answer("❌ Нет прав на редактирование", show_alert=True)
        return
    await state.update_data(editing_item_id=item_id, editing_field="comment")
    
    current_comment = item.comment if item.comment else "не указан"
    safe_comment = escape_markdown(current_comment)
    
    msg = await callback.message.answer(
        f"💬 Редактирование комментария элемента\n"
        f"Текущий комментарий: **{safe_comment}**\n\n"
        f"Введите новый комментарий:",
        reply_markup=get_skip_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(EditItemStates.comment)
    await callback.answer()
    await add_ephemeral_message(state, msg.message_id)

@router.message(EditItemStates.comment)
async def process_edit_comment(message: Message, session: AsyncSession, user, state: FSMContext):
    if message.text in SKIP_BUTTONS:
        data = await state.get_data()
        item_id = data.get('editing_item_id')
        
        await ItemCRUD.update_item(session, item_id, comment=None)
        # notify
        item = await ItemCRUD.get_item_by_id(session, item_id)
        category = await CategoryCRUD.get_category_by_id(session, item.category_id)
        await send_item_updated_notification(message.bot, category, item, user, "edit")
        
        await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
        await state.clear()
        ok = await message.answer("✅ Комментарий элемента удален", reply_markup=get_main_keyboard())
        schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)
        return
    
    data = await state.get_data()
    item_id = data.get('editing_item_id')
    
    await ItemCRUD.update_item(session, item_id, comment=message.text.strip())
    # notify
    item = await ItemCRUD.get_item_by_id(session, item_id)
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    await send_item_updated_notification(message.bot, category, item, user, "edit")
    
    await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
    await state.clear()
    ok = await message.answer("✅ Комментарий элемента обновлен", reply_markup=get_main_keyboard())
    schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)

@router.callback_query(F.data.startswith("edit_field_url_"))
async def edit_item_url(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    item_id = int(callback.data.split("edit_field_url_")[1])
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    if not item:
        await callback.answer("❌ Элемент не найден")
        return
    
    if not await _can_edit(session, item.category_id, user):
        await callback.answer("❌ Нет прав на редактирование", show_alert=True)
        return
    await state.update_data(editing_item_id=item_id, editing_field="url")
    
    current_url = item.url if item.url else "не указана"
    safe_url = escape_markdown(current_url)
    
    msg = await callback.message.answer(
        f"🔗 Редактирование ссылки элемента\n"
        f"Текущая ссылка: **{safe_url}**\n\n"
        f"Введите новую ссылку:",
        reply_markup=get_skip_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(EditItemStates.url)
    await callback.answer()
    await add_ephemeral_message(state, msg.message_id)

@router.message(EditItemStates.url)
async def process_edit_url(message: Message, session: AsyncSession, user, state: FSMContext):
    if message.text in SKIP_BUTTONS:
        data = await state.get_data()
        item_id = data.get('editing_item_id')
        
        await ItemCRUD.update_item(session, item_id, url=None)
        # notify
        item = await ItemCRUD.get_item_by_id(session, item_id)
        category = await CategoryCRUD.get_category_by_id(session, item.category_id)
        await send_item_updated_notification(message.bot, category, item, user, "edit")
        
        await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
        await state.clear()
        ok = await message.answer("✅ Ссылка элемента удалена", reply_markup=get_main_keyboard())
        schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)
        return
    
    data = await state.get_data()
    item_id = data.get('editing_item_id')
    
    await ItemCRUD.update_item(session, item_id, url=message.text.strip())
    # notify
    item = await ItemCRUD.get_item_by_id(session, item_id)
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    await send_item_updated_notification(message.bot, category, item, user, "edit")
    
    await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
    await state.clear()
    ok = await message.answer("✅ Ссылка элемента обновлена", reply_markup=get_main_keyboard())
    schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)

@router.callback_query(F.data.startswith("edit_field_photo_"))
async def edit_item_photo(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    item_id = int(callback.data.split("edit_field_photo_")[1])
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    if not item:
        await callback.answer("❌ Элемент не найден")
        return
    
    if not await _can_edit(session, item.category_id, user):
        await callback.answer("❌ Нет прав на редактирование", show_alert=True)
        return
    await state.update_data(editing_item_id=item_id, editing_field="photo")
    
    photo_status = "есть" if item.photo_file_id else "нет"
    
    msg = await callback.message.answer(
        f"📷 Редактирование фото элемента\n"
        f"Текущее фото: **{photo_status}**\n\n"
        f"Отправьте новое фото или нажмите 'Пропустить' для удаления:",
        reply_markup=get_skip_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(EditItemStates.photo)
    await callback.answer()
    await add_ephemeral_message(state, msg.message_id)

@router.message(EditItemStates.photo, F.photo.is_not(None))
async def process_edit_photo(message: Message, session: AsyncSession, user, state: FSMContext):
    photo = message.photo[-1]
    
    data = await state.get_data()
    item_id = data.get('editing_item_id')
    
    await ItemCRUD.update_item(session, item_id, photo_file_id=photo.file_id)
    # notify
    item = await ItemCRUD.get_item_by_id(session, item_id)
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    await send_item_updated_notification(message.bot, category, item, user, "edit")
    
    await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
    await state.clear()
    ok = await message.answer("✅ Фото элемента обновлено", reply_markup=get_main_keyboard())
    schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)

@router.message(EditItemStates.photo)
async def process_remove_photo(message: Message, session: AsyncSession, user, state: FSMContext):
    if message.text in SKIP_BUTTONS:
        data = await state.get_data()
        item_id = data.get('editing_item_id')
        
        await ItemCRUD.update_item(session, item_id, photo_file_id=None)
        # notify
        item = await ItemCRUD.get_item_by_id(session, item_id)
        category = await CategoryCRUD.get_category_by_id(session, item.category_id)
        await send_item_updated_notification(message.bot, category, item, user, "edit")
        
        await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
        await state.clear()
        ok = await message.answer("✅ Фото элемента удалено", reply_markup=get_main_keyboard())
        schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)
    else:
        msg = await message.answer(
            "📷 Отправьте фото или нажмите 'Пропустить' для удаления:",
            reply_markup=get_skip_keyboard()
        )
        await add_ephemeral_message(state, msg.message_id)

@router.callback_query(F.data.startswith("edit_field_tags_"))
async def edit_item_tags(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    item_id = int(callback.data.split("edit_field_tags_")[1])
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    if not item:
        await callback.answer("❌ Элемент не найден")
        return
    
    if not await _can_edit(session, item.category_id, user):
        await callback.answer("❌ Нет прав на редактирование", show_alert=True)
        return
    await state.update_data(editing_item_id=item_id, editing_field="tags", selected_tags=[])
    
    current_tags = []
    if item.tags:
        try:
            current_tags = json.loads(item.tags) if isinstance(item.tags, str) else item.tags
        except (json.JSONDecodeError, TypeError):
            current_tags = []
    
    current_tags_text = ", ".join(f"
    
    popular_tags = await TagCRUD.get_popular_tags(session, user.id, limit=20)
    
    msg = await callback.message.answer(
        f"🏷 Редактирование тегов элемента\n"
        f"Текущие теги: **{current_tags_text}**\n\n"
        f"Выберите теги или введите новые через запятую:",
        reply_markup=get_tags_keyboard(popular_tags),
        parse_mode="Markdown"
    )
    await state.set_state(EditItemStates.tags)
    await callback.answer()
    await add_ephemeral_message(state, msg.message_id)

@router.callback_query(F.data.startswith("tag_"), EditItemStates.tags)
async def process_edit_tag_selection(callback: CallbackQuery, state: FSMContext):
    tag_name = callback.data.split("tag_", 1)[1]
    
    data = await state.get_data()
    current_tags = data.get('selected_tags', [])
    
    if tag_name not in current_tags:
        current_tags.append(tag_name)
        await state.update_data(selected_tags=current_tags)
        await callback.answer(f"✅ Тег '{tag_name}' добавлен")
    else:
        await callback.answer(f"⚠️ Тег '{tag_name}' уже выбран")

@router.callback_query(F.data == "add_new_tag", EditItemStates.tags)
async def edit_add_new_tag_start(callback: CallbackQuery, state: FSMContext):
    msg = await callback.message.answer(
        "✏️ Введите название нового тега:",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(EditItemStates.add_new_tag)
    await add_ephemeral_message(state, msg.message_id)

@router.message(EditItemStates.add_new_tag)
async def process_edit_new_tag(message: Message, session: AsyncSession, user, state: FSMContext):
    if message.text in BACK_BUTTONS:
        popular_tags = await TagCRUD.get_popular_tags(session, user.id, limit=20)
        msg2 = await message.answer(
            "🏷 Выберите теги или введите новые через запятую:",
            reply_markup=get_tags_keyboard(popular_tags)
        )
        await state.set_state(EditItemStates.tags)
        await add_ephemeral_message(state, msg2.message_id)
        return
        
    if not message.text or message.text.strip() == "":
        await message.answer("❌ Название тега не может быть пустым. Попробуйте еще раз:")
        return
    
    tag_name = message.text.strip().lower()
    
    data = await state.get_data()
    current_tags = data.get('selected_tags', [])
    user_id = user.id
    if tag_name not in current_tags:
        current_tags.append(tag_name)
        await state.update_data(selected_tags=current_tags)
        if user_id is not None:
            await TagCRUD.get_or_create_tag(session, tag_name, user_id)
    
    popular_tags = await TagCRUD.get_popular_tags(session, user_id, limit=20)
    
    msg3 = await message.answer(
        "🏷 Выберите теги или введите новые через запятую:",
        reply_markup=get_tags_keyboard(popular_tags)
    )
    await state.set_state(EditItemStates.tags)
    await add_ephemeral_message(state, msg3.message_id)

@router.callback_query(F.data == "skip_tags", EditItemStates.tags)
async def finish_edit_tags(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    data = await state.get_data()
    item_id = data.get('editing_item_id')
    selected_tags = data.get('selected_tags', [])
    
    await ItemCRUD.update_item(session, item_id, tags=selected_tags)
    # notify
    item = await ItemCRUD.get_item_by_id(session, item_id)
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    await send_item_updated_notification(callback.bot, category, item, user, "edit")
    
    await cleanup_ephemeral_messages(callback.bot, state, callback.message.chat.id)
    await state.clear()
    tags_text = ", ".join(f"
    ok = await callback.message.answer(
        f"✅ Теги элемента обновлены: **{tags_text}**",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
    schedule_delete_message(callback.bot, callback.message.chat.id, ok.message_id, delay=8)
    await callback.answer()

@router.message(EditItemStates.tags)
async def process_edit_manual_tags(message: Message, session: AsyncSession, user, state: FSMContext):
    if message.text in SKIP_BUTTONS:
        await finish_edit_tags_manual(message, session, state)
        return
    
    tags = parse_tags(message.text)
    
    if tags:
        data = await state.get_data()
        current_tags = data.get('selected_tags', [])
        user_id = user.id
        for tag in tags:
            if tag not in current_tags:
                current_tags.append(tag)
                await TagCRUD.get_or_create_tag(session, tag, user_id)
        
        await state.update_data(selected_tags=current_tags)
        
        tags_text = ", ".join(f"#{tag}" for tag in current_tags)
        
        data = await state.get_data()
        item_id = data.get('editing_item_id')
        
        await ItemCRUD.update_item(session, item_id, tags=current_tags)
        # notify
        item = await ItemCRUD.get_item_by_id(session, item_id)
        category = await CategoryCRUD.get_category_by_id(session, item.category_id)
        await send_item_updated_notification(message.bot, category, item, user, "edit")
        
        await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
        await state.clear()
        ok = await message.answer(
            f"✅ Теги элемента обновлены: **{tags_text}**",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
        schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)
    else:
        await message.answer("❌ Не удалось распознать теги. Попробуйте еще раз или нажмите 'Пропустить':")

async def finish_edit_tags_manual(message: Message, session: AsyncSession, user, state: FSMContext):
    data = await state.get_data()
    item_id = data.get('editing_item_id')
    selected_tags = data.get('selected_tags', [])
    
    await ItemCRUD.update_item(session, item_id, tags=selected_tags)
    # notify
    item = await ItemCRUD.get_item_by_id(session, item_id)
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    await send_item_updated_notification(message.bot, category, item, user, "edit")
    
    await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
    await state.clear()
    tags_text = ", ".join(f"
    ok = await message.answer(
        f"✅ Теги элемента обновлены: **{tags_text}**",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
    schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)

@router.callback_query(F.data.startswith("edit_field_location_"))
async def edit_item_location(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    item_id = int(callback.data.split("edit_field_location_")[1])
    
    item = await ItemCRUD.get_item_by_id(session, item_id)
    if not item:
        await callback.answer("❌ Элемент не найден")
        return
    
    if not await _can_edit(session, item.category_id, user):
        await callback.answer("❌ Нет прав на редактирование", show_alert=True)
        return
    await state.update_data(editing_item_id=item_id, editing_field="location")
    
    current_location = f"{item.location_value}" if item.location_value else "не указано"
    if item.location_type and current_location != "не указано":
        current_location = f"{item.location_type}: {current_location}"
    safe_current_location = escape_markdown(current_location)
    
    msg = await callback.message.answer(
        f"📍 Редактирование местоположения элемента\n"
        f"Текущее местоположение: **{safe_current_location}**\n\n"
        f"Выберите тип местоположения:",
        reply_markup=get_location_type_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(EditItemStates.location_type)
    await callback.answer()
    await add_ephemeral_message(state, msg.message_id)

@router.callback_query(F.data.startswith("location_type_"), EditItemStates.location_type)
async def process_edit_location_type(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    location_type_map = {
        "location_type_city": "в городе",
        "location_type_outside": "за городом", 
        "location_type_district": "по району"
    }
    
    location_type = location_type_map.get(callback.data)
    
    if location_type:
        await state.update_data(location_type=location_type)
        
        locations = await LocationCRUD.get_locations_by_type(session, location_type, user.id)
        
        msg2 = await callback.message.answer(
            f"📍 Выберите {location_type} или добавьте новое:",
            reply_markup=get_locations_keyboard(locations, location_type)
        )
        await state.set_state(EditItemStates.location_value)
        await add_ephemeral_message(state, msg2.message_id)
    
    await callback.answer()

@router.callback_query(F.data == "skip_location", EditItemStates.location_type)
async def skip_edit_location(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    data = await state.get_data()
    item_id = data.get('editing_item_id')
    
    await ItemCRUD.update_item(session, item_id, location_type=None, location_value=None)
    # notify
    item = await ItemCRUD.get_item_by_id(session, item_id)
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    await send_item_updated_notification(callback.bot, category, item, user, "edit")
    await cleanup_ephemeral_messages(callback.bot, state, callback.message.chat.id)
    await state.clear()
    ok = await callback.message.answer("✅ Местоположение элемента удалено", reply_markup=get_main_keyboard())
    schedule_delete_message(callback.bot, callback.message.chat.id, ok.message_id, delay=8)
    await callback.answer()

@router.callback_query(F.data.startswith("location_"), EditItemStates.location_value)
async def process_edit_location_selection(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    parts = callback.data.split("_", 2)
    
    if len(parts) >= 3 and parts[1] != "add":
        location_value = "_".join(parts[2:])
        
        data = await state.get_data()
        item_id = data.get('editing_item_id')
        location_type = data.get('location_type')
        
        await ItemCRUD.update_item(
            session, 
            item_id, 
            location_type=location_type,
            location_value=location_value
        )
        await LocationCRUD.get_or_create_location(session, location_type, location_value, user.id)
        # notify
        item = await ItemCRUD.get_item_by_id(session, item_id)
        category = await CategoryCRUD.get_category_by_id(session, item.category_id)
        await send_item_updated_notification(callback.bot, category, item, user, "edit")
    await cleanup_ephemeral_messages(callback.bot, state, callback.message.chat.id)
    await state.clear()
    safe_location = escape_markdown(f"{location_type}: {location_value}")
    ok = await callback.message.answer(
        f"✅ Местоположение элемента обновлено: **{safe_location}**",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
    schedule_delete_message(callback.bot, callback.message.chat.id, ok.message_id, delay=8)
    
    await callback.answer()

@router.callback_query(F.data.startswith("add_location_"), EditItemStates.location_value)
async def edit_add_new_location_start(callback: CallbackQuery, state: FSMContext):
    location_type = callback.data.split("add_location_")[1]
    await state.update_data(adding_location_type=location_type)
    
    msg = await callback.message.answer(
        f"✏️ Введите название для типа '{location_type}':",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(EditItemStates.add_new_location)
    await add_ephemeral_message(state, msg.message_id)

@router.message(EditItemStates.add_new_location)
async def process_edit_new_location(message: Message, session: AsyncSession, user, state: FSMContext):
    if not message.text or message.text.strip() == "":
        await message.answer("❌ Название местоположения не может быть пустым. Попробуйте еще раз:")
        return
    
    data = await state.get_data()
    location_type = data.get('location_type')
    location_value = message.text.strip()
    item_id = data.get('editing_item_id')
    
    await ItemCRUD.update_item(
        session, 
        item_id, 
        location_type=location_type,
        location_value=location_value
    )
    await LocationCRUD.get_or_create_location(session, location_type, location_value, user.id)
    # notify
    item = await ItemCRUD.get_item_by_id(session, item_id)
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    await send_item_updated_notification(message.bot, category, item, user, "edit")
    await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
    await state.clear()
    safe_location = escape_markdown(f"{location_type}: {location_value}")
    ok = await message.answer(
        f"✅ Местоположение элемента обновлено: **{safe_location}**",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
    schedule_delete_message(message.bot, message.chat.id, ok.message_id, delay=8)

@router.callback_query(F.data == "skip_location", EditItemStates.location_value)
async def skip_edit_location_value(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    data = await state.get_data()
    item_id = data.get('editing_item_id')
    
    await ItemCRUD.update_item(session, item_id, location_type=None, location_value=None)
    # notify
    item = await ItemCRUD.get_item_by_id(session, item_id)
    category = await CategoryCRUD.get_category_by_id(session, item.category_id)
    await send_item_updated_notification(callback.bot, category, item, user, "edit")
    await cleanup_ephemeral_messages(callback.bot, state, callback.message.chat.id)
    await state.clear()
    ok = await callback.message.answer("✅ Местоположение элемента удалено", reply_markup=get_main_keyboard())
    schedule_delete_message(callback.bot, callback.message.chat.id, ok.message_id, delay=8)
    await callback.answer()
