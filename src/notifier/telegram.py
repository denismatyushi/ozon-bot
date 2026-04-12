import asyncio
import logging

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from src.models.product import AnomalyResult, CrossRefResult

logger = logging.getLogger(__name__)

SOURCE_NAMES = {
    "wildberries": "Wildberries",
    "ozon": "Ozon",
}

LAYER_LABELS = {
    "discount_threshold": "Big discount",
    "z_score": "Price drop vs history",
    "category_iqr": "Cheapest in category",
    "cross_marketplace": "Price mismatch between marketplaces",
}


class TelegramNotifier:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        proxy_url: str | None = None,
        api_base_url: str | None = None,
    ):
        session = None
        if proxy_url or api_base_url:
            api = (
                TelegramAPIServer.from_base(api_base_url)
                if api_base_url
                else TelegramAPIServer(
                    base="https://api.telegram.org/bot{token}/{method}",
                    file="https://api.telegram.org/file/bot{token}/{path}",
                )
            )
            session = AiohttpSession(proxy=proxy_url, api=api)

        self.bot = Bot(token=bot_token.strip(), session=session)
        self.chat_id = chat_id.strip()

    async def send_anomaly(
        self,
        anomaly: AnomalyResult,
        crossref: CrossRefResult | None = None,
    ):
        p = anomaly.product
        source = SOURCE_NAMES.get(p.source, p.source)

        # Pick emoji based on what triggered
        if "cross_marketplace" in anomaly.triggered_layers:
            header = "PRICING ERROR"
        elif anomaly.discount_percent >= 80:
            header = "HUGE DISCOUNT"
        else:
            header = "PRICE ANOMALY"

        lines = [
            f"<b>{header}: {p.name}</b>",
            "",
            f"Marketplace: {source}",
            f"Price: {p.sale_price_rub:,.0f} RUB",
        ]

        if p.original_price > p.sale_price:
            lines.append(f"Was: {p.original_price_rub:,.0f} RUB (-{anomaly.discount_percent:.0f}%)")

        # Show cross-marketplace price comparison
        if anomaly.cross_marketplace_price and anomaly.cross_marketplace_source:
            other_source = SOURCE_NAMES.get(anomaly.cross_marketplace_source, anomaly.cross_marketplace_source)
            other_rub = anomaly.cross_marketplace_price / 100
            ratio = other_rub / p.sale_price_rub if p.sale_price_rub > 0 else 0
            lines.append(f"On {other_source}: {other_rub:,.0f} RUB ({ratio:.0f}x more!)")

        if crossref and crossref.reference_prices:
            avg_rub = crossref.avg_reference_price / 100
            lines.append(f"Avg market price: {avg_rub:,.0f} RUB")

        triggers = [LAYER_LABELS.get(t, t) for t in anomaly.triggered_layers]
        lines.extend([
            "",
            f"Confidence: {anomaly.confidence}",
            f"Why: {', '.join(triggers)}",
            "",
            f'<a href="{p.url}">BUY NOW</a>',
        ])

        message = "\n".join(lines)

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
            logger.info("Sent notification for %s:%s", p.source, p.product_id)
        except Exception as e:
            logger.error("Failed to send Telegram message: %s", e)

        await asyncio.sleep(1)

    async def close(self):
        await self.bot.session.close()
