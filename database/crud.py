from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, or_, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from typing import List, Optional
import json
import logging

from .models import User, Category, Item, Tag, Location, SharedCategory
from utils.localization import DEFAULT_LANGUAGE, normalize_language

logger = logging.getLogger(__name__)

class UserCRUD:
    @staticmethod
    async def get_or_create_user(session: AsyncSession, telegram_id: int, **kwargs) -> User:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            language = normalize_language(kwargs.pop("language", DEFAULT_LANGUAGE))
            user = User(telegram_id=telegram_id, language=language, **kwargs)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        elif not getattr(user, "language", None):
            user.language = DEFAULT_LANGUAGE
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user

    @staticmethod
    async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_user_notifications(session: AsyncSession, user_id: int, notifications_enabled: bool):
        await session.execute(
            update(User).where(User.id == user_id).values(notifications_enabled=notifications_enabled)
        )
        await session.commit()

    @staticmethod
    async def update_user_language(session: AsyncSession, user_id: int, language: str):
        language = normalize_language(language)
        await session.execute(
            update(User).where(User.id == user_id).values(language=language)
        )
        await session.commit()

class CategoryCRUD:
    @staticmethod
    async def create_category(session: AsyncSession, name: str, owner_id: int, **kwargs) -> Category:
        category = Category(name=name, owner_id=owner_id, **kwargs)
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category

    @staticmethod
    async def get_user_categories(session: AsyncSession, user_id: int) -> List[Category]:
        # Получаем все категории, доступные пользователю
        query = select(Category).options(selectinload(Category.items)).where(
            or_(
                Category.owner_id == user_id,
                Category.id.in_(
                    select(SharedCategory.category_id).where(SharedCategory.user_id == user_id)
                )
            )
        ).order_by(Category.name)

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_user_editable_categories(session: AsyncSession, user_id: int) -> List[Category]:
        """Категории, где пользователь может редактировать (владелец или can_edit)."""
        query = select(Category).options(selectinload(Category.items)).where(
            or_(
                Category.owner_id == user_id,
                Category.id.in_(
                    select(SharedCategory.category_id).where(
                        and_(
                            SharedCategory.user_id == user_id,
                            SharedCategory.can_edit == True
                        )
                    )
                )
            )
        ).order_by(Category.name)

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_category_by_id(session: AsyncSession, category_id: int) -> Optional[Category]:
        result = await session.execute(select(Category).where(Category.id == category_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_category_by_share_link(session: AsyncSession, share_link: str) -> Optional[Category]:
        result = await session.execute(select(Category).where(Category.share_link == share_link))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_category_sharing(session: AsyncSession, category_id: int, sharing_type: str, share_link: str = None):
        await session.execute(
            update(Category).where(Category.id == category_id).values(sharing_type=sharing_type, share_link=share_link)
        )
        await session.commit()

    @staticmethod
    async def update_category_name(session: AsyncSession, category_id: int, name: str):
        await session.execute(update(Category).where(Category.id == category_id).values(name=name))
        await session.commit()

    @staticmethod
    async def delete_category(session: AsyncSession, category_id: int):
        await session.execute(delete(SharedCategory).where(SharedCategory.category_id == category_id))
        await session.execute(delete(Category).where(Category.id == category_id))
        await session.commit()

    @staticmethod
    async def revoke_all_shares(session: AsyncSession, category_id: int):
        """Удаляет все записи доступа (SharedCategory) для категории."""
        await session.execute(delete(SharedCategory).where(SharedCategory.category_id == category_id))
        await session.commit()

    @staticmethod
    async def get_shared_users_count(session: AsyncSession, category_id: int) -> int:
        result = await session.execute(select(func.count(SharedCategory.id)).where(SharedCategory.category_id == category_id))
        return result.scalar() or 0

    @staticmethod
    async def check_user_access(session: AsyncSession, category_id: int, user_id: int) -> Optional[SharedCategory]:
        result = await session.execute(
            select(SharedCategory).where(
                and_(SharedCategory.category_id == category_id, SharedCategory.user_id == user_id)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def add_user_access(session: AsyncSession, category_id: int, user_id: int, can_edit: bool = False):
        shared_category = SharedCategory(category_id=category_id, user_id=user_id, can_edit=can_edit)
        session.add(shared_category)
        await session.commit()

class ItemCRUD:
    @staticmethod
    async def create_item(session: AsyncSession, **kwargs) -> Item:
        try:
            if 'tags' in kwargs and isinstance(kwargs['tags'], list):
                kwargs['tags'] = json.dumps(kwargs['tags'], ensure_ascii=False)
            item = Item(**kwargs)
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item
        except Exception as e:
            logger.error(f"Ошибка создания элемента: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_user_items(session: AsyncSession, user_id: int) -> List[Item]:
        # Получаем элементы пользователя и из общих категорий
        query = select(Item).options(selectinload(Item.category)).where(
            or_(
                Item.owner_id == user_id,
                Item.category_id.in_(
                    select(SharedCategory.category_id).where(SharedCategory.user_id == user_id)
                )
            )
        ).order_by(Item.created_at.desc())
        
        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_items_accessible_to_user(session: AsyncSession, user_id: int) -> List[Item]:
        result = await session.execute(
            select(Item).options(selectinload(Item.category)).where(
                or_(
                    Item.owner_id == user_id,  # Свои элементы
                    Item.category_id.in_(  # Элементы из доступных категорий
                        select(Category.id).where(
                            or_(
                                Category.owner_id == user_id,
                                Category.id.in_(
                                    select(SharedCategory.category_id).where(
                                        SharedCategory.user_id == user_id
                                    )
                                )
                            )
                        )
                    )
                )
            ).order_by(Item.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_item_by_id(session: AsyncSession, item_id: int) -> Optional[Item]:
        result = await session.execute(
            select(Item).options(selectinload(Item.category)).where(Item.id == item_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_item(session: AsyncSession, item_id: int, **kwargs):
        try:
            if 'tags' in kwargs and isinstance(kwargs['tags'], list):
                kwargs['tags'] = json.dumps(kwargs['tags'], ensure_ascii=False)
            kwargs['updated_at'] = datetime.utcnow()
            await session.execute(update(Item).where(Item.id == item_id).values(**kwargs))
            await session.commit()
        except Exception as e:
            logger.error(f"Ошибка обновления элемента: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def delete_item(session: AsyncSession, item_id: int):
        await session.execute(delete(Item).where(Item.id == item_id))
        await session.commit()

    @staticmethod
    async def add_tags_to_item(session: AsyncSession, item_id: int, tag_names: List[str], user_id: int):
        """Добавляет теги к элементу"""
        try:
            # Получаем элемент
            item = await ItemCRUD.get_item_by_id(session, item_id)
            if not item:
                raise ValueError("Элемент не найден")
            
            # Создаем или получаем теги
            tags = []
            for tag_name in tag_names:
                tag = await TagCRUD.get_or_create_tag(session, tag_name, user_id)
                tags.append(tag)
            
            # Обновляем теги элемента (предполагаем, что в модели Item есть поле tags)
            # Если теги хранятся как JSON строка
            current_tags = json.loads(item.tags) if item.tags else []
            for tag in tags:
                if tag.name not in current_tags:
                    current_tags.append(tag.name)
            
            item.tags = json.dumps(current_tags)
            await session.commit()
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении тегов к элементу: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_items_by_category(session: AsyncSession, category_id: int) -> List[Item]:
        result = await session.execute(
            select(Item).where(Item.category_id == category_id).order_by(Item.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def filter_items(session: AsyncSession, user_id: int, filters: dict) -> List[Item]:
        result = await session.execute(
            select(SharedCategory.category_id).where(SharedCategory.user_id == user_id)
        )
        shared_category_ids = [row[0] for row in result.all()]

        query = select(Item).options(selectinload(Item.category)).where(
            or_(Item.owner_id == user_id, Item.category_id.in_(shared_category_ids))
        )

        if filters.get('category_id'):
            query = query.where(Item.category_id == filters['category_id'])
        if filters.get('tag'):
            # Безопасный поиск по тегам
            query = query.where(Item.tags.ilike(f'%{filters["tag"]}%'))
        if filters.get('price_min'):
            query = query.where(Item.price >= filters['price_min'])
        if filters.get('price_max'):
            query = query.where(Item.price <= filters['price_max'])
        if filters.get('price_exact'):
            query = query.where(Item.price == filters['price_exact'])
        if filters.get('location_type'):
            query = query.where(Item.location_type == filters['location_type'])
        if filters.get('location_value'):
            query = query.where(Item.location_value == filters['location_value'])
        if filters.get('date_from'):
            query = query.where(Item.date_from >= filters['date_from'])
        if filters.get('date_to'):
            query = query.where(
                or_(Item.date_to <= filters['date_to'], and_(Item.date_to.is_(None), Item.date_from <= filters['date_to']))
            )
        if filters.get('product_type'):
            query = query.where(Item.product_type == filters['product_type'])

        query = query.order_by(Item.created_at.desc())
        result = await session.execute(query)
        return result.scalars().all()

class TagCRUD:
    @staticmethod
    async def get_or_create_tag(session: AsyncSession, name: str, user_id: int) -> Tag:
        try:
            clean_name = name.strip().lower()
            if not clean_name:
                raise ValueError("Название тега не может быть пустым")
            
            # Ищем существующий тег
            result = await session.execute(
                select(Tag).where(and_(Tag.name == clean_name, Tag.user_id == user_id))
            )
            tag = result.scalar_one_or_none()
            
            if tag:
                # Увеличиваем счетчик использования
                tag.usage_count += 1
                await session.commit()
            else:
                # Создаем новый тег
                tag = Tag(name=clean_name, user_id=user_id, usage_count=1)
                session.add(tag)
                await session.commit()
                await session.refresh(tag)
            
            return tag
        except Exception as e:
            logger.error(f"Ошибка при работе с тегом '{name}': {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_popular_tags(session: AsyncSession, user_id: int, limit: int = 20) -> List[Tag]:
        try:
            result = await session.execute(
                select(Tag).where(Tag.user_id == user_id)
                .order_by(Tag.usage_count.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Ошибка получения популярных тегов: {e}")
            return []

class LocationCRUD:
    @staticmethod
    async def get_or_create_location(session: AsyncSession, location_type: str, name: str, user_id: int) -> Location:
        try:
            result = await session.execute(
                select(Location).where(
                    and_(
                        Location.location_type == location_type,
                        Location.name == name,
                        Location.user_id == user_id
                    )
                )
            )
            location = result.scalar_one_or_none()
            if location:
                location.usage_count += 1
                await session.commit()
            else:
                location = Location(location_type=location_type, name=name, user_id=user_id)
                session.add(location)
                await session.commit()
                await session.refresh(location)
            return location
        except Exception as e:
            logger.error(f"Ошибка при работе с локацией: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_locations_by_type(session: AsyncSession, location_type: str, user_id: int, limit: int = 10) -> List[Location]:
        try:
            result = await session.execute(
                select(Location)
                .where(and_(Location.location_type == location_type, Location.user_id == user_id))
                .order_by(Location.usage_count.desc()).limit(limit)
            )
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Ошибка получения локаций: {e}")
            return []

    @staticmethod
    async def get_location_by_id(session: AsyncSession, location_id: int) -> Optional[Location]:
        """Получить локацию по id"""
        try:
            result = await session.execute(select(Location).where(Location.id == location_id))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка получения локации по id: {e}")
            return None
