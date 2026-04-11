import asyncio
import logging
import sys
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import settings
from src.anomaly.detector import AnomalyDetector
from src.models.product import Product
from src.notifier.telegram import TelegramNotifier
from src.parsers.ozon import OzonParser
from src.parsers.wildberries import WildberriesParser
from src.storage.db import Database

# Logging setup
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _create_components():
    """Create components lazily (not at import time) so env vars are ready."""
    db = Database(settings.DB_PATH)
    detector = AnomalyDetector(
        threshold_percent=settings.ANOMALY_THRESHOLD_PERCENT,
        z_score_threshold=settings.ANOMALY_Z_SCORE_THRESHOLD,
    )
    notifier = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)
    return db, detector, notifier


async def scan_wildberries() -> list[Product]:
    parser = WildberriesParser(
        dest=settings.WB_DEST,
        max_categories=settings.WB_MAX_CATEGORIES,
    )
    try:
        return await parser.scan_all_categories(
            pages_per_category=settings.WB_PAGES_PER_CATEGORY,
        )
    finally:
        await parser.close()


async def scan_ozon() -> list[Product]:
    parser = OzonParser(max_categories=settings.OZON_MAX_CATEGORIES)
    try:
        return await parser.scan_all_categories(
            pages_per_category=settings.OZON_PAGES_PER_CATEGORY,
        )
    finally:
        await parser.close()


async def scan_cycle(db: Database, detector: AnomalyDetector, notifier: TelegramNotifier):
    started_at = datetime.now()
    logger.info("=== Scan cycle started ===")

    try:
        wb_products, ozon_products = await asyncio.gather(
            scan_wildberries(),
            scan_ozon(),
            return_exceptions=True,
        )
    except Exception as e:
        logger.error("Scan failed: %s", e)
        return

    all_products: list[Product] = []
    if isinstance(wb_products, list):
        all_products.extend(wb_products)
        logger.info("WB: %d products collected", len(wb_products))
    else:
        logger.error("WB scan error: %s", wb_products)

    if isinstance(ozon_products, list):
        all_products.extend(ozon_products)
        logger.info("Ozon: %d products collected", len(ozon_products))
    else:
        logger.error("Ozon scan error: %s", ozon_products)

    if not all_products:
        logger.info("No products found, skipping cycle")
        return

    logger.info("Total products: %d", len(all_products))

    price_dicts = [
        {
            "source": p.source,
            "product_id": p.product_id,
            "name": p.name,
            "sale_price": p.sale_price,
            "original_price": p.original_price,
            "fetched_at": p.fetched_at.isoformat(),
        }
        for p in all_products
    ]
    await db.save_prices(price_dicts)

    price_history = await db.get_price_history()
    anomalies = detector.detect(all_products, price_history)
    logger.info("Anomalies detected: %d", len(anomalies))

    notifications_sent = 0
    for anomaly in anomalies:
        p = anomaly.product
        if await db.was_notified(p.source, p.product_id, p.sale_price):
            continue
        await notifier.send_anomaly(anomaly)
        await db.mark_notified(p.source, p.product_id, p.sale_price)
        notifications_sent += 1

    finished_at = datetime.now()
    await db.save_scan_run(
        started_at=started_at,
        finished_at=finished_at,
        products_scanned=len(all_products),
        anomalies_found=len(anomalies),
        notifications_sent=notifications_sent,
    )

    logger.info(
        "=== Scan complete: %d scanned, %d anomalies, %d notified ===",
        len(all_products), len(anomalies), notifications_sent,
    )


async def run_once():
    logger.info("Starting single scan cycle (all categories)")
    logger.info("Token: %s...", settings.TELEGRAM_BOT_TOKEN[:10])
    logger.info("Chat ID: %s", settings.TELEGRAM_CHAT_ID)

    db, detector, notifier = _create_components()
    await db.init()
    try:
        await scan_cycle(db, detector, notifier)
    finally:
        await notifier.close()
        await db.close()


async def run_loop():
    logger.info("Starting Marketplace Price Anomaly Bot (all categories)")
    logger.info("WB categories: %d, Ozon categories: %d",
                settings.WB_MAX_CATEGORIES, settings.OZON_MAX_CATEGORIES)
    logger.info("Scan interval: %d minutes", settings.SCAN_INTERVAL_MINUTES)
    logger.info("Anomaly threshold: %.0f%%", settings.ANOMALY_THRESHOLD_PERCENT)

    db, detector, notifier = _create_components()
    await db.init()

    try:
        await notifier.bot.send_message(
            chat_id=settings.TELEGRAM_CHAT_ID,
            text=(
                "<b>Bot started — scanning ALL categories</b>\n"
                f"WB: {settings.WB_MAX_CATEGORIES} categories\n"
                f"Ozon: {settings.OZON_MAX_CATEGORIES} categories\n"
                f"Scan interval: {settings.SCAN_INTERVAL_MINUTES} min\n"
                f"Threshold: {settings.ANOMALY_THRESHOLD_PERCENT:.0f}%\n"
                f"Cross-marketplace comparison: ON"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Failed to send startup message: %s", e)

    await scan_cycle(db, detector, notifier)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(scan_cycle, "interval", minutes=settings.SCAN_INTERVAL_MINUTES,
                      args=[db, detector, notifier])
    scheduler.start()

    logger.info("Scheduler started, waiting for next cycle...")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        scheduler.shutdown()
        await notifier.close()
        await db.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "loop"
    if mode == "--once":
        asyncio.run(run_once())
    else:
        asyncio.run(run_loop())
