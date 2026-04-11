import asyncio
import logging
from datetime import datetime

import aiohttp

from src.models.product import Product
from src.parsers.base import BaseParser

logger = logging.getLogger(__name__)

SEARCH_URL = "https://search.wb.ru/exactmatch/ru/common/v7/search"
DETAIL_URL = "https://card.wb.ru/cards/v2/detail"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://www.wildberries.ru",
    "Referer": "https://www.wildberries.ru/",
}


class WildberriesParser(BaseParser):
    def __init__(self, dest: str = "-1257786"):
        self.dest = dest
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=HEADERS)
        return self._session

    async def search_products(self, query: str, max_pages: int = 3) -> list[Product]:
        products: list[Product] = []
        session = await self._get_session()

        for page in range(1, max_pages + 1):
            params = {
                "appType": "1",
                "curr": "rub",
                "dest": self.dest,
                "page": str(page),
                "query": query,
                "resultset": "catalog",
                "sort": "popular",
                "spp": "30",
                "suppressSpellcheck": "false",
            }

            try:
                async with session.get(SEARCH_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 429:
                        logger.warning("WB rate limited, waiting 5s...")
                        await asyncio.sleep(5)
                        continue
                    if resp.status != 200:
                        logger.error("WB search error: status %d", resp.status)
                        break

                    data = await resp.json(content_type=None)
            except Exception as e:
                logger.error("WB search request failed: %s", e)
                break

            items = data.get("data", {}).get("products", [])
            if not items:
                break

            for item in items:
                try:
                    product = self._parse_product(item, query)
                    if product and product.sale_price > 100:  # > 1 rub
                        products.append(product)
                except Exception as e:
                    logger.debug("Failed to parse WB product: %s", e)

            logger.info("WB search '%s' page %d: %d products", query, page, len(items))
            await asyncio.sleep(1.5)

        return products

    def _parse_product(self, item: dict, query: str) -> Product | None:
        product_id = str(item.get("id", ""))
        if not product_id:
            return None

        name = item.get("name", "")
        brand = item.get("brand", "")

        # WB prices are in kopecks (divided by 100 = rubles)
        sale_price = item.get("salePriceU", 0)
        original_price = item.get("priceU", 0)

        if sale_price <= 0:
            return None

        # If no original price, use sale price
        if original_price <= 0:
            original_price = sale_price

        url = f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx"

        rating = item.get("reviewRating", 0.0)
        reviews = item.get("feedbacks", 0)

        return Product(
            source="wildberries",
            product_id=product_id,
            name=name,
            brand=brand if brand else None,
            original_price=original_price,
            sale_price=sale_price,
            url=url,
            rating=rating if rating else None,
            reviews_count=reviews if reviews else None,
            category=query,
            fetched_at=datetime.now(),
        )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
