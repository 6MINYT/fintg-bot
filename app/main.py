import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher

from app.bot.handlers import router
from app.core.config import get_settings
from app.db.session import init_db
from app.services.monthly_digest import run_monthly_digest


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    await init_db()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    monthly_digest_task = asyncio.create_task(run_monthly_digest(bot, settings.tz))

    logging.info("FinTG bot started")
    try:
        await dp.start_polling(bot)
    finally:
        monthly_digest_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monthly_digest_task
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
