import asyncio
import logging
from datetime import datetime

import aiohttp

from src.models.product import Product
from src.parsers.base import BaseParser

logger = logging.getLogger(__name__)

MENU_URL = "https://static-basket-01.wbbasket.ru/vol0/data/main-menu-ru-ru-v3.json"
CATALOG_URL = "https://catalog.wb.ru/catalog/{shard}/catalog"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36"
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

    async def scan_all_categories(self, pages_per_category: int = 2) -> list[Product]:
        """Fetch WB category tree, browse each category by discount AND by cheapest price."""
        categories = await self._fetch_categories()
        if not categories:
            logger.warning("No WB categories fetched")
            return []

        logger.info("WB: loaded %d categories, scanning up to %d", len(categories), self.max_categories)
        all_products: dict[str, Product] = {}  # dedup by product_id

        for cat in categories[: self.max_categories]:
            # Pass 1: sorted by discount — catches big sales
            products = await self._fetch_category_products(cat, pages_per_category, sort="sale")
            for p in products:
                all_products[p.product_id] = p

            # Pass 2: sorted by cheapest price — catches pricing errors
            products = await self._fetch_category_products(cat, 1, sort="priceup")
            for p in products:
                if p.product_id not in all_products:
                    all_products[p.product_id] = p

            await asyncio.sleep(0.5)

        return list(all_products.values())

    async def search_products(self, query: str, max_pages: int = 3) -> list[Product]:
        """Keyword search — kept as fallback."""
        return []

    # ── Category tree ───────────────────────────────────────────

    async def _fetch_categories(self) -> list[dict]:
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
        if isinstance(nodes, dict):
            nodes = [nodes]
        for node in nodes:
            shard = node.get("shard")
            query = node.get("query")
            name = node.get("name", "")
            if shard and query:
                out.append({"shard": shard, "query": query, "name": name})
            children = node.get("childs") or node.get("nodes") or []
            if children:
                self._extract_categories(children, out)

    # ── Catalog fetching ────────────────────────────────────────

    def _parse_query_params(self, query_str: str) -> dict[str, str]:
        """Parse WB query string like 'cat=8126;kind=3' into dict."""
        params: dict[str, str] = {}
        for part in query_str.split(";"):
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                params[key.strip()] = value.strip()
            elif part:
                params["cat"] = part
        return params

    async def _fetch_category_products(
        self, cat: dict, max_pages: int, sort: str = "sale"
    ) -> list[Product]:
        session = await self._get_session()
        products: list[Product] = []
        shard = cat["shard"]
        cat_name = cat["name"]
        url = CATALOG_URL.format(shard=shard)

        # Parse the query params correctly (handles "cat=8126;kind=3" etc.)
        query_params = self._parse_query_params(cat["query"])

        for page in range(1, max_pages + 1):
            params = {
                "appType": "1",
                "curr": "rub",
                "dest": self.dest,
                "page": str(page),
                "sort": sort,
                "spp": "30",
                **query_params,
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
            logger.info("WB '%s' (sort=%s): %d products", cat_name, sort, len(products))
        return products

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

        # Skip garbage: price <= 1 RUB or no name
        if sale_price <= 100 or not name:
            return None
        if original_price <= 0:
            original_price = sale_price

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
