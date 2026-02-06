from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import InlineKeyboardBuilder
import json
import logging

from database.crud import CategoryCRUD, ItemCRUD, TagCRUD, LocationCRUD
from states import AddItemStates
from keyboards import (
    get_main_keyboard, get_back_keyboard, get_skip_keyboard, get_skip_inline_keyboard,
    get_categories_keyboard, get_tags_keyboard, get_location_type_keyboard,
    get_locations_keyboard, get_product_type_keyboard, get_date_input_keyboard
)
from utils.helpers import (
    parse_tags,
    validate_price,
    parse_date,
    format_item_card,
    escape_markdown,
    get_location_label,
)
from utils.notifications import send_item_added_notification
from config import MAX_ITEMS_PER_USER
from utils.cleanup import add_ephemeral_message, cleanup_ephemeral_messages
from utils.localization import get_value_variants, get_user_language, translate_text, DEFAULT_LANGUAGE

router = Router()
logger = logging.getLogger(__name__)

BACK_BUTTONS = get_value_variants("buttons.back")
SKIP_BUTTONS = get_value_variants("buttons.skip")

async def _language_from_state(state: FSMContext) -> str:
    data = await state.get_data()
    stored_user = data.get("user")
    return get_user_language(stored_user) if stored_user else DEFAULT_LANGUAGE

@router.message(F.text.in_(get_value_variants("buttons.add_item")))
async def add_item_start(message: Message, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    user_items = await ItemCRUD.get_user_items(session, user.id)
    
    if len(user_items) >= MAX_ITEMS_PER_USER:
        await message.answer(
            translate_text(
                language,
                f"❌ You reached the item limit ({MAX_ITEMS_PER_USER}). Remove existing items before adding new ones.",
                f"❌ Достигнут лимит элементов ({MAX_ITEMS_PER_USER}). Удалите некоторые элементы перед добавлением новых."
            ),
            reply_markup=get_main_keyboard(language=language)
        )
        return
    
    editable_categories = await CategoryCRUD.get_user_editable_categories(session, user.id)
    
    if not editable_categories:
        await message.answer(
            translate_text(
                language,
                "❌ You have no categories where items can be added.\nCreate your own category or ask the owner for edit permissions.",
                "❌ У вас нет категорий, где можно добавлять элементы.\nСоздайте свою категорию или попросите владельца поделиться правами на редактирование."
            ),
            reply_markup=get_main_keyboard(language=language)
        )
        return
    
    await state.update_data(user=user)
    
    msg = await message.answer(
        translate_text(language, "✏️ Enter the item name:", "✏️ Введите название элемента:"),
        reply_markup=get_back_keyboard(language=language)
    )
    
    await state.update_data(last_bot_message=msg.message_id)
    await add_ephemeral_message(state, msg.message_id)
    await state.set_state(AddItemStates.name)

@router.message(AddItemStates.name)
async def process_item_name(message: Message, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    if message.text in BACK_BUTTONS:
        await state.clear()
        await message.answer(
            translate_text(language, "Main menu:", "Главное меню:"),
            reply_markup=get_main_keyboard(language=language)
        )
        return
    
    if not message.text or message.text.strip() == "":
        await message.answer(
            translate_text(language, "❌ Item name cannot be empty. Try again:", "❌ Название элемента не может быть пустым. Попробуйте еще раз:")
        )
        return
    
    name = message.text.strip()
    await state.update_data(name=name)
    safe_name = escape_markdown(name)
    
    categories = await CategoryCRUD.get_user_editable_categories(session, user.id)
    if not categories:
        await state.clear()
        await message.answer(
            translate_text(language, "❌ No categories available to add this item. Try later.", "❌ Нет категорий, куда можно добавить элемент. Попробуйте позже."),
            reply_markup=get_main_keyboard(language=language)
        )
        return
    
    data = await state.get_data()
    last_message_id = data.get('last_bot_message')
    if last_message_id:
        try:
            await message.bot.delete_message(message.chat.id, last_message_id)
        except:
            pass
    
    msg = await message.answer(
        translate_text(
            language,
            f"🎯 Item: **{safe_name}**\n\n📁 Choose a category:",
            f"🎯 Элемент: **{safe_name}**\n\n📁 Выберите категорию:"
        ),
        reply_markup=get_categories_keyboard(categories),
        parse_mode="Markdown"
    )
    
    await state.update_data(last_bot_message=msg.message_id)
    await add_ephemeral_message(state, msg.message_id)
    await state.set_state(AddItemStates.category)
    
    try:
        await message.delete()
    except:
        pass

@router.callback_query(F.data.startswith("category_"), AddItemStates.category)
async def process_category_selection(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    category_id = int(callback.data.split("category_")[1])

    category = await CategoryCRUD.get_category_by_id(session, category_id)
    if not category:
        await callback.answer(
            translate_text(language, "❌ Category not found", "❌ Категория не найдена"),
            show_alert=True
        )
        return

    has_access = category.owner_id == user.id
    if not has_access:
        access = await CategoryCRUD.check_user_access(session, category_id, user.id)
        has_access = bool(access and getattr(access, 'can_edit', False))

    if not has_access:
        await callback.answer(
            translate_text(language, "❌ You don't have permission to add items to this category", "❌ У вас нет прав на добавление в эту категорию"),
            show_alert=True
        )
        return

    await state.update_data(category_id=category_id)
    
    data = await state.get_data()
    name = data.get('name')
    safe_name = escape_markdown(name) if name else "—"
    safe_name = escape_markdown(name) if name else "—"
    
    kb = InlineKeyboardBuilder()
    kb.button(
        text=translate_text(language, "🏷 Tags", "🏷 Теги"),
        callback_data="add_tags"
    )
    kb.button(
        text=translate_text(language, "💸 Price", "💸 Цена"),
        callback_data="add_price"
    )
    kb.button(
        text=translate_text(language, "📍 Location", "📍 Место"),
        callback_data="add_location"
    )
    kb.button(
        text=translate_text(language, "📅 Date", "📅 Дата"),
        callback_data="add_date"
    )
    kb.button(
        text=translate_text(language, "🔗 Link", "🔗 Ссылка"),
        callback_data="add_url"
    )
    kb.button(
        text=translate_text(language, "💬 Comment", "💬 Комментарий"),
        callback_data="add_comment"
    )
    kb.button(
        text=translate_text(language, "📷 Photo", "📷 Фото"),
        callback_data="add_photo"
    )
    kb.button(
        text=translate_text(language, "✅ Finish", "✅ Завершить"),
        callback_data="finish_item"
    )
    kb.adjust(2)
    
    try:
        await callback.message.delete()
    except:
        pass
    
    msg = await callback.message.answer(
        translate_text(
            language,
            f"🎯 New item\nName: **{safe_name}**\n\nChoose what you want to add:",
            f"🎯 Новый элемент\nНазвание: **{safe_name}**\n\nВыберите, что хотите добавить:"
        ),
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )
    
    await state.update_data(last_bot_message=msg.message_id)
    await add_ephemeral_message(state, msg.message_id)
    await state.set_state(AddItemStates.select_field)

@router.callback_query(F.data == "add_tags", AddItemStates.select_field)
async def add_tags_handler(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    data = await state.get_data()
    
    popular_tags = await TagCRUD.get_popular_tags(session, user.id, limit=20)
    
    selected_text = translate_text(language, "Choose tags:\n\n", "Выберите теги:\n\n")
    current_tags = data.get('selected_tags') or []
    if current_tags:
        formatted_tags = ", ".join(f"#{escape_markdown(t)}" for t in current_tags)
        selected_text = translate_text(language, f"Selected tags: {formatted_tags}\n\n", f"Выбранные теги: {formatted_tags}\n\n")
    
    try:
        await callback.message.delete()
    except:
        pass
    
    msg = await callback.message.answer(
        selected_text + translate_text(language, "🏷 Choose tags or type new ones separated by commas:", "🏷 Выберите теги или введите новые через запятую:"),
        reply_markup=get_tags_keyboard(popular_tags, selected_tags=current_tags, language=language)
    )
    await state.update_data(last_bot_message=msg.message_id)
    await add_ephemeral_message(state, msg.message_id)
    await state.set_state(AddItemStates.tags)

@router.callback_query(F.data.startswith("tag_"), AddItemStates.tags)
async def process_tag_selection(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    tag_name = callback.data.split("tag_", 1)[1]
    data = await state.get_data()
    current_tags = data.get('selected_tags') or []
    
    if tag_name in current_tags:
        current_tags.remove(tag_name)
        await callback.answer(
            translate_text(language, f"❌ Tag '{tag_name}' removed", f"❌ Тег '{tag_name}' удален")
        )
    else:
        current_tags.append(tag_name)
        await TagCRUD.get_or_create_tag(session, tag_name, user.id)
        await callback.answer(
            translate_text(language, f"✅ Tag '{tag_name}' added", f"✅ Тег '{tag_name}' добавлен")
        )
    
    await state.update_data(selected_tags=current_tags)
    
    popular_tags = await TagCRUD.get_popular_tags(session, user.id, limit=20)
    selected_text = ""
    if current_tags:
        selected_text = translate_text(
            language,
            "Selected tags: ",
            "Выбранные теги: "
        ) + ", ".join(f"#{t}" for t in current_tags) + "\n\n"
    
    await callback.message.edit_text(
        selected_text + translate_text(language, "🏷 Choose tags or type new ones separated by commas:", "🏷 Выберите теги или введите новые через запятую:"),
        reply_markup=get_tags_keyboard(popular_tags, selected_tags=current_tags, language=language),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "add_new_tag", AddItemStates.tags)
async def add_new_tag_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = data.get("user")
    language = get_user_language(user) if user else DEFAULT_LANGUAGE
    msg = await callback.message.answer(
        translate_text(language, "✏️ Enter a new tag name:", "✏️ Введите название нового тега:"),
        reply_markup=get_back_keyboard(language=language)
    )
    await state.set_state(AddItemStates.add_new_tag)
    await add_ephemeral_message(state, msg.message_id)

@router.message(AddItemStates.add_new_tag)
async def process_new_tag(message: Message, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    if message.text in BACK_BUTTONS:
        data = await state.get_data()
        
        popular_tags = await TagCRUD.get_popular_tags(session, user.id, limit=20)
        
        selected_text = translate_text(language, "Choose tags:\n\n", "Выберите теги:\n\n")
        current_tags = data.get('selected_tags') or []
        if current_tags:
            selected_text = translate_text(language, "Selected tags: ", "Выбранные теги: ") + ", ".join(f"#{t}" for t in current_tags) + "\n\n"
        
        msg2 = await message.answer(
            selected_text + translate_text(language, "🏷 Choose tags or type new ones separated by commas:", "🏷 Выберите теги или введите новые через запятую:"),
            reply_markup=get_tags_keyboard(popular_tags, selected_tags=current_tags, language=language)
        )
        await state.set_state(AddItemStates.tags)
        await add_ephemeral_message(state, msg2.message_id)
        return

    if not message.text or message.text.strip() == "":
        await message.answer(
            translate_text(language, "❌ Tag name cannot be empty. Try again:", "❌ Название тега не может быть пустым. Попробуйте еще раз:")
        )
        return

    tag_name = message.text.strip().lower()
    data = await state.get_data()
    current_tags = data.get('selected_tags') or []
    if tag_name not in current_tags:
        current_tags.append(tag_name)
        await state.update_data(selected_tags=current_tags)
        await TagCRUD.get_or_create_tag(session, tag_name, user.id)
        
        popular_tags = await TagCRUD.get_popular_tags(session, user.id, limit=20)
        
        selected_text = ""
        if current_tags:
            selected_text = translate_text(language, "Selected tags: ", "Выбранные теги: ") + ", ".join(f"#{t}" for t in current_tags) + "\n\n"
            
        msg3 = await message.answer(
            selected_text + translate_text(language, "🏷 Choose tags or type new ones separated by commas:", "🏷 Выберите теги или введите новые через запятую:"),
            reply_markup=get_tags_keyboard(popular_tags, selected_tags=current_tags, language=language)
        )
        await state.set_state(AddItemStates.tags)
        await add_ephemeral_message(state, msg3.message_id)
    else:
        await message.answer(
            translate_text(language, "⚠️ This tag is already selected", "⚠️ Этот тег уже выбран")
        )

@router.callback_query(F.data == "skip_tags", AddItemStates.tags)
async def skip_tags(callback: CallbackQuery, state: FSMContext):
    await return_to_field_selection(callback, state)

@router.message(AddItemStates.tags)
async def process_manual_tags(message: Message, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    if message.text in SKIP_BUTTONS:
        await return_to_field_selection(message, state)
        return

    tags = parse_tags(message.text)
    if tags:
        data = await state.get_data()
        current_tags = data.get('selected_tags') or []
        for tag in tags:
            if tag not in current_tags:
                current_tags.append(tag)
                await TagCRUD.get_or_create_tag(session, tag, user.id)
        await state.update_data(selected_tags=current_tags)
        await message.answer(
            translate_text(language, f"✅ Added tags: {', '.join(tags)}", f"✅ Добавлены теги: {', '.join(tags)}")
        )
        await return_to_field_selection(message, state)
    else:
        await message.answer(
            translate_text(language, "❌ Unable to recognize tags. Try again or press 'Skip'.", "❌ Не удалось распознать теги. Попробуйте еще раз или нажмите 'Пропустить':")
        )

@router.callback_query(F.data == "add_price", AddItemStates.select_field)
async def add_price_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = data.get("user")
    language = get_user_language(user) if user else DEFAULT_LANGUAGE
    try:
        await callback.message.delete()
    except:
        pass
    
    msg = await callback.message.answer(
        translate_text(language, "💸 Enter the price (e.g., 1500) or press 'Skip':", "💸 Введите стоимость (например: 1500) или нажмите 'Пропустить':"),
        reply_markup=get_skip_keyboard(language=language)
    )
    await state.update_data(last_bot_message=msg.message_id)
    await add_ephemeral_message(state, msg.message_id)
    await state.set_state(AddItemStates.price)

@router.message(AddItemStates.price)
async def process_price(message: Message, state: FSMContext):
    data = await state.get_data()
    user = data.get("user")
    language = get_user_language(user) if user else DEFAULT_LANGUAGE
    if message.text in SKIP_BUTTONS:
        await return_to_field_selection(message, state)
        return
    
    price = validate_price(message.text)
    
    if price is not None:
        await state.update_data(price=price)
        await message.answer(
            translate_text(language, f"✅ Price set: {price}", f"✅ Цена установлена: {price}")
        )
        await return_to_field_selection(message, state)
    else:
        await message.answer(
            translate_text(language, "❌ Invalid price. Enter a number (e.g., 1500) or press 'Skip':", "❌ Некорректная цена. Введите число (например: 1500) или нажмите 'Пропустить':"),
            reply_markup=get_skip_keyboard(language=language)
        )

@router.callback_query(F.data == "add_location", AddItemStates.select_field)
async def add_location_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    state_user = data.get("user")
    language = get_user_language(state_user) if state_user else DEFAULT_LANGUAGE
    try:
        await callback.message.delete()
    except:
        pass
    
    msg = await callback.message.answer(
        translate_text(language, "📍 Choose a location type:", "📍 Выберите тип местоположения:"),
        reply_markup=get_location_type_keyboard(language=language)
    )
    await state.update_data(last_bot_message=msg.message_id)
    await add_ephemeral_message(state, msg.message_id)
    await state.set_state(AddItemStates.location_type)

@router.callback_query(F.data.startswith("location_type_"), AddItemStates.location_type)
async def process_location_type(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    location_type_map = {
        "location_type_city": "в городе",
        "location_type_outside": "за городом", 
        "location_type_district": "по району"
    }
    
    location_type = location_type_map.get(callback.data)
    
    if location_type:
        await state.update_data(location_type=location_type)
        locations = await LocationCRUD.get_locations_by_type(session, location_type, user.id)
        display_name_en = get_location_label(location_type, "en")
        display_name_ru = get_location_label(location_type, "ru")
        await callback.message.edit_text(
            translate_text(
                language,
                f"📍 Choose {display_name_en} or add a new one:",
                f"📍 Выберите {display_name_ru} или добавьте новое:"
            ),
            reply_markup=get_locations_keyboard(locations, location_type, language=language)
        )
        await state.set_state(AddItemStates.location_value)
    
    await callback.answer()

@router.callback_query(F.data == "skip_location", AddItemStates.location_type)
async def skip_location_from_type(callback: CallbackQuery, state: FSMContext):
    await return_to_field_selection(callback, state)

@router.callback_query(F.data.startswith("location_"), AddItemStates.location_value)
async def process_location_selection(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    parts = callback.data.split("_", 2)
    
    if len(parts) >= 3 and parts[1] != "add":
        location_type_key = parts[1]
        location_value = "_".join(parts[2:])
        
        location_type_map = {
            "city": "в городе",
            "outside": "за городом",
            "district": "по району"
        }
        
        location_type = location_type_map.get(location_type_key, location_type_key)
        
        await state.update_data(location_value=location_value)
        await LocationCRUD.get_or_create_location(session, location_type, location_value, user.id)
        await callback.message.answer(
            translate_text(language, f"✅ Location set: {location_value}", f"✅ Местоположение установлено: {location_value}")
        )
        await return_to_field_selection(callback, state)
    
    await callback.answer()

@router.callback_query(F.data.startswith("add_location_"), AddItemStates.location_value)
async def add_new_location_start(callback: CallbackQuery, user, state: FSMContext):
    language = get_user_language(user)
    location_type = callback.data.split("add_location_")[1]
    await state.update_data(adding_location_type=location_type)
    
    label_en = get_location_label(location_type, "en")
    label_ru = get_location_label(location_type, "ru")
    await callback.message.answer(
        translate_text(language, f"✏️ Enter a name for '{label_en}':", f"✏️ Введите название для типа '{label_ru}':"),
        reply_markup=get_back_keyboard(language=language)
    )
    await state.set_state(AddItemStates.add_new_location)

@router.message(AddItemStates.add_new_location)
async def process_new_location(message: Message, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    if message.text in BACK_BUTTONS:
        data = await state.get_data()
        location_type = data.get('location_type')
        locations = await LocationCRUD.get_locations_by_type(session, location_type, user.id)
        label_en = get_location_label(location_type, "en")
        label_ru = get_location_label(location_type, "ru")
        await message.answer(
            translate_text(
                language,
                f"📍 Choose {label_en} or add a new one:",
                f"📍 Выберите {label_ru} или добавьте новое:"
            ),
            reply_markup=get_locations_keyboard(locations, location_type, language=language)
        )
        await state.set_state(AddItemStates.location_value)
        return
        
    if not message.text or message.text.strip() == "":
        await message.answer(
            translate_text(language, "❌ Location name cannot be empty. Try again:", "❌ Название местоположения не может быть пустым. Попробуйте еще раз:")
        )
        return
    
    data = await state.get_data()
    location_type = data.get('location_type')
    location_value = message.text.strip()
    
    await state.update_data(location_value=location_value)
    await LocationCRUD.get_or_create_location(session, location_type, location_value, user.id)
    await message.answer(
        translate_text(language, f"✅ Location set: {location_value}", f"✅ Местоположение установлено: {location_value}")
    )
    await return_to_field_selection(message, state)

@router.callback_query(F.data == "skip_location", AddItemStates.location_value)
async def skip_location_from_value(callback: CallbackQuery, state: FSMContext):
    await return_to_field_selection(callback, state)

@router.callback_query(F.data == "add_date", AddItemStates.select_field)
async def add_date_handler(callback: CallbackQuery, state: FSMContext):
    language = await _language_from_state(state)
    try:
        await callback.message.delete()
    except:
        pass
    
    msg = await callback.message.answer(
        translate_text(language, "📅 Choose a date type:", "📅 Выберите тип даты:"),
        reply_markup=get_date_input_keyboard(language=language)
    )
    await state.update_data(last_bot_message=msg.message_id)
    await state.set_state(AddItemStates.date_type)

@router.callback_query(F.data == "date_single", AddItemStates.date_type)
async def date_single_handler(callback: CallbackQuery, state: FSMContext):
    language = await _language_from_state(state)
    await callback.message.edit_text(
        translate_text(language, "📅 Enter the date in DD.MM.YYYY format or press 'Skip':", "📅 Введите дату в формате ДД.ММ.ГГГГ или нажмите 'Пропустить':"),
        reply_markup=get_skip_inline_keyboard(language=language)
    )
    await state.set_state(AddItemStates.date_single)

@router.callback_query(F.data == "date_range", AddItemStates.date_type)
async def date_range_handler(callback: CallbackQuery, state: FSMContext):
    language = await _language_from_state(state)
    await callback.message.edit_text(
        translate_text(language, "📅 Enter the start date in DD.MM.YYYY:", "📅 Введите начальную дату в формате ДД.ММ.ГГГГ:"),
        reply_markup=get_skip_inline_keyboard(language=language)
    )
    await state.set_state(AddItemStates.date_from)

@router.callback_query(F.data == "skip_date", AddItemStates.date_type)
async def skip_date_handler(callback: CallbackQuery, state: FSMContext):
    await return_to_field_selection(callback, state)

@router.callback_query(F.data == "skip_field")
async def skip_field_handler(callback: CallbackQuery, state: FSMContext):
    await return_to_field_selection(callback, state)

@router.message(AddItemStates.date_single)
async def process_date_single(message: Message, state: FSMContext):
    language = await _language_from_state(state)
    if message.text in SKIP_BUTTONS:
        await return_to_field_selection(message, state)
        return
    
    date_obj = parse_date(message.text)
    if date_obj:
        await state.update_data(date_from=date_obj)
        await message.answer(
            translate_text(language, f"✅ Date set: {date_obj.strftime('%d.%m.%Y')}", f"✅ Дата установлена: {date_obj.strftime('%d.%m.%Y')}")
        )
        await return_to_field_selection(message, state)
    else:
        await message.answer(
            translate_text(language, "❌ Invalid date. Use DD.MM.YYYY or press 'Skip':", "❌ Некорректная дата. Введите дату в формате ДД.ММ.ГГГГ или нажмите 'Пропустить':"),
            reply_markup=get_skip_keyboard(language=language)
        )

@router.message(AddItemStates.date_from)
async def process_date_from(message: Message, state: FSMContext):
    language = await _language_from_state(state)
    if message.text in SKIP_BUTTONS:
        await return_to_field_selection(message, state)
        return

    date_obj = parse_date(message.text)
    if date_obj:
        await state.update_data(date_from=date_obj)
        await message.answer(
            translate_text(language, "📅 Enter the end date in DD.MM.YYYY:", "📅 Введите конечную дату в формате ДД.ММ.ГГГГ:"),
            reply_markup=get_skip_keyboard(language=language)
        )
        await state.set_state(AddItemStates.date_to)
    else:
        await message.answer(
            translate_text(language, "❌ Invalid date. Use DD.MM.YYYY or press 'Skip':", "❌ Некорректная дата. Введите дату в формате ДД.ММ.ГГГГ или нажмите 'Пропустить':"),
            reply_markup=get_skip_keyboard(language=language)
        )

@router.message(AddItemStates.date_to)
async def process_date_to(message: Message, state: FSMContext):
    language = await _language_from_state(state)
    if message.text in SKIP_BUTTONS:
        await return_to_field_selection(message, state)
        return

    date_obj = parse_date(message.text)
    if date_obj:
        data = await state.get_data()
        date_from = data.get('date_from')
        if date_from and date_obj >= date_from:
            await state.update_data(date_to=date_obj)
            await message.answer(
                translate_text(
                    language,
                    f"✅ Date range set: {date_from.strftime('%d.%m.%Y')} - {date_obj.strftime('%d.%m.%Y')}",
                    f"✅ Диапазон дат установлен: {date_from.strftime('%d.%m.%Y')} - {date_obj.strftime('%d.%m.%Y')}"
                )
            )
            await return_to_field_selection(message, state)
        else:
            await message.answer(
                translate_text(language, "❌ End date must be later than the start date. Try again or press 'Skip':", "❌ Конечная дата должна быть позже начальной. Попробуйте еще раз или нажмите 'Пропустить':"),
                reply_markup=get_skip_keyboard(language=language)
            )
    else:
        await message.answer(
            translate_text(language, "❌ Invalid date. Use DD.MM.YYYY or press 'Skip':", "❌ Некорректная дата. Введите дату в формате ДД.ММ.ГГГГ или нажмите 'Пропустить':"),
            reply_markup=get_skip_keyboard(language=language)
        )

@router.callback_query(F.data == "add_url", AddItemStates.select_field)
async def add_url_handler(callback: CallbackQuery, state: FSMContext):
    language = await _language_from_state(state)
    try:
        await callback.message.delete()
    except:
        pass
    
    msg = await callback.message.answer(
        translate_text(language, "🔗 Enter a link or press 'Skip':", "🔗 Введите ссылку или нажмите 'Пропустить':"),
        reply_markup=get_skip_keyboard(language=language)
    )
    await state.update_data(last_bot_message=msg.message_id)
    await add_ephemeral_message(state, msg.message_id)
    await state.set_state(AddItemStates.url)

@router.message(AddItemStates.url)
async def process_url(message: Message, state: FSMContext):
    language = await _language_from_state(state)
    if message.text in SKIP_BUTTONS:
        await return_to_field_selection(message, state)
        return
        
    url = message.text.strip()
    if url.startswith(('http://', 'https://')):
        await state.update_data(url=url)
        await message.answer(
            translate_text(language, f"✅ Link saved: {url}", f"✅ Ссылка добавлена: {url}")
        )
        await return_to_field_selection(message, state)
    else:
        await message.answer(
            translate_text(language, "❌ Invalid link. Use http:// or https://, or press 'Skip':", "❌ Некорректная ссылка. Введите ссылку, начинающуюся с http:// или https://, или нажмите 'Пропустить':"),
            reply_markup=get_skip_keyboard(language=language)
        )

@router.callback_query(F.data == "add_comment", AddItemStates.select_field)
async def add_comment_handler(callback: CallbackQuery, state: FSMContext):
    language = await _language_from_state(state)
    try:
        await callback.message.delete()
    except:
        pass
    
    msg = await callback.message.answer(
        translate_text(language, "💬 Enter a comment or press 'Skip':", "💬 Введите комментарий или нажмите 'Пропустить':"),
        reply_markup=get_skip_keyboard(language=language)
    )
    await state.update_data(last_bot_message=msg.message_id)
    await add_ephemeral_message(state, msg.message_id)
    await state.set_state(AddItemStates.comment)

@router.message(AddItemStates.comment)
async def process_comment(message: Message, state: FSMContext):
    language = await _language_from_state(state)
    if message.text in SKIP_BUTTONS:
        await return_to_field_selection(message, state)
        return
    
    comment = message.text.strip()
    await state.update_data(comment=comment)
    await message.answer(
        translate_text(language, f"✅ Comment added: {comment}", f"✅ Комментарий добавлен: {comment}")
    )
    await return_to_field_selection(message, state)

@router.callback_query(F.data == "add_photo", AddItemStates.select_field)
async def add_photo_handler(callback: CallbackQuery, state: FSMContext):
    language = await _language_from_state(state)
    try:
        await callback.message.delete()
    except:
        pass
    
    msg = await callback.message.answer(
        translate_text(language, "📷 Send a photo or press 'Skip':", "📷 Отправьте фото или нажмите 'Пропустить':"),
        reply_markup=get_skip_keyboard(language=language)
    )
    await state.update_data(last_bot_message=msg.message_id)
    await add_ephemeral_message(state, msg.message_id)
    await state.set_state(AddItemStates.photo)

@router.message(AddItemStates.photo, F.photo.is_not(None))
async def process_photo(message: Message, state: FSMContext):
    language = await _language_from_state(state)
    photo = message.photo[-1]
    await state.update_data(photo_file_id=photo.file_id)
    await message.answer(
        translate_text(language, "✅ Photo added", "✅ Фото добавлено")
    )
    await return_to_field_selection(message, state)

@router.message(AddItemStates.photo)
async def process_photo_text(message: Message, state: FSMContext):
    language = await _language_from_state(state)
    if message.text in SKIP_BUTTONS:
        await return_to_field_selection(message, state)
        return

    await message.answer(
        translate_text(language, "❌ Please send a photo or press 'Skip':", "❌ Пожалуйста, отправьте фото или нажмите 'Пропустить':")
    )

@router.callback_query(F.data == "finish_item", AddItemStates.select_field)
async def finish_item(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    data = await state.get_data()
    
    name = data.get('name')
    category_id = data.get('category_id')
    selected_tags = data.get('selected_tags', [])
    if selected_tags and not isinstance(selected_tags, list):
        selected_tags = []
    price = data.get('price')
    location_type = data.get('location_type')
    location_value = data.get('location_value')
    url = data.get('url')
    comment = data.get('comment')
    photo_file_id = data.get('photo_file_id')
    
    if not name or not category_id:
        await callback.answer(
            translate_text(language, "❌ Error: missing name or category", "❌ Ошибка: отсутствует название или категория")
        )
        return
    
    try:
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        if not category:
            await callback.answer(
                translate_text(language, "❌ Category unavailable", "❌ Категория недоступна"),
                show_alert=True
            )
            return

        has_access = category.owner_id == user.id
        if not has_access:
            access = await CategoryCRUD.check_user_access(session, category_id, user.id)
            has_access = bool(access and getattr(access, 'can_edit', False))

        if not has_access:
            await callback.answer(
                translate_text(language, "❌ You don't have permission to add items to this category", "❌ У вас нет прав добавлять элементы в эту категорию"),
                show_alert=True
            )
            return

        item_data = {
            'name': name,
            'category_id': category_id,
            'owner_id': user.id,
            'price': price,
            'url': url,
            'comment': comment,
            'photo_file_id': photo_file_id
        }
        
        if location_type and location_value:
            location = await LocationCRUD.get_or_create_location(session, location_type, location_value, user.id)
            item_data['location_id'] = location.id
        
        item = await ItemCRUD.create_item(session, **item_data)
        
        if selected_tags:
            await ItemCRUD.add_tags_to_item(session, item.id, selected_tags, user.id)
        
        if category and category.sharing_type in ["view_only", "collaborative"]:
            await send_item_added_notification(callback.bot, category, item, user)
        
        item_card = await format_item_card(session, item, language=language)
        
        try:
            await callback.message.delete()
        except:
            pass
        
        try:
            await cleanup_ephemeral_messages(callback.bot, state, callback.message.chat.id)
        except Exception:
            pass

        if item.photo_file_id:
            await callback.message.answer_photo(
                photo=item.photo_file_id,
                caption=item_card,
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(language=language)
            )
        else:
            await callback.message.answer(
                item_card,
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(language=language)
            )
        
        await callback.answer(
            translate_text(language, "✅ Item added successfully!", "✅ Элемент успешно добавлен!")
        )
        await state.clear()
        
    except Exception as e:
        try:
            logger.exception("Error while finishing item creation. state=%s", data)
        except Exception:
            pass
        await callback.answer(
            translate_text(language, f"❌ Failed to create item: {str(e)}", f"❌ Ошибка при создании элемента: {str(e)}")
        )

async def return_to_field_selection(message_or_callback, state: FSMContext):
    data = await state.get_data()
    name = data.get('name')
    user = data.get('user')
    language = get_user_language(user) if user else DEFAULT_LANGUAGE

    if name:
        safe_name = escape_markdown(str(name))
    else:
        safe_name = translate_text(language, "Unnamed", "Без названия")
    
    kb = InlineKeyboardBuilder()
    kb.button(text=translate_text(language, "🏷 Tags", "🏷 Теги"), callback_data="add_tags")
    kb.button(text=translate_text(language, "💸 Price", "💸 Цена"), callback_data="add_price")
    kb.button(text=translate_text(language, "📍 Location", "📍 Место"), callback_data="add_location")
    kb.button(text=translate_text(language, "📅 Date", "📅 Дата"), callback_data="add_date")
    kb.button(text=translate_text(language, "🔗 Link", "🔗 Ссылка"), callback_data="add_url")
    kb.button(text=translate_text(language, "💬 Comment", "💬 Комментарий"), callback_data="add_comment")
    kb.button(text=translate_text(language, "📷 Photo", "📷 Фото"), callback_data="add_photo")
    kb.button(text=translate_text(language, "✅ Finish", "✅ Завершить"), callback_data="finish_item")
    kb.adjust(2)
    
    last_message_id = data.get('last_bot_message')
    if last_message_id:
        try:
            if hasattr(message_or_callback, 'message'):
                await message_or_callback.message.bot.delete_message(
                    message_or_callback.message.chat.id, 
                    last_message_id
                )
            else:
                await message_or_callback.bot.delete_message(
                    message_or_callback.chat.id, 
                    last_message_id
                )
        except:
            pass
    
    prompt_text = translate_text(
        language,
        f"🎯 New item\nName: **{safe_name}**\n\nChoose what you want to add:",
        f"🎯 Новый элемент\nНазвание: **{safe_name}**\n\nВыберите, что хотите добавить:"
    )
    if hasattr(message_or_callback, 'message'):
        msg = await message_or_callback.message.answer(
            prompt_text,
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )
    else:
        msg = await message_or_callback.answer(
            prompt_text,
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )
    
    await state.update_data(last_bot_message=msg.message_id)
    await add_ephemeral_message(state, msg.message_id)
    await state.set_state(AddItemStates.select_field)
