from aiogram.fsm.state import State, StatesGroup

class AddItemStates(StatesGroup):
    """Состояния для добавления элемента"""
    name = State()
    category = State()
    select_field = State()  # Новое состояние для выбора полей
    tags = State()
    add_new_tag = State()
    price = State()
    location_type = State()
    location_value = State()
    add_new_location = State()
    date_type = State()
    date_single = State()
    date_from = State()
    date_to = State()
    url = State()
    comment = State()
    photo = State()

class AddCategoryStates(StatesGroup):
    """Состояния для добавления категории"""
    name = State()
    sharing_type = State()

class ManageCategoryStates(StatesGroup):
    """Состояния для управления категориями"""
    rename = State()
    change_sharing_type = State()
    add_user_by_id = State()
    enter_access_code = State()  # Новое состояние для ввода кода

class FilterStates(StatesGroup):
    """Состояния для фильтрации"""
    price_exact = State()
    date_from = State()
    date_to = State()

class EditItemStates(StatesGroup):
    """Состояния для редактирования элемента"""
    name = State()
    tags = State()
    add_new_tag = State()
    price = State()
    date_type = State()
    date_single = State()
    date_from = State()
    date_to = State()
    location_type = State()
    location_value = State()
    add_new_location = State()
    comment = State()
    url = State()
    photo = State()