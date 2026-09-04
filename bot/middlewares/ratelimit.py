import time
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from bot.config import get_settings


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._requests: dict[int, list[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        settings = get_settings()
        user_id = event.from_user.id
        now = time.time()
        window_start = now - 60

        self._requests[user_id] = [
            ts for ts in self._requests[user_id] if ts > window_start
        ]

        if len(self._requests[user_id]) >= settings.rate_limit_per_minute:
            await event.answer(
                "⏳ Слишком много запросов. Подождите минуту и попробуйте снова."
            )
            return None

        self._requests[user_id].append(now)
        return await handler(event, data)
