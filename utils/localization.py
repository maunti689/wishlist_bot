"""Simple localization helpers for the bot UI."""
from typing import Dict, Optional

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "en": "English",
    "ru": "Русский",
}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # Buttons
    "buttons.add_item": {
        "en": "➕ Add item",
        "ru": "➕ Добавить элемент",
    },
    "buttons.add_category": {
        "en": "📁 Add category",
        "ru": "📁 Добавить категорию",
    },
    "buttons.view_list": {
        "en": "📃 View list",
        "ru": "📃 Посмотреть список",
    },
    "buttons.filter": {
        "en": "🔍 Filtering",
        "ru": "🔍 Фильтрация",
    },
    "buttons.manage_categories": {
        "en": "👥 Manage categories",
        "ru": "👥 Управление категориями",
    },
    "buttons.enter_code": {
        "en": "🔑 Enter code",
        "ru": "🔑 Ввести код",
    },
    "buttons.settings": {
        "en": "⚙️ Settings",
        "ru": "⚙️ Настройки",
    },
    "buttons.back": {
        "en": "◀️ Back",
        "ru": "◀️ Назад",
    },
    "buttons.skip": {
        "en": "⏭ Skip",
        "ru": "⏭ Пропустить",
    },
    "buttons.add_new_tag": {
        "en": "➕ Add new tag",
        "ru": "➕ Добавить новый тег",
    },
    "buttons.continue": {
        "en": "⏭ Continue",
        "ru": "⏭ Продолжить",
    },
    "buttons.add_new_location": {
        "en": "➕ Add new",
        "ru": "➕ Добавить новое",
    },
    "buttons.edit": {
        "en": "✏️ Edit",
        "ru": "✏️ Редактировать",
    },
    "buttons.delete": {
        "en": "🗑 Delete",
        "ru": "🗑 Удалить",
    },
    "buttons.yes": {
        "en": "✅ Yes",
        "ru": "✅ Да",
    },
    "buttons.no": {
        "en": "❌ No",
        "ru": "❌ Нет",
    },
    "buttons.back_to_categories": {
        "en": "◀️ Back to list",
        "ru": "◀️ Назад к списку",
    },
    "buttons.back_to_main": {
        "en": "◀️ Back to main menu",
        "ru": "◀️ Назад в главное меню",
    },

    # Location buttons
    "location.city": {
        "en": "🏙 In the city",
        "ru": "🏙 В городе",
    },
    "location.outside": {
        "en": "🌲 Outside the city",
        "ru": "🌲 За городом",
    },
    "location.district": {
        "en": "🏘 By district",
        "ru": "🏘 По району",
    },

    # Filters
    "filters.by_category": {
        "en": "📁 By category",
        "ru": "📁 По категории",
    },
    "filters.by_tag": {
        "en": "🏷 By tag",
        "ru": "🏷 По тегу",
    },
    "filters.by_price": {
        "en": "💸 By price",
        "ru": "💸 По стоимости",
    },
    "filters.by_location": {
        "en": "📍 By location",
        "ru": "📍 По местоположению",
    },
    "filters.by_date": {
        "en": "📅 By date",
        "ru": "📅 По дате",
    },
    "filters.by_type": {
        "en": "🎯 By type",
        "ru": "🎯 По типу",
    },
    "filters.reset": {
        "en": "🔄 Reset filters",
        "ru": "🔄 Сбросить фильтры",
    },
    "filters.exact_price": {
        "en": "💰 Exact amount",
        "ru": "💰 Точная сумма",
    },

    # Date shortcuts
    "date.this_week": {
        "en": "📅 This week",
        "ru": "📅 Эта неделя",
    },
    "date.this_month": {
        "en": "📅 This month",
        "ru": "📅 Этот месяц",
    },
    "date.custom_range": {
        "en": "📅 Custom range",
        "ru": "📅 С/по даты",
    },
    "date.single": {
        "en": "📅 Single date",
        "ru": "📅 Одна дата",
    },
    "date.range": {
        "en": "📅 Date range",
        "ru": "📅 С/По даты",
    },

    # Product types
    "product.event": {
        "en": "🎪 Event",
        "ru": "🎪 Мероприятие",
    },
    "product.restaurant": {
        "en": "🍽 Cafe/restaurant",
        "ru": "🍽 Кафе/ресторан",
    },
    "product.thing": {
        "en": "🛍 Item",
        "ru": "🛍 Вещь",
    },

    # Fields
    "fields.name": {
        "en": "📝 Name",
        "ru": "📝 Название",
    },
    "fields.tags": {
        "en": "🏷 Tags",
        "ru": "🏷 Теги",
    },
    "fields.price": {
        "en": "💸 Price",
        "ru": "💸 Цена",
    },
    "fields.date": {
        "en": "📅 Date",
        "ru": "📅 Дата",
    },
    "fields.location": {
        "en": "📍 Location",
        "ru": "📍 Местоположение",
    },
    "fields.comment": {
        "en": "💬 Comment",
        "ru": "💬 Комментарий",
    },
    "fields.url": {
        "en": "🔗 Link",
        "ru": "🔗 Ссылка",
    },
    "fields.photo": {
        "en": "📷 Photo",
        "ru": "📷 Фото",
    },

    # Sharing
    "sharing.private": {
        "en": "🔒 Private",
        "ru": "🔒 Личная",
    },
    "sharing.view_only": {
        "en": "👁 View only",
        "ru": "👁 Только просмотр",
    },
    "sharing.collaborative": {
        "en": "✍️ Collaborative",
        "ru": "✍️ Общая",
    },

    # Categories / misc
    "category.access_settings": {
        "en": "👥 Access settings",
        "ru": "👥 Настройки доступа",
    },
    "category.stats": {
        "en": "📊 Stats",
        "ru": "📊 Статистика",
    },
    "category.rename": {
        "en": "✏️ Rename",
        "ru": "✏️ Переименовать",
    },
    "category.change_sharing_type": {
        "en": "🔄 Change access type",
        "ru": "🔄 Изменить тип доступа",
    },
    "category.get_access_code": {
        "en": "🔑 Get access code",
        "ru": "🔑 Получить код доступа",
    },
    "category.manage_users": {
        "en": "👥 Manage users",
        "ru": "👥 Управление пользователями",
    },
}


def normalize_language(language: Optional[str]) -> str:
    """Return a supported language code (defaults to EN)."""
    if not language:
        return DEFAULT_LANGUAGE
    language = language.lower()
    if language in SUPPORTED_LANGUAGES:
        return language
    if language.startswith("en"):
        return "en"
    if language.startswith("ru"):
        return "ru"
    return DEFAULT_LANGUAGE


def get_user_language(user) -> str:
    """Extract the preferred language from a user model or fallback to default."""
    return normalize_language(getattr(user, "language", None))


def translate(key: str, language: Optional[str] = None, **kwargs) -> str:
    """Resolve translation by key with graceful fallback to English or key itself."""
    language = normalize_language(language)
    template = TRANSLATIONS.get(key, {}).get(language)
    if template is None:
        template = TRANSLATIONS.get(key, {}).get(DEFAULT_LANGUAGE, key)
    try:
        return template.format(**kwargs)
    except KeyError:
        # Missing formatting argument; return template to avoid crash.
        return template


def translate_text(language: Optional[str], english: str, russian: str) -> str:
    """Helper for ad-hoc translations without registering a key."""
    return russian if normalize_language(language) == "ru" else english


def get_value_variants(key: str) -> set[str]:
    """Return all localized values registered for a key."""
    values = TRANSLATIONS.get(key, {})
    return set(values.values()) if values else set()
