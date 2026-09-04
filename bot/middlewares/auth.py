from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from bot.db.models import User
from bot.db.session import get_session_factory


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        telegram_id = None

        if isinstance(event, Message) and event.from_user:
            telegram_id = event.from_user.id
        elif hasattr(event, "from_user") and event.from_user:
            telegram_id = event.from_user.id
        elif hasattr(event, "message") and event.message and event.message.from_user:
            telegram_id = event.message.from_user.id

        if telegram_id:
            session_factory = get_session_factory()
            async with session_factory() as session:
                user = await session.scalar(
                    select(User).where(
                        User.telegram_id == telegram_id,
                        User.is_active.is_(True),
                    )
                )

        data["db_user"] = user

        if telegram_id and user is None:
            if isinstance(event, Message):
                await event.answer(
                    "⛔ У вас нет доступа к боту. Обратитесь к администратору."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⛔ Нет доступа. Обратитесь к администратору.",
                    show_alert=True,
                )
            return None

        return await handler(event, data)
