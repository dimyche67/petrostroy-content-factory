import sys
sys.stdout.write("BOT: module loading...\n")
sys.stdout.flush()

import asyncio
import logging
import socket
import traceback
sys.stdout.write("BOT: stdlib ok\n"); sys.stdout.flush()

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from loguru import logger
sys.stdout.write("BOT: aiogram ok\n"); sys.stdout.flush()

from bot.config import get_settings
sys.stdout.write("BOT: config ok\n"); sys.stdout.flush()
from bot.db.seed import seed_all
from bot.db.session import get_session_factory, init_db
sys.stdout.write("BOT: db ok\n"); sys.stdout.flush()
from bot.handlers import setup_routers
sys.stdout.write("BOT: handlers ok\n"); sys.stdout.flush()
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.ratelimit import RateLimitMiddleware
sys.stdout.write("BOT: all imports ok\n"); sys.stdout.flush()

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, force=True)


async def on_startup() -> None:
    await init_db()
    session_factory = get_session_factory()
    async with session_factory() as session:
        await seed_all(session)
    print("BOT: DB initialized and seeded", flush=True)


async def main() -> None:
    print("BOT: main() started", flush=True)
    settings = get_settings()
    print(f"BOT: token={settings.telegram_token[:15]}...", flush=True)

    session = AiohttpSession()
    session._connector_init["family"] = socket.AF_INET
    bot = Bot(
        token=settings.telegram_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    @dp.errors()
    async def error_handler(event: ErrorEvent) -> None:
        print(f"BOT ERROR: {event.exception}", flush=True)
        traceback.print_exc()

    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.message.middleware(RateLimitMiddleware())

    dp.include_router(setup_routers())

    await on_startup()
    print("BOT: starting polling...", flush=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
