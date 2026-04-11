import asyncio
import logging

from aiogram import Bot

from src.models.product import AnomalyResult, CrossRefResult

logger = logging.getLogger(__name__)

SOURCE_NAMES = {
    "wildberries": "Wildberries",
    "ozon": "Ozon",
}


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id

    async def send_anomaly(
        self,
        anomaly: AnomalyResult,
        crossref: CrossRefResult | None = None,
    ):
        """Send a formatted anomaly alert to Telegram."""
        p = anomaly.product
        source = SOURCE_NAMES.get(p.source, p.source)

        lines = [
            f"<b>ANOMALY: {p.name}</b>",
            "",
            f"Marketplace: {source}",
            f"Current price: {p.sale_price_rub:,.0f} RUB",
            f"Original price: {p.original_price_rub:,.0f} RUB",
            f"Discount: {anomaly.discount_percent:.0f}%",
        ]

        if crossref and crossref.reference_prices:
            avg_rub = crossref.avg_reference_price / 100
            lines.append(f"Avg market price: {avg_rub:,.0f} RUB")

        lines.extend([
            f"Confidence: {anomaly.confidence}",
            f"Triggers: {', '.join(anomaly.triggered_layers)}",
            "",
            f'<a href="{p.url}">Open product</a>',
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

        await asyncio.sleep(1)  # Rate limit: 1 msg/sec

    async def send_scan_summary(
        self,
        products_scanned: int,
        anomalies_found: int,
        notifications_sent: int,
    ):
        """Send a short scan summary."""
        message = (
            f"<b>Scan complete</b>\n"
            f"Products scanned: {products_scanned}\n"
            f"Anomalies found: {anomalies_found}\n"
            f"Notifications sent: {notifications_sent}"
        )
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Failed to send scan summary: %s", e)

    async def close(self):
        await self.bot.session.close()
