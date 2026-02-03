import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
import re
import secrets
from config import DATE_FORMAT

def parse_tags(tags_string: str) -> List[str]:
    """Parse a comma-separated string of tags."""
    if not tags_string:
        return []
    
    # Split by commas and strip whitespace
    tags = [tag.strip() for tag in tags_string.split(',')]
    # Drop empty segments
    tags = [tag for tag in tags if tag]
    # Normalize casing
    tags = [tag.lower() for tag in tags]
    
    return tags

async def format_item_card(session, item) -> str:
    """Render a text card for an item using DB session helpers."""
    try:
        title = escape_markdown(str(item.name)) if getattr(item, 'name', None) else 'Без названия'
        card = f"🎯 **{title}**\n\n"
        
        if hasattr(item, 'category') and item.category:
            cat = escape_markdown(item.category.name)
            card += f"📁 Категория: {cat}\n"
        
        # Tags
        if item.tags:
            try:
                tags_list = json.loads(item.tags) if isinstance(item.tags, str) else item.tags
                if tags_list and isinstance(tags_list, list):
                    tags_str = ", ".join(f"#{escape_markdown(str(tag))}" for tag in tags_list)
                    card += f"🏷 Теги: {tags_str}\n"
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Price
        if item.price:
            card += f"💸 Стоимость: {format_price(item.price)}\n"
        
        # Location
        if hasattr(item, 'location_id') and item.location_id:
            # Load stored location by ID
            from database.crud import LocationCRUD
            location = await LocationCRUD.get_location_by_id(session, item.location_id)
            if location:
                location_emoji = get_location_emoji(location.location_type)
                card += f"{location_emoji} Местоположение: {escape_markdown(location.name)}\n"
        elif item.location_type and item.location_value:
            location_emoji = get_location_emoji(item.location_type)
            card += f"{location_emoji} Местоположение: {escape_markdown(item.location_value)}\n"
        
        # Date info
        if hasattr(item, 'date_from') and item.date_from:
            if hasattr(item, 'date_to') and item.date_to and item.date_to != item.date_from:
                # Date range
                card += f"📅 Период: {item.date_from.strftime(DATE_FORMAT)} - {item.date_to.strftime(DATE_FORMAT)}\n"
            else:
                # Single date
                card += f"📅 Дата: {item.date_from.strftime(DATE_FORMAT)}\n"
        elif hasattr(item, 'date') and item.date:  # Legacy compatibility
            card += f"📅 Дата: {item.date.strftime(DATE_FORMAT)}\n"
        
        # Product type
        if item.product_type and item.product_type != "вещь":
            type_emoji = get_product_type_emoji(item.product_type)
            card += f"{type_emoji} Тип: {escape_markdown(item.product_type)}\n"
        
        # URL
        if item.url:
            card += f"🔗 Ссылка: {escape_markdown(item.url)}\n"
        
        # Comment
        if item.comment:
            card += f"💬 Комментарий: {escape_markdown(item.comment)}\n"
        
        return card
        
    except Exception as e:
        # Fallback when formatting fails
        return f"🎯 **{getattr(item, 'name', 'Неизвестный элемент')}**\n❌ Ошибка отображения данных"

def format_item_card_sync(item) -> str:
    """Synchronous helper that builds an item card."""
    try:
        title = escape_markdown(str(item.name)) if getattr(item, 'name', None) else 'Без названия'
        card = f"🎯 **{title}**\n\n"
        
        if hasattr(item, 'category') and item.category:
            cat = escape_markdown(item.category.name)
            card += f"📁 Категория: {cat}\n"
        
        # Tags
        if item.tags:
            try:
                tags_list = json.loads(item.tags) if isinstance(item.tags, str) else item.tags
                if tags_list and isinstance(tags_list, list):
                    tags_str = ", ".join(f"#{escape_markdown(str(tag))}" for tag in tags_list)
                    card += f"🏷 Теги: {tags_str}\n"
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Price
        if item.price:
            card += f"💸 Стоимость: {format_price(item.price)}\n"
        
        # Location
        if item.location_type and item.location_value:
            location_emoji = get_location_emoji(item.location_type)
            card += f"{location_emoji} Местоположение: {escape_markdown(item.location_value)}\n"
        
        # Date info
        if hasattr(item, 'date_from') and item.date_from:
            if hasattr(item, 'date_to') and item.date_to and item.date_to != item.date_from:
                # Date range
                card += f"📅 Период: {item.date_from.strftime(DATE_FORMAT)} - {item.date_to.strftime(DATE_FORMAT)}\n"
            else:
                # Single date
                card += f"📅 Дата: {item.date_from.strftime(DATE_FORMAT)}\n"
        elif hasattr(item, 'date') and item.date:  # Legacy compatibility
            card += f"📅 Дата: {item.date.strftime(DATE_FORMAT)}\n"
        
        # Product type
        if item.product_type and item.product_type != "вещь":
            type_emoji = get_product_type_emoji(item.product_type)
            card += f"{type_emoji} Тип: {escape_markdown(item.product_type)}\n"
        
        # URL
        if item.url:
            card += f"🔗 Ссылка: {escape_markdown(item.url)}\n"
        
        # Comment
        if item.comment:
            card += f"💬 Комментарий: {escape_markdown(item.comment)}\n"
        
        return card
        
    except Exception as e:
        # Fallback when formatting fails
        return f"🎯 **{getattr(item, 'name', 'Неизвестный элемент')}**\n❌ Ошибка отображения данных"

def format_price(price: float) -> str:
    """Format price with thousands separator and currency."""
    if price == int(price):
        return f"{int(price):,} ₽".replace(",", " ")
    else:
        return f"{price:,.2f} ₽".replace(",", " ")

def get_location_emoji(location_type: str) -> str:
    """Return emoji associated with a location type."""
    emoji_map = {
        "в городе": "🏙",
        "за городом": "🌲",
        "по району": "🏘"
    }
    return emoji_map.get(location_type, "📍")

def get_product_type_emoji(product_type: str) -> str:
    """Return emoji associated with product type."""
    emoji_map = {
        "мероприятие": "🎪",
        "кафе/ресторан": "🍽",
        "вещь": "🛍"
    }
    return emoji_map.get(product_type, "🛍")

def parse_date(date_string: str) -> Optional[datetime]:
    """Parse a date string in DATE_FORMAT."""
    if not date_string:
        return None
    
    try:
        return datetime.strptime(date_string.strip(), DATE_FORMAT)
    except ValueError:
        return None

def validate_price(price_string: str) -> Optional[float]:
    """Validate and normalize price input."""
    if not price_string:
        return None
    
    # Preserve leading minus if provided
    is_negative = price_string.strip().startswith('-')
    
    # Keep only digits and decimal separators
    cleaned = re.sub(r'[^\d.,]', '', price_string)
    
    # If both comma and dot exist treat commas as thousand separators
    if ',' in cleaned and '.' in cleaned:
        cleaned = cleaned.replace(',', '')
    else:
        # If only commas are present treat them as decimal separator
        if ',' in cleaned and '.' not in cleaned:
            cleaned = cleaned.replace(',', '.')
    
    # Restore sign for correct parsing
    if cleaned and is_negative:
        cleaned = '-' + cleaned
    
    try:
        price = float(cleaned)
        return price if price >= 0 else None
    except ValueError:
        return None

def get_week_range() -> Tuple[datetime, datetime]:
    """Return datetime boundaries for the current week."""
    now = datetime.now()
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return start_of_week, end_of_week

def get_month_range() -> Tuple[datetime, datetime]:
    """Return datetime boundaries for the current month."""
    now = datetime.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Determine the last moment of the current month
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_month = now.replace(month=now.month + 1, day=1)
    
    end_of_month = next_month - timedelta(seconds=1)
    return start_of_month, end_of_month

def truncate_text(text: str, max_length: int = 50) -> str:
    """Trim text to the requested length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def parse_price_filter(filter_text: str) -> Dict[str, float]:
    """Parse textual price filters into numeric bounds."""
    result = {}
    
    if filter_text.startswith('<'):
        # < 1000
        try:
            result['price_max'] = float(filter_text[1:].strip())
        except ValueError:
            pass
    elif filter_text.startswith('>'):
        # > 2000
        try:
            result['price_min'] = float(filter_text[1:].strip())
        except ValueError:
            pass
    elif filter_text.startswith('='):
        # = 3000
        try:
            result['price_exact'] = float(filter_text[1:].strip())
        except ValueError:
            pass
    elif '-' in filter_text:
        # 1000-3000
        try:
            min_price, max_price = filter_text.split('-')
            result['price_min'] = float(min_price.strip())
            result['price_max'] = float(max_price.strip())
        except ValueError:
            pass
    
    return result

def escape_markdown(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters in user text."""
    if text is None:
        return ""
    text = str(text)
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


def generate_secure_code(length: int = 10, alphabet: str = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789") -> str:
    """Generate a secure random string based on provided alphabet."""
    if length <= 0:
        raise ValueError("length must be positive")
    if not alphabet:
        raise ValueError("alphabet must not be empty")
    return ''.join(secrets.choice(alphabet) for _ in range(length))
