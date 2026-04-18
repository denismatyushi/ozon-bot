"""Entry point — builds the aiogram bot, registers handlers, schedules reminders."""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import settings
from src.handlers import grammar, lesson, placement, progress, settings as settings_h, start, vocab
from src.storage.db import Database

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def build_bot() -> Bot:
    session = None
    if settings.PROXY_URL or settings.TELEGRAM_API_BASE_URL:
        api = (
            TelegramAPIServer.from_base(settings.TELEGRAM_API_BASE_URL)
            if settings.TELEGRAM_API_BASE_URL else None
        )
        if api:
            session = AiohttpSession(proxy=settings.PROXY_URL, api=api)
        else:
            session = AiohttpSession(proxy=settings.PROXY_URL)

    return Bot(
        token=settings.TELEGRAM_BOT_TOKEN.strip(),
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def daily_reminder(bot: Bot, db: Database) -> None:
    """Nudge students who didn't do anything today."""
    users = await db.all_users_with_reminders()
    sent = 0
    for u in users:
        stats = await db.today_stats(u["tg_id"])
        if stats.get("xp", 0) > 0:
            continue
        try:
            await bot.send_message(
                u["tg_id"],
                "🔔 Не забудьте про английский сегодня!\n"
                "5–10 минут в день — и через месяц вы заметите разницу.\n\n"
                "Нажмите /menu, чтобы начать.",
            )
            sent += 1
        except Exception as e:
            logger.warning("Reminder to %s failed: %s", u["tg_id"], e)
    logger.info("Daily reminder sent to %d users", sent)


async def main():
    if not settings.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")

    db = Database(settings.DB_PATH)
    await db.init()

    bot = build_bot()
    dp = Dispatcher(storage=MemoryStorage())
    dp["db"] = db  # injected into handlers via aiogram DI

    dp.include_router(placement.router)
    dp.include_router(vocab.router)
    dp.include_router(grammar.router)
    dp.include_router(lesson.router)
    dp.include_router(progress.router)
    dp.include_router(settings_h.router)
    dp.include_router(start.router)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_reminder, "cron", hour=settings.REMINDER_HOUR, args=[bot, db])
    scheduler.start()

    me = await bot.get_me()
    logger.info("Starting English School Bot as @%s", me.username)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
