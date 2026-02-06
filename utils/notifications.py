import asyncio
from datetime import datetime, timedelta
from typing import List
from aiogram import Bot
from sqlalchemy import select, or_, and_
from database.models import AsyncSessionLocal, Item, User, Category, SharedCategory
from config import NOTIFICATION_DAYS_BEFORE
from utils.helpers import escape_markdown
from utils.localization import translate_text, get_user_language
import logging

logger = logging.getLogger(__name__)


def _user_language(user: User) -> str:
    """Return normalized language for a DB user object."""
    return get_user_language(user) if user else None


def _display_name(user: User, language: str) -> str:
    """Escape and localize fallback name for notifications."""
    fallback = translate_text(language, "User", "Пользователь")
    raw_name = user.first_name or user.username or fallback
    return escape_markdown(raw_name)


def _action_text(update_type: str, language: str) -> str:
    """Return localized verb describing an item update."""
    actions_en = {
        "edit": "edited",
        "delete": "deleted",
        "move": "moved"
    }
    actions_ru = {
        "edit": "отредактировал",
        "delete": "удалил",
        "move": "переместил"
    }
    default_en = "updated"
    default_ru = "изменил"
    return translate_text(language, actions_en.get(update_type, default_en), actions_ru.get(update_type, default_ru))

class NotificationScheduler:
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
    
    async def start(self):
        self.running = True
        logger.info("Notification scheduler started")
        
        await self.check_notifications()
        logger.info("Immediate notification check finished")

        while self.running:
            try:
                await self.check_notifications()
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error inside notification scheduler: {e}")
                await asyncio.sleep(300)
    
    async def stop(self):
        self.running = False
        logger.info("Notification scheduler stopped")
    
    async def check_notifications(self):
        async with AsyncSessionLocal() as session:
            await self._check_item_notifications(session)
            await self._check_category_notifications(session)
    
    async def _check_item_notifications(self, session):
        now = datetime.now()
        sent = set()

        for days_before in NOTIFICATION_DAYS_BEFORE:
            target_date = now + timedelta(days=days_before)
            result = await session.execute(
                select(Item, User)
                .join(User, Item.owner_id == User.id)
                .where(
                    or_(
                        and_(
                            Item.date_from >= target_date.replace(hour=0, minute=0, second=0),
                            Item.date_from <= target_date.replace(hour=23, minute=59, second=59)
                        ),
                        and_(
                            Item.date >= target_date.replace(hour=0, minute=0, second=0),
                            Item.date <= target_date.replace(hour=23, minute=59, second=59)
                        )
                    ),
                    Item.notifications_enabled == True,
                    User.notifications_enabled == True
                )
            )
            items_and_users = result.all()
            for item, user in items_and_users:
                key = (user.id, getattr(item, "id", None), days_before)
                if key not in sent:
                    await self._send_item_reminder(user, item, days_before)
                    sent.add(key)
    
    async def _check_category_notifications(self, session):
        now = datetime.now()
        target_date = now + timedelta(days=7)

        result = await session.execute(
            select(Category, User)
            .join(User, Category.owner_id == User.id)
            .where(
                Category.date >= target_date.replace(hour=0, minute=0, second=0),
                Category.date <= target_date.replace(hour=23, minute=59, second=59),
                User.notifications_enabled == True
            )
        )
        categories_and_users = result.all()
        for category, user in categories_and_users:
            await self._send_category_reminder(user, category)
    
    async def _send_item_reminder(self, user: User, item: Item, days_before: int):
        try:
            language = _user_language(user)
            date_val = getattr(item, "date_from", None) or getattr(item, "date", None)
            if not date_val:
                return
            safe_name = escape_markdown(item.name)
            comment_text = ""
            if item.comment:
                comment_text = translate_text(
                    language,
                    f"\n💬 Comment: {escape_markdown(item.comment)}",
                    f"\n💬 Комментарий: {escape_markdown(item.comment)}"
                )
            if days_before == 1:
                text = translate_text(
                    language,
                    "🔔 Reminder!\n\n"
                    f"Tomorrow ({date_val.strftime('%d.%m.%Y')}) you have a scheduled item:\n"
                    f"🎯 **{safe_name}**",
                    "🔔 Напоминание!\n\n"
                    f"Завтра ({date_val.strftime('%d.%m.%Y')}) у вас запланирован элемент:\n"
                    f"🎯 **{safe_name}**"
                )
            else:
                text = translate_text(
                    language,
                    "🔔 Reminder!\n\n"
                    f"In {days_before} days ({date_val.strftime('%d.%m.%Y')}) you have a scheduled item:\n"
                    f"🎯 **{safe_name}**",
                    "🔔 Напоминание!\n\n"
                    f"Через {days_before} дней ({date_val.strftime('%d.%m.%Y')}) у вас запланирован элемент:\n"
                    f"🎯 **{safe_name}**"
                )
            text += comment_text
            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send reminder to user {user.telegram_id}: {e}")
    
    async def _send_category_reminder(self, user: User, category: Category):
        try:
            language = _user_language(user)
            safe_category_name = escape_markdown(category.name)
            text = translate_text(
                language,
                "🔔 Category reminder!\n\n"
                f"In 7 days ({category.date.strftime('%d.%m.%Y')}) this category is due:\n"
                f"📁 **{safe_category_name}**",
                "🔔 Напоминание о категории!\n\n"
                f"Через 7 дней ({category.date.strftime('%d.%m.%Y')}) наступает дата категории:\n"
                f"📁 **{safe_category_name}**"
            )
            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send category reminder to user {user.telegram_id}: {e}")

async def send_item_added_notification(bot: Bot, category: Category, item: Item, user: User):
    try:
        if not category or category.sharing_type not in ["view_only", "collaborative"]:
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(
                    or_(
                        User.id == category.owner_id,
                        User.id.in_(
                            select(SharedCategory.user_id).where(
                                SharedCategory.category_id == category.id
                            )
                        )
                    ),
                    User.id != user.id,
                    User.notifications_enabled == True
                )
            )
            users_to_notify = result.scalars().all()

            for notify_user in users_to_notify:
                try:
                    language = _user_language(notify_user)
                    safe_category_name = escape_markdown(category.name)
                    author_name = _display_name(user, language)
                    item_name = escape_markdown(item.name)
                    text = translate_text(
                        language,
                        "📢 New item in a shared category!\n\n"
                        f"📁 Category: **{safe_category_name}**\n"
                        f"👤 Added by: {author_name}\n"
                        f"🎯 Item: **{item_name}**",
                        "📢 Новый элемент в общей категории!\n\n"
                        f"📁 Категория: **{safe_category_name}**\n"
                        f"👤 Добавил: {author_name}\n"
                        f"🎯 Элемент: **{item_name}**"
                    )
                    
                    if item.photo_file_id:
                        await bot.send_photo(
                            chat_id=notify_user.telegram_id,
                            photo=item.photo_file_id,
                            caption=text,
                            parse_mode="Markdown"
                        )
                    else:
                        await bot.send_message(
                            chat_id=notify_user.telegram_id,
                            text=text,
                            parse_mode="Markdown"
                        )
                except Exception as e:
                    logger.error(f"Failed to notify user {notify_user.telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Error in send_item_added_notification: {e}")

async def send_item_updated_notification(bot: Bot, category: Category, item: Item, user: User, update_type: str):
    try:
        if not category or category.sharing_type not in ["view_only", "collaborative"]:
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(
                    or_(
                        User.id == category.owner_id,
                        User.id.in_(
                            select(SharedCategory.user_id).where(
                                SharedCategory.category_id == category.id
                            )
                        )
                    ),
                    User.id != user.id,
                    User.notifications_enabled == True
                )
            )
            users_to_notify = result.scalars().all()

            for notify_user in users_to_notify:
                try:
                    language = _user_language(notify_user)
                    safe_category_name = escape_markdown(category.name)
                    author_name = _display_name(user, language)
                    item_name = escape_markdown(item.name)
                    action_text = _action_text(update_type, language)
                    text = translate_text(
                        language,
                        "🔄 Shared category update!\n\n"
                        f"📁 Category: **{safe_category_name}**\n"
                        f"👤 {author_name} {action_text} an item:\n"
                        f"🎯 **{item_name}**",
                        "🔄 Изменение в общей категории!\n\n"
                        f"📁 Категория: **{safe_category_name}**\n"
                        f"👤 {author_name} {action_text} элемент:\n"
                        f"🎯 **{item_name}**"
                    )
                    
                    if update_type != "delete" and item.photo_file_id:
                        await bot.send_photo(
                            chat_id=notify_user.telegram_id,
                            photo=item.photo_file_id,
                            caption=text,
                            parse_mode="Markdown"
                        )
                    else:
                        await bot.send_message(
                            chat_id=notify_user.telegram_id,
                            text=text,
                            parse_mode="Markdown"
                        )
                except Exception as e:
                    logger.error(f"Failed to notify user {notify_user.telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Error in send_item_updated_notification: {e}")

async def send_category_shared_notification(bot: Bot, category: Category, owner: User, shared_user: User):
    try:
        language = _user_language(shared_user)
        safe_category_name = escape_markdown(category.name)
        owner_name = _display_name(owner, language)
        access_type_en = "View only" if category.sharing_type == "view_only" else "Edit"
        access_type_ru = "Просмотр" if category.sharing_type == "view_only" else "Редактирование"
        text = translate_text(
            language,
            "🔗 You have been granted access to a category!\n\n"
            f"📁 Category: **{safe_category_name}**\n"
            f"👤 Owner: {owner_name}\n"
            f"🔐 Access type: {access_type_en}",
            "🔗 Вам предоставлен доступ к категории!\n\n"
            f"📁 Категория: **{safe_category_name}**\n"
            f"👤 Владелец: {owner_name}\n"
            f"🔐 Тип доступа: {access_type_ru}"
        )
        
        await bot.send_message(
            chat_id=shared_user.telegram_id,
            text=text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send category access notification to user {shared_user.telegram_id}: {e}")

async def send_category_access_revoked_notification(bot: Bot, category: Category, owner: User, revoked_user: User):
    try:
        language = _user_language(revoked_user)
        safe_category_name = escape_markdown(category.name)
        owner_name = _display_name(owner, language)
        text = translate_text(
            language,
            "❌ Category access revoked!\n\n"
            f"📁 Category: **{safe_category_name}**\n"
            f"👤 Owner: {owner_name}",
            "❌ Доступ к категории отозван!\n\n"
            f"📁 Категория: **{safe_category_name}**\n"
            f"👤 Владелец: {owner_name}"
        )
        
        await bot.send_message(
            chat_id=revoked_user.telegram_id,
            text=text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send access revocation notification to user {revoked_user.telegram_id}: {e}")
