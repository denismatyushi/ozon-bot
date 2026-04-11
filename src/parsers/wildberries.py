import asyncio
import logging
from datetime import datetime

import aiohttp

from src.models.product import Product
from src.parsers.base import BaseParser

logger = logging.getLogger(__name__)

MENU_URL = "https://static-basket-01.wbbasket.ru/vol0/data/main-menu-ru-ru-v3.json"
CATALOG_URL = "https://catalog.wb.ru/catalog/{shard}/catalog"
SEARCH_URL = "https://search.wb.ru/exactmatch/ru/common/v7/search"

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
    def __init__(self, dest: str = "-1257786", max_categories: int = 50):
        self.dest = dest
        self.max_categories = max_categories
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=HEADERS)
        return self._session

    # ── Public API ──────────────────────────────────────────────

    async def scan_all_categories(self, pages_per_category: int = 2) -> list[Product]:
        """Fetch the WB category tree, then browse each category sorted by discount."""
        categories = await self._fetch_categories()
        if not categories:
            logger.warning("No WB categories fetched, falling back to search")
            return []

        logger.info("WB: loaded %d categories, scanning up to %d", len(categories), self.max_categories)
        all_products: list[Product] = []

        for cat in categories[: self.max_categories]:
            products = await self._fetch_category_products(cat, pages_per_category)
            all_products.extend(products)
            # Polite delay between categories
            await asyncio.sleep(1.0)

        return all_products

    async def search_products(self, query: str, max_pages: int = 3) -> list[Product]:
        """Keyword search — kept as fallback."""
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
                "sort": "sale",
                "spp": "30",
                "suppressSpellcheck": "false",
            }
            items = await self._request_products(session, SEARCH_URL, params)
            if not items:
                break
            for item in items:
                p = self._parse_product(item, query)
                if p:
                    products.append(p)
            logger.info("WB search '%s' page %d: %d items", query, page, len(items))
            await asyncio.sleep(1.5)

        return products

    # ── Category tree ───────────────────────────────────────────

    async def _fetch_categories(self) -> list[dict]:
        """Download WB main menu and extract browsable categories with shard+query."""
        session = await self._get_session()
        try:
            async with session.get(MENU_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.error("WB menu fetch failed: %d", resp.status)
                    return []
                menu = await resp.json(content_type=None)
        except Exception as e:
            logger.error("WB menu request failed: %s", e)
            return []

        categories: list[dict] = []
        self._extract_categories(menu, categories)
        return categories

    def _extract_categories(self, nodes: list | dict, out: list[dict]):
        """Recursively walk the menu tree and collect leaf categories that have shard+query."""
        if isinstance(nodes, dict):
            nodes = [nodes]
        for node in nodes:
            shard = node.get("shard")
            query = node.get("query")
            name = node.get("name", "")
            # Leaf category with catalog params
            if shard and query:
                out.append({"shard": shard, "query": query, "name": name})
            # Recurse into children
            children = node.get("childs") or node.get("nodes") or []
            if children:
                self._extract_categories(children, out)

    # ── Catalog fetching ────────────────────────────────────────

    async def _fetch_category_products(self, cat: dict, max_pages: int) -> list[Product]:
        session = await self._get_session()
        products: list[Product] = []
        shard = cat["shard"]
        cat_name = cat["name"]

        url = CATALOG_URL.format(shard=shard)

        for page in range(1, max_pages + 1):
            params = {
                "appType": "1",
                "curr": "rub",
                "dest": self.dest,
                "page": str(page),
                "sort": "sale",       # sort by discount
                "spp": "30",
                cat["query"].split("=")[0] if "=" in cat["query"] else "cat": (
                    cat["query"].split("=")[1] if "=" in cat["query"] else cat["query"]
                ),
            }
            items = await self._request_products(session, url, params)
            if not items:
                break
            for item in items:
                p = self._parse_product(item, cat_name)
                if p:
                    products.append(p)
            await asyncio.sleep(1.0)

        if products:
            logger.info("WB category '%s': %d products", cat_name, len(products))
        return products

    # ── Shared helpers ──────────────────────────────────────────

    async def _request_products(self, session: aiohttp.ClientSession, url: str, params: dict) -> list[dict]:
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 429:
                    logger.warning("WB rate limited, waiting 5s...")
                    await asyncio.sleep(5)
                    return []
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
        except Exception as e:
            logger.error("WB request failed (%s): %s", url, e)
            return []
        return data.get("data", {}).get("products", [])

    def _parse_product(self, item: dict, category: str) -> Product | None:
        product_id = str(item.get("id", ""))
        if not product_id:
            return None

        name = item.get("name", "")
        brand = item.get("brand", "")
        sale_price = item.get("salePriceU", 0)
        original_price = item.get("priceU", 0)

        if sale_price <= 100:  # > 1 rub
            return None
        if original_price <= 0:
            original_price = sale_price

        # Skip if discount is trivial (< 30%) to save memory
        if original_price > 0:
            discount = (1 - sale_price / original_price) * 100
            if discount < 30:
                return None

        return Product(
            source="wildberries",
            product_id=product_id,
            name=name,
            brand=brand or None,
            original_price=original_price,
            sale_price=sale_price,
            url=f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx",
            rating=item.get("reviewRating") or None,
            reviews_count=item.get("feedbacks") or None,
            category=category,
            fetched_at=datetime.now(),
        )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
