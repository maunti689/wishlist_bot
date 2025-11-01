from keyboards import (
    get_main_keyboard, get_back_keyboard, get_skip_keyboard,
    get_tags_keyboard, get_location_type_keyboard, get_locations_keyboard,
    get_product_type_keyboard, get_date_input_keyboard, get_categories_keyboard
)


def test_main_and_back_keyboards_exist():
    mk = get_main_keyboard()
    bk = get_back_keyboard()
    assert mk is not None
    assert bk is not None


def test_skip_keyboard_exists():
    sk = get_skip_keyboard()
    assert sk is not None


def test_date_input_keyboard():
    dk = get_date_input_keyboard()
    assert dk is not None


def test_categories_keyboard_empty_list():
    kb = get_categories_keyboard([], include_skip=True)
    assert kb is not None
