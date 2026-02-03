from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from typing import List, Optional

from utils.localization import translate as _, DEFAULT_LANGUAGE

def get_main_keyboard(language: str = DEFAULT_LANGUAGE) -> ReplyKeyboardMarkup:
    """Main menu keyboard."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=_("buttons.add_item", language=language)),
        KeyboardButton(text=_("buttons.add_category", language=language))
    )
    builder.row(
        KeyboardButton(text=_("buttons.view_list", language=language)),
        KeyboardButton(text=_("buttons.filter", language=language))
    )
    builder.row(
        KeyboardButton(text=_("buttons.manage_categories", language=language)),
        KeyboardButton(text=_("buttons.enter_code", language=language))
    )
    builder.row(
        KeyboardButton(text=_("buttons.settings", language=language)),
        KeyboardButton(text=_("buttons.back", language=language))
    )
    
    return builder.as_markup(resize_keyboard=True)

def get_back_keyboard(language: str = DEFAULT_LANGUAGE) -> ReplyKeyboardMarkup:
    """Keyboard with a Back button."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=_("buttons.back", language=language)))
    return builder.as_markup(resize_keyboard=True)

def get_skip_keyboard(language: str = DEFAULT_LANGUAGE) -> ReplyKeyboardMarkup:
    """Keyboard that offers Skip and Back buttons."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=_("buttons.skip", language=language)))
    builder.row(KeyboardButton(text=_("buttons.back", language=language)))
    return builder.as_markup(resize_keyboard=True)

def get_skip_inline_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Inline keyboard with a Skip button."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=_("buttons.skip", language=language), callback_data="skip_field"))
    return builder.as_markup()

def get_categories_keyboard(categories: List, include_skip: bool = False, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Inline keyboard for category selection."""
    builder = InlineKeyboardBuilder()
    
    for category in categories:
        builder.row(InlineKeyboardButton(
            text=category.name,
            callback_data=f"category_{category.id}"
        ))
    
    if include_skip:
        builder.row(InlineKeyboardButton(text=_("buttons.skip", language=language), callback_data="skip_category"))
    
    return builder.as_markup()

def get_tags_keyboard(
    tags: List,
    selected_tags: Optional[List] = None,
    include_add: bool = True,
    include_skip: bool = True,
    language: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    """Inline keyboard with tag buttons."""
    builder = InlineKeyboardBuilder()
    selected_tags = selected_tags or []
    
    # Display tags two per row
    for i in range(0, len(tags), 2):
        row_buttons = []
        # First button in the row
        tag = tags[i]
        text = f"✅ {tag.name}" if tag.name in selected_tags else tag.name
        row_buttons.append(InlineKeyboardButton(text=text, callback_data=f"tag_{tag.name}"))
        
        # Second button in the row (if available)
        if i + 1 < len(tags):
            tag = tags[i + 1]
            text = f"✅ {tag.name}" if tag.name in selected_tags else tag.name
            row_buttons.append(InlineKeyboardButton(text=text, callback_data=f"tag_{tag.name}"))
        
        builder.row(*row_buttons)
    
    if include_add:
        builder.row(
            InlineKeyboardButton(
                text=_("buttons.add_new_tag", language=language),
                callback_data="add_new_tag"
            )
        )

    if include_skip:
        builder.row(
            InlineKeyboardButton(
                text=_("buttons.continue", language=language),
                callback_data="skip_tags"
            )
        )

    return builder.as_markup()

def get_location_type_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Keyboard to choose a location type."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=_("location.city", language=language), callback_data="location_type_city"),
        InlineKeyboardButton(text=_("location.outside", language=language), callback_data="location_type_outside")
    )
    builder.row(
        InlineKeyboardButton(text=_("location.district", language=language), callback_data="location_type_district")
    )
    builder.row(
        InlineKeyboardButton(text=_("buttons.skip", language=language), callback_data="skip_location")
    )
    return builder.as_markup()

def get_locations_keyboard(
    locations: List,
    location_type: str,
    include_skip: bool = True,
    language: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    """Keyboard listing saved locations."""
    builder = InlineKeyboardBuilder()
    
    # Map descriptive types to callback suffixes
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
    
    builder.row(
        InlineKeyboardButton(
            text=_("buttons.add_new_location", language=language),
            callback_data=f"add_location_{location_type}"
        )
    )

    if include_skip:
        builder.row(
            InlineKeyboardButton(text=_("buttons.skip", language=language), callback_data="skip_location")
        )

    return builder.as_markup()

def get_item_actions_keyboard(item_id: int, can_edit: bool = True, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Actions keyboard for an item; hides edit/delete when not allowed."""
    builder = InlineKeyboardBuilder()
    if can_edit:
        builder.row(
            InlineKeyboardButton(
                text=_("buttons.edit", language=language),
                callback_data=f"edit_item_{item_id}"
            ),
            InlineKeyboardButton(
                text=_("buttons.delete", language=language),
                callback_data=f"delete_item_{item_id}"
            )
        )
    return builder.as_markup()

def get_filter_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Keyboard with filtering options."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=_("filters.by_category", language=language), callback_data="filter_category"),
        InlineKeyboardButton(text=_("filters.by_tag", language=language), callback_data="filter_tag")
    )
    builder.row(
        InlineKeyboardButton(text=_("filters.by_price", language=language), callback_data="filter_price"),
        InlineKeyboardButton(text=_("filters.by_location", language=language), callback_data="filter_location")
    )
    builder.row(
        InlineKeyboardButton(text=_("filters.by_date", language=language), callback_data="filter_date"),
        InlineKeyboardButton(text=_("filters.by_type", language=language), callback_data="filter_type")
    )
    builder.row(
        InlineKeyboardButton(text=_("filters.reset", language=language), callback_data="clear_filters")
    )
    return builder.as_markup()

def get_price_filter_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Keyboard with common price filters."""
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
    builder.row(
        InlineKeyboardButton(text=_("filters.exact_price", language=language), callback_data="price_exact")
    )
    return builder.as_markup()

def get_date_filter_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Keyboard with preset date filters."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=_("date.this_week", language=language), callback_data="date_this_week"),
        InlineKeyboardButton(text=_("date.this_month", language=language), callback_data="date_this_month")
    )
    builder.row(
        InlineKeyboardButton(text=_("date.custom_range", language=language), callback_data="date_custom")
    )
    return builder.as_markup()

def get_product_type_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Keyboard to select product type."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=_("product.event", language=language), callback_data="type_мероприятие"),
        InlineKeyboardButton(text=_("product.restaurant", language=language), callback_data="type_кафе/ресторан")
    )
    builder.row(
        InlineKeyboardButton(text=_("product.thing", language=language), callback_data="type_вещь")
    )
    return builder.as_markup()

def get_edit_fields_keyboard(item_id: int, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Keyboard to choose which item field to edit."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=_("fields.name", language=language), callback_data=f"edit_field_name_{item_id}"),
        InlineKeyboardButton(text=_("fields.tags", language=language), callback_data=f"edit_field_tags_{item_id}")
    )
    builder.row(
        InlineKeyboardButton(text=_("fields.price", language=language), callback_data=f"edit_field_price_{item_id}"),
        InlineKeyboardButton(text=_("fields.date", language=language), callback_data=f"edit_field_date_{item_id}")
    )
    builder.row(
        InlineKeyboardButton(text=_("fields.location", language=language), callback_data=f"edit_field_location_{item_id}"),
        InlineKeyboardButton(text=_("fields.comment", language=language), callback_data=f"edit_field_comment_{item_id}")
    )
    builder.row(
        InlineKeyboardButton(text=_("fields.url", language=language), callback_data=f"edit_field_url_{item_id}"),
        InlineKeyboardButton(text=_("fields.photo", language=language), callback_data=f"edit_field_photo_{item_id}")
    )
    return builder.as_markup()

def get_confirmation_keyboard(action: str, item_id: int = None, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Keyboard for confirming or cancelling an action."""
    builder = InlineKeyboardBuilder()
    if item_id:
        builder.row(
            InlineKeyboardButton(text=_("buttons.yes", language=language), callback_data=f"confirm_{action}_{item_id}"),
            InlineKeyboardButton(text=_("buttons.no", language=language), callback_data=f"cancel_{action}_{item_id}")
        )
    else:
        builder.row(
            InlineKeyboardButton(text=_("buttons.yes", language=language), callback_data=f"confirm_{action}"),
            InlineKeyboardButton(text=_("buttons.no", language=language), callback_data=f"cancel_{action}")
        )
    return builder.as_markup()

def get_sharing_type_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Keyboard to choose a category sharing type."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=_("sharing.private", language=language), callback_data="sharing_private")
    )
    builder.row(
        InlineKeyboardButton(text=_("sharing.view_only", language=language), callback_data="sharing_view_only")
    )
    builder.row(
        InlineKeyboardButton(text=_("sharing.collaborative", language=language), callback_data="sharing_collaborative")
    )
    return builder.as_markup()

def get_category_management_keyboard(
    category_id: int,
    is_owner: bool = True,
    language: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    """Keyboard with category management actions."""
    builder = InlineKeyboardBuilder()
    
    if is_owner:
        builder.row(
            InlineKeyboardButton(
                text=_("category.access_settings", language=language),
                callback_data=f"category_sharing_{category_id}"
            ),
            InlineKeyboardButton(
                text=_("category.stats", language=language),
                callback_data=f"category_stats_{category_id}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=_("category.rename", language=language),
                callback_data=f"category_rename_{category_id}"
            ),
            InlineKeyboardButton(
                text=_("buttons.delete", language=language),
                callback_data=f"category_delete_{category_id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text=_("buttons.back_to_categories", language=language),
            callback_data="back_to_categories"
        )
    )
    return builder.as_markup()

def get_category_sharing_keyboard(category_id: int, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Keyboard exposing access-management actions for a category."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("category.change_sharing_type", language=language),
            callback_data=f"change_sharing_type_{category_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("category.get_access_code", language=language),
            callback_data=f"get_share_link_{category_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("category.manage_users", language=language),
            callback_data=f"manage_users_{category_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("buttons.back", language=language),
            callback_data=f"category_menu_{category_id}"
        )
    )
    return builder.as_markup()

def get_date_input_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Keyboard for choosing how to input date values."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=_("date.single", language=language), callback_data="date_single"),
        InlineKeyboardButton(text=_("date.range", language=language), callback_data="date_range")
    )
    builder.row(
        InlineKeyboardButton(text=_("buttons.skip", language=language), callback_data="skip_date")
    )
    return builder.as_markup()

def get_categories_list_keyboard(categories: List, user_id: int, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    """Extended keyboard with a list of categories."""
    builder = InlineKeyboardBuilder()
    
    for category in categories:
        # Add emoji based on sharing type
        if category.sharing_type == "private":
            emoji = "🔒"
        elif category.sharing_type == "view_only":
            emoji = "👁"
        else:
            emoji = "✍️"
        
        # Count items when the relationship attribute is present
        items_count = 0
        if hasattr(category, 'items') and category.items:
            items_count = len(category.items)
        
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {category.name} ({items_count})",
            callback_data=f"category_menu_{category.id}"
        ))
    
    builder.row(
        InlineKeyboardButton(
            text=_("buttons.back_to_main", language=language),
            callback_data="back_to_main"
        )
    )
    return builder.as_markup()
