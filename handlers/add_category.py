from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from database.crud import CategoryCRUD
from states import AddCategoryStates
from keyboards import get_main_keyboard, get_back_keyboard, get_sharing_type_keyboard
from config import MAX_CATEGORIES_PER_USER
from utils.helpers import escape_markdown
from utils.localization import translate as _, translate_text, get_user_language, get_value_variants

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text.in_(get_value_variants("buttons.add_category")))
async def add_category_start(message: Message, session: AsyncSession, user, state: FSMContext):
    try:
        language = get_user_language(user)
        user_categories = await CategoryCRUD.get_user_categories(session, user.id)
        
        if len(user_categories) >= MAX_CATEGORIES_PER_USER:
            await message.answer(
                translate_text(
                    language,
                    f"❌ You have reached the category limit ({MAX_CATEGORIES_PER_USER}). Remove a few before adding new ones.",
                    f"❌ Достигнут лимит категорий ({MAX_CATEGORIES_PER_USER}). Удалите некоторые категории перед добавлением новых."
                ),
                reply_markup=get_main_keyboard(language=language)
            )
            return
        
        await message.answer(
            translate_text(language, "📝 Enter a name for the new category:", "📝 Введите название новой категории:"),
            reply_markup=get_back_keyboard(language=language)
        )
        await state.set_state(AddCategoryStates.name)
        
    except Exception as e:
        logger.error(f"Ошибка в add_category_start: {e}")
        await message.answer(
            translate_text(language, "❌ Something went wrong. Please try again.", "❌ Произошла ошибка. Попробуйте еще раз."),
            reply_markup=get_main_keyboard(language=language)
        )

@router.message(AddCategoryStates.name)
async def process_category_name(message: Message, session: AsyncSession, user, state: FSMContext):
    language = get_user_language(user)
    if message.text in get_value_variants("buttons.back"):
        await state.clear()
        await message.answer(
            translate_text(language, "🏠 Main menu", "🏠 Главное меню"),
            reply_markup=get_main_keyboard(language=language)
        )
        return
    
    if not message.text or message.text.strip() == "":
        await message.answer(
            translate_text(language, "❌ Category name cannot be empty. Try again:", "❌ Название категории не может быть пустым. Попробуйте еще раз:")
        )
        return
    
    category_name = message.text.strip()
    safe_category_name = escape_markdown(category_name)
    
    if len(category_name) > 100:
        await message.answer(
            translate_text(language, "❌ Name is too long (max 100 characters). Try again:", "❌ Название слишком длинное (максимум 100 символов). Попробуйте еще раз:")
        )
        return
    
    if len(category_name) < 2:
        await message.answer(
            translate_text(language, "❌ Name is too short (min 2 characters). Try again:", "❌ Название слишком короткое (минимум 2 символа). Попробуйте еще раз:")
        )
        return
    
    try:
        user_categories = await CategoryCRUD.get_user_categories(session, user.id)
        own_categories = [cat for cat in user_categories if cat.owner_id == user.id]
        existing_names = [cat.name.lower() for cat in own_categories]
        
        if category_name.lower() in existing_names:
            await message.answer(
                translate_text(
                    language,
                    f"❌ Category '{safe_category_name}' already exists. Enter a different name:",
                    f"❌ Категория с названием '{safe_category_name}' уже существует. Введите другое название:"
                )
            )
            return
        
        await state.update_data(name=category_name)
        
        await message.answer(
            translate_text(
                language,
                f"📁 Category: **{safe_category_name}**\n\n🔐 Choose an access type:",
                f"📁 Категория: **{safe_category_name}**\n\n🔐 Выберите тип доступа к категории:"
            ),
            reply_markup=get_sharing_type_keyboard(language=language),
            parse_mode="Markdown"
        )
        await state.set_state(AddCategoryStates.sharing_type)
        
    except Exception as e:
        logger.error(f"Ошибка в process_category_name: {e}")
        await message.answer(
            translate_text(language, "❌ Failed to process the name. Please try again.", "❌ Произошла ошибка при обработке названия. Попробуйте еще раз."),
            reply_markup=get_main_keyboard(language=language)
        )
        await state.clear()

@router.callback_query(F.data.startswith("sharing_"), AddCategoryStates.sharing_type)
async def process_category_sharing_type(callback: CallbackQuery, session: AsyncSession, user, state: FSMContext):
    sharing_type = callback.data.split("sharing_")[1]
    language = get_user_language(user)
    
    data = await state.get_data()
    category_name = data.get('name')
    
    if not category_name:
        await callback.answer(translate_text(language, "❌ Category name not found", "❌ Ошибка: название категории не найдено"))
        await callback.message.answer(
            translate_text(language, "❌ Something went wrong. Please start creating the category again.", "❌ Произошла ошибка. Попробуйте создать категорию заново."),
            reply_markup=get_main_keyboard(language=language)
        )
        await state.clear()
        return
    
    try:
        category = await CategoryCRUD.create_category(
            session=session,
            name=category_name,
            owner_id=user.id,
            sharing_type=sharing_type
        )
        share_code = None
        if sharing_type in ["view_only", "collaborative"]:
            share_code = await CategoryCRUD.generate_unique_share_code(session)
        await CategoryCRUD.update_category_sharing(session, category.id, sharing_type, share_code)
        
        await state.clear()
        
        sharing_names = {
            "private": _("sharing.private", language=language),
            "view_only": _("sharing.view_only", language=language),
            "collaborative": _("sharing.collaborative", language=language)
        }
        
        safe_created_name = escape_markdown(category.name)
        success_text = (
            translate_text(
                language,
                f"✅ Category '{safe_created_name}' has been created!\n"
                f"🔐 Access type: {sharing_names.get(sharing_type)}",
                f"✅ Категория '{safe_created_name}' успешно создана!\n"
                f"🔐 Тип доступа: {sharing_names.get(sharing_type)}"
            )
        )
        
        if sharing_type == "view_only":
            success_text += translate_text(
                language,
                "\n\n👁 Other users will be able to view items in this category using the access code.",
                "\n\n👁 Другие пользователи смогут просматривать элементы в этой категории по коду доступа."
            )
        elif sharing_type == "collaborative":
            success_text += translate_text(
                language,
                "\n\n✍️ Other users will be able to add and edit items in this category using the access code.",
                "\n\n✍️ Другие пользователи смогут добавлять и редактировать элементы в этой категории по коду доступа."
            )
        
        if sharing_type != "private" and share_code:
            success_text += translate_text(
                language,
                f"\n\n🔑 Access code:\n`{share_code}`",
                f"\n\n🔑 Код для доступа:\n`{share_code}`"
            )
            success_text += translate_text(
                language,
                "\n\nShare it with people you want to invite to the category.",
                "\n\nОтправьте этот код тем, кому хотите дать доступ к категории."
            )
        
        await callback.message.answer(
            success_text,
            reply_markup=get_main_keyboard(language=language),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в process_category_sharing_type: {e}")
        await callback.message.answer(
            translate_text(language, "❌ Failed to create category. Please try again.", "❌ Произошла ошибка при создании категории. Попробуйте еще раз."),
            reply_markup=get_main_keyboard(language=language)
        )
        await state.clear()
    
    await callback.answer()
