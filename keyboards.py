from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from typing import List

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="➕ Добавить элемент"),
        KeyboardButton(text="📁 Добавить категорию")
    )
    builder.row(
        KeyboardButton(text="📃 Посмотреть список"),
        KeyboardButton(text="🔍 Фильтрация")
    )
    builder.row(
        KeyboardButton(text="👥 Управление категориями"),
        KeyboardButton(text="🔑 Ввести код")
    )
    builder.row(
        KeyboardButton(text="⚙️ Настройки"),
        KeyboardButton(text="◀️ Назад")
    )
    
    return builder.as_markup(resize_keyboard=True)

def get_back_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой назад"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="◀️ Назад"))
    return builder.as_markup(resize_keyboard=True)

def get_skip_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопками пропустить и назад"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="⏭ Пропустить"))
    builder.row(KeyboardButton(text="◀️ Назад"))
    return builder.as_markup(resize_keyboard=True)

def get_skip_inline_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура с кнопкой пропустить"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_field"))
    return builder.as_markup()

def get_categories_keyboard(categories: List, include_skip=False) -> InlineKeyboardMarkup:
    """Инлайн-клавиатура с категориями"""
    builder = InlineKeyboardBuilder()
    
    for category in categories:
        builder.row(InlineKeyboardButton(
            text=category.name,
            callback_data=f"category_{category.id}"
        ))
    
    if include_skip:
        builder.row(InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_category"))
    
    return builder.as_markup()

def get_tags_keyboard(tags: List, selected_tags: List = None, include_add=True, include_skip=True) -> InlineKeyboardMarkup:
    """Инлайн-клавиатура с тегами"""
    builder = InlineKeyboardBuilder()
    selected_tags = selected_tags or []
    
    # Отображаем теги по 2 в ряд
    for i in range(0, len(tags), 2):
        row_buttons = []
        # Первая кнопка в ряду
        tag = tags[i]
        text = f"✅ {tag.name}" if tag.name in selected_tags else tag.name
        row_buttons.append(InlineKeyboardButton(text=text, callback_data=f"tag_{tag.name}"))
        
        # Вторая кнопка в ряду (если есть)
        if i + 1 < len(tags):
            tag = tags[i + 1]
            text = f"✅ {tag.name}" if tag.name in selected_tags else tag.name
            row_buttons.append(InlineKeyboardButton(text=text, callback_data=f"tag_{tag.name}"))
        
        builder.row(*row_buttons)
    
    if include_add:
        builder.row(InlineKeyboardButton(text="➕ Добавить новый тег", callback_data="add_new_tag"))
    
    if include_skip:
        builder.row(InlineKeyboardButton(text="⏭ Продолжить", callback_data="skip_tags"))
    
    return builder.as_markup()

def get_location_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа местоположения"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏙 В городе", callback_data="location_type_city"),
        InlineKeyboardButton(text="🌲 За городом", callback_data="location_type_outside")
    )
    builder.row(InlineKeyboardButton(text="🏘 По району", callback_data="location_type_district"))
    builder.row(InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_location"))
    return builder.as_markup()

def get_locations_keyboard(locations: List, location_type: str, include_skip=True) -> InlineKeyboardMarkup:
    """Клавиатура с местоположениями"""
    builder = InlineKeyboardBuilder()
    
    # Маппинг типов для callback_data
    type_mapping = {
        "в городе": "city",
        "за городом": "outside", 
        "по району": "district"
    }
    
    callback_type = type_mapping.get(location_type, location_type)
    
    for location in locations:
        builder.row(InlineKeyboardButton(
            text=location.name,
            callback_data=f"location_{callback_type}_{location.name}"
        ))
    
    builder.row(InlineKeyboardButton(
        text="➕ Добавить новое",
        callback_data=f"add_location_{location_type}"
    ))
    
    if include_skip:
        builder.row(InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_location"))
    
    return builder.as_markup()

def get_item_actions_keyboard(item_id: int, can_edit: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура действий с элементом. Если нет прав на редактирование — кнопки скрыты."""
    builder = InlineKeyboardBuilder()
    if can_edit:
        builder.row(
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_item_{item_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_item_{item_id}")
        )
    return builder.as_markup()

def get_filter_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура фильтрации"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📁 По категории", callback_data="filter_category"),
        InlineKeyboardButton(text="🏷 По тегу", callback_data="filter_tag")
    )
    builder.row(
        InlineKeyboardButton(text="💸 По стоимости", callback_data="filter_price"),
        InlineKeyboardButton(text="📍 По местоположению", callback_data="filter_location")
    )
    builder.row(
        InlineKeyboardButton(text="📅 По дате", callback_data="filter_date"),
        InlineKeyboardButton(text="🎯 По типу", callback_data="filter_type")
    )
    builder.row(InlineKeyboardButton(text="🔄 Сбросить фильтры", callback_data="clear_filters"))
    return builder.as_markup()

def get_price_filter_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура фильтрации по цене"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="< 1000", callback_data="price_max_1000"),
        InlineKeyboardButton(text="1000-3000", callback_data="price_range_1000_3000")
    )
    builder.row(
        InlineKeyboardButton(text="3000-5000", callback_data="price_range_3000_5000"),
        InlineKeyboardButton(text="5000-10000", callback_data="price_range_5000_10000")
    )
    builder.row(InlineKeyboardButton(text="> 10000", callback_data="price_min_10000"))
    builder.row(InlineKeyboardButton(text="💰 Точная сумма", callback_data="price_exact"))
    return builder.as_markup()

def get_date_filter_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура фильтрации по дате"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Эта неделя", callback_data="date_this_week"),
        InlineKeyboardButton(text="📅 Этот месяц", callback_data="date_this_month")
    )
    builder.row(InlineKeyboardButton(text="📅 С/по даты", callback_data="date_custom"))
    return builder.as_markup()

def get_product_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа продукта"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎪 Мероприятие", callback_data="type_мероприятие"),
        InlineKeyboardButton(text="🍽 Кафе/ресторан", callback_data="type_кафе/ресторан")
    )
    builder.row(InlineKeyboardButton(text="🛍 Вещь", callback_data="type_вещь"))
    return builder.as_markup()

def get_edit_fields_keyboard(item_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора поля для редактирования"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Название", callback_data=f"edit_field_name_{item_id}"),
        InlineKeyboardButton(text="🏷 Теги", callback_data=f"edit_field_tags_{item_id}")
    )
    builder.row(
        InlineKeyboardButton(text="💸 Цена", callback_data=f"edit_field_price_{item_id}"),
        InlineKeyboardButton(text="📅 Дата", callback_data=f"edit_field_date_{item_id}")
    )
    builder.row(
        InlineKeyboardButton(text="📍 Местоположение", callback_data=f"edit_field_location_{item_id}"),
        InlineKeyboardButton(text="💬 Комментарий", callback_data=f"edit_field_comment_{item_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔗 Ссылка", callback_data=f"edit_field_url_{item_id}"),
        InlineKeyboardButton(text="📷 Фото", callback_data=f"edit_field_photo_{item_id}")
    )
    return builder.as_markup()

def get_confirmation_keyboard(action: str, item_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия"""
    builder = InlineKeyboardBuilder()
    if item_id:
        builder.row(
            InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}_{item_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel_{action}_{item_id}")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel_{action}")
        )
    return builder.as_markup()

def get_sharing_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа шеринга категории"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔒 Личная", callback_data="sharing_private"))
    builder.row(InlineKeyboardButton(text="👁 Только просмотр", callback_data="sharing_view_only"))
    builder.row(InlineKeyboardButton(text="✍️ Общая", callback_data="sharing_collaborative"))
    return builder.as_markup()

def get_category_management_keyboard(category_id: int, is_owner: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура управления категорией"""
    builder = InlineKeyboardBuilder()
    
    if is_owner:
        builder.row(
            InlineKeyboardButton(text="👥 Настройки доступа", callback_data=f"category_sharing_{category_id}"),
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"category_stats_{category_id}")
        )
        builder.row(
            InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"category_rename_{category_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"category_delete_{category_id}")
        )
    
    builder.row(InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_categories"))
    return builder.as_markup()

def get_category_sharing_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Клавиатура управления доступом к категории"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Изменить тип доступа", callback_data=f"change_sharing_type_{category_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔑 Получить код доступа", callback_data=f"get_share_link_{category_id}")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Управление пользователями", callback_data=f"manage_users_{category_id}")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"category_menu_{category_id}")
    )
    return builder.as_markup()

def get_date_input_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа ввода даты"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Одна дата", callback_data="date_single"),
        InlineKeyboardButton(text="📅 С/По даты", callback_data="date_range")
    )
    builder.row(InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_date"))
    return builder.as_markup()

def get_categories_list_keyboard(categories: List, user_id: int) -> InlineKeyboardMarkup:
    """Расширенная клавиатура со списком категорий"""
    builder = InlineKeyboardBuilder()
    
    for category in categories:
        # Добавляем эмодзи в зависимости от типа доступа
        if category.sharing_type == "private":
            emoji = "🔒"
        elif category.sharing_type == "view_only":
            emoji = "👁"
        else:
            emoji = "✍️"
        
        # Подсчитываем элементы в категории (если есть атрибут items)
        items_count = 0
        if hasattr(category, 'items') and category.items:
            items_count = len(category.items)
        
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {category.name} ({items_count})",
            callback_data=f"category_menu_{category.id}"
        ))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад в главное меню", callback_data="back_to_main"))
    return builder.as_markup()
