import asyncio
from datetime import datetime, timedelta
from typing import List
from aiogram import Bot
from sqlalchemy import select, or_, and_
from database.models import AsyncSessionLocal, Item, User, Category, SharedCategory
from config import NOTIFICATION_DAYS_BEFORE
from utils.helpers import escape_markdown
import logging

logger = logging.getLogger(__name__)

class NotificationScheduler:
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
    
    async def start(self):
        self.running = True
        logger.info("Планировщик уведомлений запущен")
        
        await self.check_notifications()
        logger.info("⚡ Немедленная проверка уведомлений завершена")

        while self.running:
            try:
                await self.check_notifications()
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Ошибка в планировщике уведомлений: {e}")
                await asyncio.sleep(300)
    
    async def stop(self):
        self.running = False
        logger.info("Планировщик уведомлений остановлен")
    
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
            date_val = getattr(item, "date_from", None) or getattr(item, "date", None)
            if not date_val:
                return
            safe_name = escape_markdown(item.name)
            comment_text = f"\n💬 {escape_markdown(item.comment)}" if item.comment else ""
            if days_before == 1:
                text = f"🔔 Напоминание!\n\n" \
                       f"Завтра ({date_val.strftime('%d.%m.%Y')}) у вас запланирован элемент:\n" \
                       f"🎯 **{safe_name}**"
            else:
                text = f"🔔 Напоминание!\n\n" \
                       f"Через {days_before} дней ({date_val.strftime('%d.%m.%Y')}) у вас запланирован элемент:\n" \
                       f"🎯 **{safe_name}**"
            text += comment_text
            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания пользователю {user.telegram_id}: {e}")
    
    async def _send_category_reminder(self, user: User, category: Category):
        try:
            safe_category_name = escape_markdown(category.name)
            text = f"🔔 Напоминание о категории!\n\n" \
                   f"Через 7 дней ({category.date.strftime('%d.%m.%Y')}) наступает дата категории:\n" \
                   f"📁 **{safe_category_name}**"
            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания о категории пользователю {user.telegram_id}: {e}")

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
                    safe_category_name = escape_markdown(category.name)
                    author_name = escape_markdown(user.first_name or user.username or 'Пользователь')
                    item_name = escape_markdown(item.name)
                    text = (
                        f"📢 Новый элемент в общей категории!\n\n"
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
                    logger.error(f"Ошибка отправки уведомления пользователю {notify_user.telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка в send_item_added_notification: {e}")

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

            update_texts = {
                "edit": "отредактировал",
                "delete": "удалил",
                "move": "переместил"
            }
            action = update_texts.get(update_type, "изменил")

            for notify_user in users_to_notify:
                try:
                    safe_category_name = escape_markdown(category.name)
                    author_name = escape_markdown(user.first_name or user.username or 'Пользователь')
                    item_name = escape_markdown(item.name)
                    text = (
                        f"🔄 Изменение в общей категории!\n\n"
                        f"📁 Категория: **{safe_category_name}**\n"
                        f"👤 {author_name} {action} элемент:\n"
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
                    logger.error(f"Ошибка отправки уведомления пользователю {notify_user.telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка в send_item_updated_notification: {e}")

async def send_category_shared_notification(bot: Bot, category: Category, owner: User, shared_user: User):
    try:
        safe_category_name = escape_markdown(category.name)
        owner_name = escape_markdown(owner.first_name or owner.username or 'Пользователь')
        text = (
            f"🔗 Вам предоставлен доступ к категории!\n\n"
            f"📁 Категория: **{safe_category_name}**\n"
            f"👤 Владелец: {owner_name}\n"
            f"🔐 Тип доступа: {'Просмотр' if category.sharing_type == 'view_only' else 'Редактирование'}"
        )
        
        await bot.send_message(
            chat_id=shared_user.telegram_id,
            text=text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о доступе пользователю {shared_user.telegram_id}: {e}")

async def send_category_access_revoked_notification(bot: Bot, category: Category, owner: User, revoked_user: User):
    try:
        safe_category_name = escape_markdown(category.name)
        owner_name = escape_markdown(owner.first_name or owner.username or 'Пользователь')
        text = (
            f"❌ Доступ к категории отозван!\n\n"
            f"📁 Категория: **{safe_category_name}**\n"
            f"👤 Владелец: {owner_name}"
        )
        
        await bot.send_message(
            chat_id=revoked_user.telegram_id,
            text=text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об отзыве доступа пользователю {revoked_user.telegram_id}: {e}")
