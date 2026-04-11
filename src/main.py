import asyncio
import logging
import sys
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import settings
from src.anomaly.detector import AnomalyDetector
from src.crossref.checker import CrossRefChecker
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

# Components
db = Database(settings.DB_PATH)
detector = AnomalyDetector(
    threshold_percent=settings.ANOMALY_THRESHOLD_PERCENT,
    z_score_threshold=settings.ANOMALY_Z_SCORE_THRESHOLD,
)
notifier = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)
crossref = CrossRefChecker(serpapi_key=settings.SERPAPI_KEY)


async def scan_wildberries() -> list[Product]:
    """Scan Wildberries for products."""
    parser = WildberriesParser(dest=settings.WB_DEST)
    all_products: list[Product] = []

    try:
        for query in settings.wb_queries_list:
            products = await parser.search_products(query, max_pages=2)
            all_products.extend(products)
            logger.info("WB '%s': found %d products", query, len(products))
    finally:
        await parser.close()

    return all_products


async def scan_ozon() -> list[Product]:
    """Scan Ozon for products."""
    parser = OzonParser()
    all_products: list[Product] = []

    try:
        for query in settings.ozon_queries_list:
            products = await parser.search_products(query, max_pages=1)
            all_products.extend(products)
            logger.info("Ozon '%s': found %d products", query, len(products))
    finally:
        await parser.close()

    return all_products


async def scan_cycle():
    """Main scan cycle: fetch, detect, verify, notify."""
    started_at = datetime.now()
    logger.info("=== Scan cycle started ===")

    # 1. Fetch products from both marketplaces concurrently
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
    else:
        logger.error("WB scan error: %s", wb_products)

    if isinstance(ozon_products, list):
        all_products.extend(ozon_products)
    else:
        logger.error("Ozon scan error: %s", ozon_products)

    if not all_products:
        logger.info("No products found, skipping cycle")
        return

    logger.info("Total products fetched: %d", len(all_products))

    # 2. Save prices to history
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

    # 3. Load price history for z-score analysis
    price_history = await db.get_price_history()

    # 4. Detect anomalies
    anomalies = detector.detect(all_products, price_history)
    logger.info("Anomalies detected: %d", len(anomalies))

    # 5. Filter duplicates and verify
    notifications_sent = 0
    for anomaly in anomalies:
        p = anomaly.product

        # Skip if already notified
        if await db.was_notified(p.source, p.product_id, p.sale_price):
            continue

        # Cross-reference if enabled
        crossref_result = None
        if settings.CROSSREF_ENABLED:
            crossref_result = await crossref.verify(anomaly)
            if not crossref_result.is_confirmed_anomaly:
                logger.info("Cross-ref rejected anomaly: %s", p.name)
                continue

        # Send notification
        await notifier.send_anomaly(anomaly, crossref_result)
        await db.mark_notified(p.source, p.product_id, p.sale_price)
        notifications_sent += 1

    # 6. Save scan run stats
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
        len(all_products),
        len(anomalies),
        notifications_sent,
    )


async def run_once():
    """Single scan cycle for GitHub Actions / cron usage."""
    logger.info("Starting single scan cycle")
    logger.info("Anomaly threshold: %.0f%%", settings.ANOMALY_THRESHOLD_PERCENT)
    logger.info("WB queries: %s", settings.wb_queries_list)
    logger.info("Ozon queries: %s", settings.ozon_queries_list)

    await db.init()
    try:
        await scan_cycle()
    finally:
        await crossref.close()
        await notifier.close()
        await db.close()


async def run_loop():
    """Continuous mode with scheduler for local / Codespaces usage."""
    logger.info("Starting Marketplace Price Anomaly Bot")
    logger.info("Scan interval: %d minutes", settings.SCAN_INTERVAL_MINUTES)
    logger.info("Anomaly threshold: %.0f%%", settings.ANOMALY_THRESHOLD_PERCENT)
    logger.info("WB queries: %s", settings.wb_queries_list)
    logger.info("Ozon queries: %s", settings.ozon_queries_list)

    await db.init()

    try:
        await notifier.bot.send_message(
            chat_id=settings.TELEGRAM_CHAT_ID,
            text=(
                "<b>Bot started</b>\n"
                f"Scan interval: {settings.SCAN_INTERVAL_MINUTES} min\n"
                f"Threshold: {settings.ANOMALY_THRESHOLD_PERCENT:.0f}%\n"
                f"WB queries: {', '.join(settings.wb_queries_list)}\n"
                f"Ozon queries: {', '.join(settings.ozon_queries_list)}"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Failed to send startup message: %s", e)

    await scan_cycle()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(scan_cycle, "interval", minutes=settings.SCAN_INTERVAL_MINUTES)
    scheduler.start()

    logger.info("Scheduler started, waiting for next cycle...")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        scheduler.shutdown()
        await crossref.close()
        await notifier.close()
        await db.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "loop"
    if mode == "--once":
        asyncio.run(run_once())
    else:
        asyncio.run(run_loop())
