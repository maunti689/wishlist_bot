from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from database.crud import ItemCRUD, CategoryCRUD, TagCRUD, LocationCRUD, UserCRUD
from states import FilterStates
from keyboards import (
    get_main_keyboard, get_filter_keyboard, get_categories_keyboard,
    get_tags_keyboard, get_price_filter_keyboard, get_date_filter_keyboard,
    get_location_type_keyboard, get_locations_keyboard, get_product_type_keyboard,
    get_item_actions_keyboard, get_back_keyboard
)
from utils.helpers import (
    format_item_card_sync, get_week_range, get_month_range, 
    parse_date, validate_price, parse_price_filter
)
from utils.cleanup import schedule_delete_message

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "🔍 Фильтрация")
async def filter_menu(message: Message, state: FSMContext):
    """Главное меню фильтрации"""
    await state.clear()
    msg = await message.answer("🔍 Выберите параметр для фильтрации:", reply_markup=get_filter_keyboard())
    schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=30)

@router.callback_query(F.data == "filter_category")
async def filter_by_category(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    """Фильтрация по категории"""
    try:
        categories = await CategoryCRUD.get_user_categories(session, user.id)
        if not categories:
            await callback.answer("❌ У вас нет категорий")
            return
        msg = await callback.message.answer("📂 Выберите категорию для фильтрации:", reply_markup=get_categories_keyboard(categories))
        schedule_delete_message(callback.bot, callback.message.chat.id, msg.message_id, delay=30)
    except Exception as e:
        logger.error(f"Ошибка в filter_by_category: {e}")
        await callback.answer("❌ Произошла ошибка")
    await callback.answer()

@router.callback_query(F.data.startswith("category_"))
async def apply_category_filter(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    """Применение фильтра по категории"""
    try:
        category_id = int(callback.data.split("category_")[1])
        filters = {'category_id': category_id}
        items = await ItemCRUD.filter_items(session, user.id, filters)
        category = await CategoryCRUD.get_category_by_id(session, category_id)
        await show_filtered_results(callback.message, items, f"Категория: {category.name if category else 'Неизвестная'}")
    except Exception as e:
        logger.error(f"Ошибка в apply_category_filter: {e}")
        await callback.message.answer("❌ Произошла ошибка при применении фильтра", reply_markup=get_main_keyboard())
    await callback.answer()

@router.callback_query(F.data == "filter_tag")
async def filter_by_tag(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    """Фильтрация по тегу"""
    try:
        popular_tags = await TagCRUD.get_popular_tags(session, user.id, limit=20)
        if not popular_tags:
            await callback.answer("❌ Теги не найдены")
            return
        msg = await callback.message.answer("🏷 Выберите тег для фильтрации:", reply_markup=get_tags_keyboard(popular_tags, include_add=False, include_skip=False))
        schedule_delete_message(callback.bot, callback.message.chat.id, msg.message_id, delay=30)
    except Exception as e:
        logger.error(f"Ошибка в filter_by_tag: {e}")
        await callback.answer("❌ Произошла ошибка")
    await callback.answer()

@router.callback_query(F.data.startswith("tag_"))
async def apply_tag_filter(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    """Применение фильтра по тегу"""
    try:
        tag_name = callback.data.split("tag_", 1)[1]
        filters = {'tag': tag_name}
        items = await ItemCRUD.filter_items(session, user.id, filters)
        await show_filtered_results(callback.message, items, f"Тег: #{tag_name}")
    except Exception as e:
        logger.error(f"Ошибка в apply_tag_filter: {e}")
        await callback.message.answer("❌ Произошла ошибка при применении фильтра", reply_markup=get_main_keyboard())
    await callback.answer()

@router.callback_query(F.data == "filter_price")
async def filter_by_price(callback: CallbackQuery, state: FSMContext):
    """Фильтрация по цене"""
    msg = await callback.message.answer("💸 Выберите диапазон цен:", reply_markup=get_price_filter_keyboard())
    schedule_delete_message(callback.bot, callback.message.chat.id, msg.message_id, delay=30)
    await callback.answer()

@router.callback_query(F.data.startswith("price_"))
async def apply_price_filter(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    """Применение фильтра по цене"""
    try:
        price_filter = callback.data
        filters = {}
        filter_text = ""
        
        if price_filter == "price_max_1000":
            filters['price_max'] = 1000
            filter_text = "до 1000 ₽"
        elif price_filter == "price_range_1000_3000":
            filters['price_min'] = 1000
            filters['price_max'] = 3000
            filter_text = "1000-3000 ₽"
        elif price_filter == "price_range_3000_5000":
            filters['price_min'] = 3000
            filters['price_max'] = 5000
            filter_text = "3000-5000 ₽"
        elif price_filter == "price_range_5000_10000":
            filters['price_min'] = 5000
            filters['price_max'] = 10000
            filter_text = "5000-10000 ₽"
        elif price_filter == "price_min_10000":
            filters['price_min'] = 10000
            filter_text = "от 10000 ₽"
        elif price_filter == "price_exact":
            msg = await callback.message.answer(
                "💰 Введите точную сумму:", 
                reply_markup=get_back_keyboard()
            )
            schedule_delete_message(callback.bot, callback.message.chat.id, msg.message_id, delay=30)
            await state.set_state(FilterStates.price_exact)
            await callback.answer()
            return
            
        if filters:
            items = await ItemCRUD.filter_items(session, user.id, filters)
            await show_filtered_results(callback.message, items, f"Цена: {filter_text}")
            
    except Exception as e:
        logger.error(f"Ошибка в apply_price_filter: {e}")
        await callback.message.answer("❌ Произошла ошибка при применении фильтра", reply_markup=get_main_keyboard())
    
    await callback.answer()

@router.message(FilterStates.price_exact)
async def process_exact_price_filter(message: Message, session: AsyncSession, user, state: FSMContext):
    """Обработка точной цены для фильтрации"""
    # Обработка кнопки "Назад"
    if message.text == "◀️ Назад":
        await state.clear()
        await message.answer("🏠 Главное меню", reply_markup=get_main_keyboard())
        return
    
    try:
        is_valid, price = validate_price(message.text)
        if is_valid and price is not None:
            filters = {'price_exact': price}
            items = await ItemCRUD.filter_items(session, user.id, filters)
            await show_filtered_results(message, items, f"Точная цена: {price} ₽")
            await state.clear()
        else:
            await message.answer("❌ Некорректная цена. Попробуйте еще раз:")
    except Exception as e:
        logger.error(f"Ошибка в process_exact_price_filter: {e}")
        await message.answer("❌ Произошла ошибка при обработке цены", reply_markup=get_main_keyboard())
        await state.clear()

@router.callback_query(F.data == "filter_date")
async def filter_by_date(callback: CallbackQuery, state: FSMContext):
    """Фильтрация по дате"""
    await callback.message.answer("📅 Выберите период:", reply_markup=get_date_filter_keyboard())
    await callback.answer()

@router.callback_query(F.data == "date_this_week")
async def filter_this_week(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    """Фильтрация по текущей неделе"""
    try:
        start_date, end_date = get_week_range()
        filters = {'date_from': start_date, 'date_to': end_date}
        items = await ItemCRUD.filter_items(session, user.id, filters)
        await show_filtered_results(callback.message, items, "Эта неделя")
    except Exception as e:
        logger.error(f"Ошибка в filter_this_week: {e}")
        await callback.message.answer("❌ Произошла ошибка при применении фильтра", reply_markup=get_main_keyboard())
    await callback.answer()

@router.callback_query(F.data == "date_this_month")
async def filter_this_month(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    """Фильтрация по текущему месяцу"""
    try:
        start_date, end_date = get_month_range()
        filters = {'date_from': start_date, 'date_to': end_date}
        items = await ItemCRUD.filter_items(session, user.id, filters)
        await show_filtered_results(callback.message, items, "Этот месяц")
    except Exception as e:
        logger.error(f"Ошибка в filter_this_month: {e}")
        await callback.message.answer("❌ Произошла ошибка при применении фильтра", reply_markup=get_main_keyboard())
    await callback.answer()

@router.callback_query(F.data == "date_custom")
async def filter_custom_date(callback: CallbackQuery, state: FSMContext):
    """Пользовательская фильтрация по дате"""
    await callback.message.answer(
        "📅 Введите дату начала в формате ДД.ММ.ГГГГ:", 
        reply_markup=get_back_keyboard()
    )
    await state.set_state(FilterStates.date_from)
    await callback.answer()

@router.message(FilterStates.date_from)
async def process_date_from(message: Message, state: FSMContext):
    """Обработка даты начала"""
    # Обработка кнопки "Назад"
    if message.text == "◀️ Назад":
        await state.clear()
        await message.answer("🏠 Главное меню", reply_markup=get_main_keyboard())
        return
        
    try:
        date_from = parse_date(message.text)
        if date_from:
            await state.update_data(date_from=date_from)
            await message.answer(
                "📅 Введите дату окончания в формате ДД.ММ.ГГГГ:", 
                reply_markup=get_back_keyboard()
            )
            await state.set_state(FilterStates.date_to)
        else:
            await message.answer("❌ Некорректная дата. Используйте формат ДД.ММ.ГГГГ:")
    except Exception as e:
        logger.error(f"Ошибка в process_date_from: {e}")
        await message.answer("❌ Произошла ошибка при обработке даты", reply_markup=get_main_keyboard())
        await state.clear()

@router.message(FilterStates.date_to)
async def process_date_to(message: Message, session: AsyncSession, user, state: FSMContext):
    """Обработка даты окончания"""
    # Обработка кнопки "Назад"
    if message.text == "◀️ Назад":
        await state.set_state(FilterStates.date_from)
        await message.answer("📅 Введите дату начала в формате ДД.ММ.ГГГГ:", reply_markup=get_back_keyboard())
        return
        
    try:
        date_to = parse_date(message.text)
        if date_to:
            data = await state.get_data()
            date_from = data.get('date_from')
            if date_from and date_to >= date_from:
                filters = {'date_from': date_from, 'date_to': date_to}
                items = await ItemCRUD.filter_items(session, user.id, filters)
                filter_text = f"С {date_from.strftime('%d.%m.%Y')} по {date_to.strftime('%d.%m.%Y')}"
                await show_filtered_results(message, items, filter_text)
                await state.clear()
            else:
                await message.answer("❌ Дата окончания должна быть не раньше даты начала:")
        else:
            await message.answer("❌ Некорректная дата. Используйте формат ДД.ММ.ГГГГ:")
    except Exception as e:
        logger.error(f"Ошибка в process_date_to: {e}")
        await message.answer("❌ Произошла ошибка при обработке даты", reply_markup=get_main_keyboard())
        await state.clear()

@router.callback_query(F.data == "filter_location")
async def filter_by_location(callback: CallbackQuery, state: FSMContext):
    """Фильтрация по местоположению"""
    await callback.message.answer("📍 Выберите тип местоположения:", reply_markup=get_location_type_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("location_type_"))
async def filter_by_location_type(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    """Фильтрация по типу местоположения"""
    try:
        location_type_map = {
            "location_type_city": "в городе",
            "location_type_outside": "за городом",
            "location_type_district": "по району"
        }
        location_type = location_type_map.get(callback.data)
        
        if location_type:
            locations = await LocationCRUD.get_locations_by_type(session, location_type, user.id)
            if not locations:
                filters = {'location_type': location_type}
                items = await ItemCRUD.filter_items(session, user.id, filters)
                await show_filtered_results(callback.message, items, f"Тип: {location_type}")
            else:
                await callback.message.answer(
                    f"📍 Выберите конкретное место ({location_type}):", 
                    reply_markup=get_locations_keyboard(locations, location_type, include_skip=True)
                )
    except Exception as e:
        logger.error(f"Ошибка в filter_by_location_type: {e}")
        await callback.message.answer("❌ Произошла ошибка при применении фильтра", reply_markup=get_main_keyboard())
    
    await callback.answer()

@router.callback_query(F.data.startswith("location_"))
async def apply_location_filter(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    """Применение фильтра по местоположению"""
    try:
        if callback.data == "skip_location":
            await callback.answer()
            return
            
        parts = callback.data.split("_", 2)
        if len(parts) >= 3:
            location_type = parts[1]
            location_value = parts[2]
            filters = {'location_type': location_type, 'location_value': location_value}
            items = await ItemCRUD.filter_items(session, user.id, filters)
            await show_filtered_results(callback.message, items, f"Место: {location_value}")
    except Exception as e:
        logger.error(f"Ошибка в apply_location_filter: {e}")
        await callback.message.answer("❌ Произошла ошибка при применении фильтра", reply_markup=get_main_keyboard())
    
    await callback.answer()

@router.callback_query(F.data == "filter_type")
async def filter_by_product_type(callback: CallbackQuery, state: FSMContext):
    """Фильтрация по типу продукта"""
    await callback.message.answer("🎯 Выберите тип продукта:", reply_markup=get_product_type_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("type_"))
async def apply_product_type_filter(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    """Применение фильтра по типу продукта"""
    try:
        product_type = callback.data.split("type_")[1]
        filters = {'product_type': product_type}
        items = await ItemCRUD.filter_items(session, user.id, filters)
        await show_filtered_results(callback.message, items, f"Тип: {product_type}")
    except Exception as e:
        logger.error(f"Ошибка в apply_product_type_filter: {e}")
        await callback.message.answer("❌ Произошла ошибка при применении фильтра", reply_markup=get_main_keyboard())
    
    await callback.answer()

@router.callback_query(F.data == "clear_filters")
async def clear_filters(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    """Сброс всех фильтров"""
    try:
        await state.clear()
        items = await ItemCRUD.get_items_accessible_to_user(session, user.id)
        await show_filtered_results(callback.message, items, "Все элементы (фильтры сброшены)")
    except Exception as e:
        logger.error(f"Ошибка в clear_filters: {e}")
        await callback.message.answer("❌ Произошла ошибка при сбросе фильтров", reply_markup=get_main_keyboard())
    
    await callback.answer()

async def show_filtered_results(message: Message, items: list, filter_description: str):
    """Показать результаты фильтрации"""
    try:
        if not items:
            m = await message.answer(
                f"🔍 Фильтр: {filter_description}\n\n❌ Элементы не найдены", 
                reply_markup=get_main_keyboard()
            )
            schedule_delete_message(message.bot, message.chat.id, m.message_id, delay=15)
            return
            
        m1 = await message.answer(
            f"🔍 Фильтр: {filter_description}\n📊 Найдено элементов: {len(items)}"
        )
        schedule_delete_message(message.bot, message.chat.id, m1.message_id, delay=15)
        
        # Показываем первые 10 элементов
        for item in items[:10]:
            try:
                card_text = format_item_card_sync(item)
                if item.photo_file_id:
                    await message.answer_photo(
                        photo=item.photo_file_id, 
                        caption=card_text, 
                        reply_markup=get_item_actions_keyboard(item.id), 
                        parse_mode="Markdown"
                    )
                else:
                    await message.answer(
                        card_text, 
                        reply_markup=get_item_actions_keyboard(item.id), 
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logger.error(f"Ошибка при показе элемента {item.id}: {e}")
                continue
        
        if len(items) > 10:
            await message.answer(f"... и еще {len(items) - 10} элементов")
            
        m2 = await message.answer(
            "Результаты фильтрации показаны выше 👆", 
            reply_markup=get_main_keyboard()
        )
        schedule_delete_message(message.bot, message.chat.id, m2.message_id, delay=15)
        
    except Exception as e:
        logger.error(f"Ошибка в show_filtered_results: {e}")
        await message.answer(
            "❌ Произошла ошибка при показе результатов", 
            reply_markup=get_main_keyboard()
        )
