from aiogram.fsm.state import State, StatesGroup

class AddItemStates(StatesGroup):
    """States used during the add-item flow."""
    name = State()
    category = State()
    select_field = State()  # State for selecting which field to fill next
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
    """States for creating a new category."""
    name = State()
    sharing_type = State()

class ManageCategoryStates(StatesGroup):
    """States for category management flows."""
    rename = State()
    change_sharing_type = State()
    add_user_by_id = State()
    enter_access_code = State()  # State when user types in an access code

class FilterStates(StatesGroup):
    """States used in filtering dialogues."""
    price_exact = State()
    date_from = State()
    date_to = State()

class EditItemStates(StatesGroup):
    """States for editing individual item fields."""
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
