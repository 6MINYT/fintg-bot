import asyncio
import logging
from calendar import monthrange
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from aiogram import Bot

from app.db.session import SessionLocal
from app.services.monthly_report import build_monthly_report
from app.services.transactions import list_users


REPORT_TIME = time(hour=20, minute=0)


async def run_monthly_digest(bot: Bot, tz: ZoneInfo) -> None:
    while True:
        target = _next_report_at(datetime.now(tz))
        await asyncio.sleep(max((target - datetime.now(tz)).total_seconds(), 1))
        await send_monthly_digest(bot, target.date())


async def send_monthly_digest(bot: Bot, report_day: date) -> None:
    async with SessionLocal() as session:
        users = await list_users(session)
        for user in users:
            try:
                report = await build_monthly_report(session, user, report_day)
                await bot.send_message(user.telegram_id, report)
            except Exception:
                logging.exception("Failed to send monthly report to user %s", user.telegram_id)

        await session.commit()


def _next_report_at(now: datetime) -> datetime:
    last_day = monthrange(now.year, now.month)[1]
    target = datetime.combine(date(now.year, now.month, last_day), REPORT_TIME, tzinfo=now.tzinfo)
    if now < target:
        return target

    year = now.year + (1 if now.month == 12 else 0)
    month = 1 if now.month == 12 else now.month + 1
    last_day = monthrange(year, month)[1]
    return datetime.combine(date(year, month, last_day), REPORT_TIME, tzinfo=now.tzinfo)
