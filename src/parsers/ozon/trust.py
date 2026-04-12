"""Trust building: warmup via Yandex search so Ozon sees organic referrer."""
from __future__ import annotations

import logging
import random
import urllib.parse

from .human import bezier_mouse_move, human_viewport_tour, natural_scroll, random_dwell

logger = logging.getLogger(__name__)

WARMUP_QUERIES = [
    "ozon скидки",
    "ozon электроника",
    "ozon смартфоны распродажа",
    "ozon ноутбуки купить",
    "маркетплейс ozon",
]


async def warmup_via_yandex(page, timeout_ms: int = 25_000) -> bool:
    """Open Yandex, search, click first Ozon result → page arrives with organic referrer."""
    query = random.choice(WARMUP_QUERIES)
    try:
        search_url = f"https://yandex.ru/search/?text={urllib.parse.quote(query)}"
        logger.info("Trust warmup: Yandex search '%s'", query)
        await page.goto(search_url, wait_until="domcontentloaded", timeout=timeout_ms)
        await random_dwell(1.0, 2.5)
        await human_viewport_tour(page, n_moves=2)
        await natural_scroll(page, total_px=random.randint(400, 900))
        await random_dwell(0.8, 1.8)

        # Find first link to ozon.ru
        link = await page.query_selector("a[href*='ozon.ru']")
        if not link:
            logger.info("No Ozon link on Yandex SERP — navigating directly with Yandex referrer")
            await page.set_extra_http_headers({"referer": "https://yandex.ru/"})
            return False

        box = await link.bounding_box()
        if box:
            await bezier_mouse_move(page, box["x"] + box["width"]/2, box["y"] + box["height"]/2)
            await random_dwell(0.3, 0.9)
        try:
            async with page.expect_navigation(timeout=timeout_ms, wait_until="domcontentloaded"):
                await link.click()
        except Exception as e:
            logger.warning("Yandex → Ozon click failed: %s", e)
            return False

        await random_dwell(1.2, 2.8)
        return True
    except Exception as e:
        logger.warning("Yandex warmup failed: %s", e)
        return False
