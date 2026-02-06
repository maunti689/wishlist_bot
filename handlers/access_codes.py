from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from keyboards import get_main_keyboard, get_back_keyboard
from states import ManageCategoryStates
from database.crud import CategoryCRUD
from utils.cleanup import add_ephemeral_message, cleanup_ephemeral_messages, schedule_delete_message
from utils.helpers import escape_markdown
from utils.localization import translate_text, get_user_language, get_value_variants
from utils.redis_client import get_redis_connection
from config import ACCESS_CODE_MAX_ATTEMPTS, ACCESS_CODE_BLOCK_SECONDS, ACCESS_CODE_LENGTH

router = Router()
logger = logging.getLogger(__name__)

ATTEMPT_PREFIX = "access_code_attempts"


def _attempts_key(user_id: int) -> str:
    return f"{ATTEMPT_PREFIX}:{user_id}"


async def _get_block_ttl(user_id: int) -> int:
    try:
        redis = await get_redis_connection()
    except Exception as exc:
        logger.warning("Redis unavailable while checking attempt limits: %s", exc)
        return 0
    key = _attempts_key(user_id)
    try:
        raw_value = await redis.get(key)
        if not raw_value:
            return 0
        attempts = int(raw_value)
        if attempts < ACCESS_CODE_MAX_ATTEMPTS:
            return 0
        ttl = await redis.ttl(key)
        if ttl is None or ttl < 0:
            await redis.expire(key, ACCESS_CODE_BLOCK_SECONDS)
            ttl = ACCESS_CODE_BLOCK_SECONDS
        return ttl
    except Exception as exc:
        logger.warning("Failed to fetch attempt TTL: %s", exc)
        return 0


async def _register_failed_attempt(user_id: int) -> int:
    try:
        redis = await get_redis_connection()
    except Exception as exc:
        logger.warning("Redis unavailable to record attempts: %s", exc)
        return 0
    key = _attempts_key(user_id)
    try:
        raw_value = await redis.get(key)
        if raw_value and int(raw_value) >= ACCESS_CODE_MAX_ATTEMPTS:
            ttl = await redis.ttl(key)
            if ttl is None or ttl < 0:
                await redis.expire(key, ACCESS_CODE_BLOCK_SECONDS)
                ttl = ACCESS_CODE_BLOCK_SECONDS
            return ttl

        attempts = await redis.incr(key)
        if attempts == 1:
            await redis.expire(key, ACCESS_CODE_BLOCK_SECONDS)
        if attempts >= ACCESS_CODE_MAX_ATTEMPTS:
            ttl = await redis.ttl(key)
            if ttl is None or ttl < 0:
                await redis.expire(key, ACCESS_CODE_BLOCK_SECONDS)
                ttl = ACCESS_CODE_BLOCK_SECONDS
            return ttl
        return 0
    except Exception as exc:
        logger.warning("Failed to update access attempts: %s", exc)
        return 0


async def _reset_attempts(user_id: int) -> None:
    try:
        redis = await get_redis_connection()
    except Exception:
        return
    try:
        await redis.delete(_attempts_key(user_id))
    except Exception as exc:
        logger.warning("Failed to reset attempts: %s", exc)


def _format_block_text(language: str, seconds: int) -> str:
    if seconds < 60:
        value = max(1, seconds)
        return translate_text(
            language,
            f"⏳ Too many attempts. Try again in {value} seconds.",
            f"⏳ Слишком много попыток. Попробуйте через {value} секунд."
        )
    minutes = max(1, seconds // 60)
    return translate_text(
        language,
        f"⏳ Too many attempts. Try again in {minutes} minutes.",
        f"⏳ Слишком много попыток. Попробуйте через {minutes} минут."
    )


async def _inform_rate_limit(message: Message, language: str, ttl: int):
    await message.answer(
        _format_block_text(language, ttl),
        reply_markup=get_back_keyboard(language=language)
    )

@router.message(F.text.in_(get_value_variants("buttons.enter_code")))
async def enter_code_start(message: Message, user, state: FSMContext):
    """Entry point when a user wants to type an access code."""
    logger.info(f"User {message.from_user.id} pressed 'Enter code'")
    
    language = get_user_language(user)
    code_length_text_en = (
        f"🔑 Enter a {ACCESS_CODE_LENGTH}-character access code for a category.\n\n"
        "The code may include letters and numbers, e.g. `ABC123`"
    )
    code_length_text_ru = (
        f"🔑 Введите код доступа из {ACCESS_CODE_LENGTH} символов.\n\n"
        "Код может содержать буквы и цифры, например `ABC123`"
    )
    msg = await message.answer(
        translate_text(language, code_length_text_en, code_length_text_ru),
        reply_markup=get_back_keyboard(language=language),
        parse_mode="Markdown"
    )
    await state.set_state(ManageCategoryStates.enter_access_code)
    await add_ephemeral_message(state, msg.message_id)

@router.message(ManageCategoryStates.enter_access_code)
async def process_access_code(message: Message, session: AsyncSession, user, state: FSMContext):
    """Validate and process the access code provided by the user."""
    logger.info(f"Processing access code: {message.text}")
    language = get_user_language(user)

    current_block = await _get_block_ttl(user.id)
    if current_block:
        await _inform_rate_limit(message, language, current_block)
        return

    # Handle Back button press
    if message.text in get_value_variants("buttons.back"):
        await state.clear()
        await message.answer(
            translate_text(language, "🏠 Main menu", "🏠 Главное меню"),
            reply_markup=get_main_keyboard(language=language)
        )
        return

    if not message.text:
        msg = await message.answer(
            translate_text(language, "❌ The code cannot be empty. Try again:", "❌ Код не может быть пустым. Попробуйте еще раз:"),
            reply_markup=get_back_keyboard(language=language)
        )
        await add_ephemeral_message(state, msg.message_id)
        return

    code = message.text.strip().upper()

    if len(code) != ACCESS_CODE_LENGTH or not code.isalnum():
        ttl = await _register_failed_attempt(user.id)
        if ttl:
            await _inform_rate_limit(message, language, ttl)
        else:
            await message.answer(
                translate_text(
                    language,
                    f"❌ The code must contain {ACCESS_CODE_LENGTH} letters and/or digits. Try again:",
                    f"❌ Код должен содержать {ACCESS_CODE_LENGTH} символов (буквы/цифры). Попробуйте еще раз:"
                ),
                reply_markup=get_back_keyboard(language=language)
            )
        return

    try:
        category = await CategoryCRUD.get_category_by_share_link(session, code)
    except Exception as e:
        logger.error(f"Failed to load category by code: {e}")
        msg = await message.answer(
            translate_text(language, "❌ An error occurred while searching for the category. Try again later.", "❌ Произошла ошибка при поиске категории. Попробуйте позже."),
            reply_markup=get_main_keyboard(language=language)
        )
        await state.clear()
        schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
        return

    if not category:
        ttl = await _register_failed_attempt(user.id)
        if ttl:
            await _inform_rate_limit(message, language, ttl)
        else:
            msg = await message.answer(
                translate_text(language, "❌ No category found for this code.", "❌ Категория с таким кодом не найдена."),
                reply_markup=get_main_keyboard(language=language)
            )
            await state.clear()
            schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
        return

    if category.sharing_type == "private":
        ttl = await _register_failed_attempt(user.id)
        if ttl:
            await _inform_rate_limit(message, language, ttl)
        else:
            msg = await message.answer(
                translate_text(language, "❌ This category is private and cannot be shared.", "❌ Эта категория является личной и недоступна для доступа."),
                reply_markup=get_main_keyboard(language=language)
            )
            await state.clear()
            schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
        return

    if category.owner_id == user.id:
        category_name = escape_markdown(category.name)
        msg = await message.answer(
            translate_text(
                language,
                f"ℹ️ This is your own category '{category_name}'.",
                f"ℹ️ Это ваша собственная категория '{category_name}'."
            ),
            reply_markup=get_main_keyboard(language=language)
        )
        await state.clear()
        schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
        return
    
    # Check whether the user already has access
    try:
        existing_access = await CategoryCRUD.check_user_access(session, category.id, user.id)
    except Exception as e:
        logger.error(f"Failed to check shared access: {e}")
        await message.answer(
            translate_text(language, "❌ Failed to verify access.", "❌ Произошла ошибка при проверке доступа."),
            reply_markup=get_main_keyboard(language=language)
        )
        await state.clear()
        return
    
    if existing_access:
        # Clean up ephemeral prompts before responding
        await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
        await state.clear()
        await _reset_attempts(user.id)
        category_name = escape_markdown(category.name)
        msg = await message.answer(
            translate_text(
                language,
                f"ℹ️ You already have access to category '{category_name}'.",
                f"ℹ️ У вас уже есть доступ к категории '{category_name}'."
            ),
            reply_markup=get_main_keyboard(language=language)
        )
        schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
        return
    
    # Grant access to the shared category
    try:
        can_edit = category.sharing_type == "collaborative"
        await CategoryCRUD.add_user_access(session, category.id, user.id, can_edit)
        await _reset_attempts(user.id)
        
        access_type = translate_text(language, "editing", "редактирования") if can_edit else translate_text(language, "viewing", "просмотра")
        
        # Clean up ephemeral prompts before final response
        await cleanup_ephemeral_messages(message.bot, state, message.chat.id)
        await state.clear()
        action_text = translate_text(
            language,
            "add and edit items" if can_edit else "view items",
            "добавлять и редактировать элементы" if can_edit else "просматривать элементы"
        )
        category_name = escape_markdown(category.name)
        msg = await message.answer(
            translate_text(
                language,
                f"✅ You now have {access_type} access to:\n"
                f"📁 **{category_name}**\n\n"
                f"You can now {action_text} in this category.",
                f"✅ Вы получили доступ для {access_type} к категории:\n"
                f"📁 **{category_name}**\n\n"
                f"Теперь вы можете {action_text} в этой категории."
            ),
            reply_markup=get_main_keyboard(language=language),
            parse_mode="Markdown"
        )
        schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
        
    except Exception as e:
        logger.error(f"Failed to grant shared access: {e}")
        msg = await message.answer(
            translate_text(language, "❌ Failed to grant access. Please try again later.", "❌ Произошла ошибка при добавлении доступа. Попробуйте позже."),
            reply_markup=get_main_keyboard(language=language)
        )
        await state.clear()
        schedule_delete_message(message.bot, message.chat.id, msg.message_id, delay=10)
