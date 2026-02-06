from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import CategoryCRUD
from keyboards import get_main_keyboard
from utils.localization import get_value_variants, get_user_language, translate_text

router = Router()

class JoinSharedCategoryStates(StatesGroup):
    waiting_for_code = State()

@router.message(F.text.in_(get_value_variants("buttons.enter_code")))
async def ask_for_share_code(message: Message, user, state: FSMContext):
    language = get_user_language(user)
    await message.answer(
        translate_text(language, "🔑 Enter the category access code:", "🔑 Введите код доступа к категории:")
    )
    await state.set_state(JoinSharedCategoryStates.waiting_for_code)

@router.message(StateFilter(JoinSharedCategoryStates.waiting_for_code))
async def process_share_code(message: Message, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    code = message.text.strip()

    category = await CategoryCRUD.get_category_by_share_link(session, code)
    if not category:
        await message.answer(
            translate_text(language, "❌ Category not found for this code. Check the code and try again.", "❌ Категория с таким кодом не найдена. Проверьте код и попробуйте снова.")
        )
        return

    if category.owner_id == user.id:
        await message.answer(
            translate_text(language, "⚠️ This is your own category. You already have access.", "⚠️ Это ваша собственная категория. Вы уже имеете к ней доступ.")
        )
        await state.clear()
        return

    already_has_access = await CategoryCRUD.check_user_access(session, category.id, user.id)
    if already_has_access:
        await message.answer(
            translate_text(language, "✅ You already have access to this category.", "✅ У вас уже есть доступ к этой категории."),
            reply_markup=get_main_keyboard(language=language)
        )
    else:
        await CategoryCRUD.add_user_access(session, category.id, user.id)
        await message.answer(
            translate_text(language, f"✅ Access granted to \"{category.name}\"!", f"✅ Доступ к категории \"{category.name}\" предоставлен!"),
            reply_markup=get_main_keyboard(language=language)
        )

    await state.clear()
