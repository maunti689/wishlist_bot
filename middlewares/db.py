from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from database.models import AsyncSessionLocal
from database.crud import UserCRUD


class DatabaseMiddleware(BaseMiddleware):
    """Attach DB session and ensure the user object is available."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Create async session via context manager
        async with AsyncSessionLocal() as session:
            try:
                # Expose session to downstream handlers
                data["session"] = session

                # When event is from a user, load their profile
                if hasattr(event, 'from_user') and event.from_user:
                    user = await UserCRUD.get_or_create_user(
                        session=session,
                        telegram_id=event.from_user.id,
                        username=event.from_user.username,
                        first_name=event.from_user.first_name,
                        last_name=event.from_user.last_name
                    )
                    data["user"] = user

                # Proceed with the next handler in the chain
                return await handler(event, data)

            except Exception as e:
                # Roll back on errors so the session stays clean
                await session.rollback()
                raise e
