import pytest
import os
from aiogram.client.session.aiohttp import AiohttpSession

# Set environment variables BEFORE importing settings
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:ABC-DEF"
os.environ["TELEGRAM_CHAT_ID"] = "987654"
os.environ["PROXY_URL"] = "http://user:pass@1.2.3.4:5678"

from config.settings import Settings
from src.notifier.telegram import TelegramNotifier

def test_settings_proxy():
    s = Settings()
    assert s.PROXY_URL == "http://user:pass@1.2.3.4:5678"

@pytest.mark.asyncio
async def test_notifier_proxy_init():
    token = "123456:ABC-DEF"
    chat_id = "987654"
    proxy = "http://1.2.3.4:8080"

    notifier = TelegramNotifier(token, chat_id, proxy_url=proxy)

    assert notifier.bot.session is not None
    assert isinstance(notifier.bot.session, AiohttpSession)
    # In aiogram 3.x AiohttpSession.proxy is accessible
    assert notifier.bot.session.proxy == proxy

    await notifier.close()
