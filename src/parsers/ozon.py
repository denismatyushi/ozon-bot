import asyncio
import json
import logging
import re
from datetime import datetime

import aiohttp

from src.models.product import Product
from src.parsers.base import BaseParser

logger = logging.getLogger(__name__)

# Ozon's internal API used by the frontend
OZON_SEARCH_URL = "https://www.ozon.ru/api/composer-api.bx/page/json/v2"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}


class OzonParser(BaseParser):
    """Ozon parser using HTML scraping with regex extraction.

    Ozon has strong anti-bot protections. This parser uses a lightweight
    approach: fetch the search HTML page and extract product data from
    embedded JSON state (window.__NUXT__ or script tags).
    If this approach gets blocked, switch to Playwright-based parsing.
    """

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=HEADERS)
        return self._session

    async def search_products(self, query: str, max_pages: int = 2) -> list[Product]:
        products: list[Product] = []
        session = await self._get_session()

        for page in range(1, max_pages + 1):
            url = f"https://www.ozon.ru/search/?text={query}&sorting=discount&page={page}"

            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=20),
                    allow_redirects=True,
                ) as resp:
                    if resp.status == 403:
                        logger.warning("Ozon blocked request (403), skipping")
                        break
                    if resp.status == 429:
                        logger.warning("Ozon rate limited, waiting 10s...")
                        await asyncio.sleep(10)
                        continue
                    if resp.status != 200:
                        logger.error("Ozon search error: status %d", resp.status)
                        break

                    html = await resp.text()
            except Exception as e:
                logger.error("Ozon search request failed: %s", e)
                break

            page_products = self._extract_products_from_html(html, query)
            products.extend(page_products)
            logger.info("Ozon search '%s' page %d: %d products", query, page, len(page_products))

            if not page_products:
                break

            await asyncio.sleep(3)

        return products

    def _extract_products_from_html(self, html: str, query: str) -> list[Product]:
        """Try to extract product data from Ozon HTML page.

        Ozon embeds product data in JSON within script tags.
        We try multiple extraction strategies.
        """
        products: list[Product] = []

        # Strategy 1: Find JSON state in script tags
        json_blocks = re.findall(r'data-state="({[^"]*?searchResultsV2[^"]*?})"', html)
        for block in json_blocks:
            try:
                block_unescaped = block.replace("&quot;", '"').replace("&amp;", "&")
                data = json.loads(block_unescaped)
                items = data.get("items", [])
                for item in items:
                    product = self._parse_state_item(item, query)
                    if product:
                        products.append(product)
            except (json.JSONDecodeError, KeyError):
                continue

        if products:
            return products

        # Strategy 2: Extract from __NEXT_DATA__ or similar embedded JSON
        next_data = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if next_data:
            try:
                data = json.loads(next_data.group(1))
                products = self._extract_from_next_data(data, query)
                if products:
                    return products
            except json.JSONDecodeError:
                pass

        # Strategy 3: Basic regex extraction of product cards from HTML
        products = self._extract_with_regex(html, query)
        return products

    def _parse_state_item(self, item: dict, query: str) -> Product | None:
        try:
            main_state = item.get("mainState", [])
            product_id = str(item.get("id", ""))
            if not product_id:
                return None

            name = ""
            sale_price = 0
            original_price = 0

            for atom in main_state:
                atom_id = atom.get("id", "")
                if atom_id == "name" or atom.get("type") == "textAtom":
                    text = atom.get("atom", {}).get("textAtom", {}).get("text", "")
                    if text and not name:
                        name = text

            # Price extraction from mainState
            for atom in main_state:
                if atom.get("type") == "priceV2":
                    price_data = atom.get("atom", {}).get("priceV2", {})
                    price_str = price_data.get("price", [{}])[0].get("text", "")
                    orig_str = price_data.get("originalPrice", [{}])[0].get("text", "") if price_data.get("originalPrice") else ""

                    sale_price = self._parse_price_string(price_str)
                    original_price = self._parse_price_string(orig_str) if orig_str else sale_price

            if not name or sale_price <= 100:
                return None

            url = f"https://www.ozon.ru/product/{product_id}/"

            return Product(
                source="ozon",
                product_id=product_id,
                name=name,
                original_price=original_price if original_price > 0 else sale_price,
                sale_price=sale_price,
                url=url,
                category=query,
                fetched_at=datetime.now(),
            )
        except Exception:
            return None

    def _extract_from_next_data(self, data: dict, query: str) -> list[Product]:
        """Extract products from __NEXT_DATA__ JSON structure."""
        products = []
        # Navigate through various possible paths in __NEXT_DATA__
        try:
            self._find_products_recursive(data, products, query, depth=0)
        except Exception:
            pass
        return products

    def _find_products_recursive(self, obj: dict | list, products: list, query: str, depth: int):
        if depth > 10:
            return
        if isinstance(obj, dict):
            # Check if this looks like a product
            if "id" in obj and ("price" in obj or "finalPrice" in obj):
                product = self._parse_generic_item(obj, query)
                if product:
                    products.append(product)
            else:
                for v in obj.values():
                    if isinstance(v, (dict, list)):
                        self._find_products_recursive(v, products, query, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    self._find_products_recursive(item, products, query, depth + 1)

    def _parse_generic_item(self, item: dict, query: str) -> Product | None:
        try:
            product_id = str(item.get("id", ""))
            name = item.get("title", "") or item.get("name", "")
            if not product_id or not name:
                return None

            sale_price = item.get("finalPrice", 0) or item.get("price", 0)
            original_price = item.get("originalPrice", 0) or item.get("basePrice", 0)

            if isinstance(sale_price, str):
                sale_price = self._parse_price_string(sale_price)
            else:
                sale_price = int(sale_price * 100)

            if isinstance(original_price, str):
                original_price = self._parse_price_string(original_price)
            else:
                original_price = int(original_price * 100)

            if sale_price <= 100:
                return None

            url = f"https://www.ozon.ru/product/{product_id}/"

            return Product(
                source="ozon",
                product_id=product_id,
                name=name,
                original_price=original_price if original_price > 0 else sale_price,
                sale_price=sale_price,
                url=url,
                category=query,
                fetched_at=datetime.now(),
            )
        except Exception:
            return None

    def _extract_with_regex(self, html: str, query: str) -> list[Product]:
        """Last resort: basic regex extraction of product links and prices."""
        products = []

        # Find product links with IDs
        product_links = re.findall(r'href="(/product/[^"]*?-(\d+)/[^"]*?)"', html)

        # Find prices near product contexts
        prices = re.findall(r'(\d[\d\s]*)\s*₽', html)

        # This approach is limited, but provides fallback data
        seen_ids = set()
        for link, pid in product_links[:50]:
            if pid in seen_ids:
                continue
            seen_ids.add(pid)

            # Try to find a name near the link
            name_match = re.search(
                rf'href="{re.escape(link)}"[^>]*>([^<]+)<',
                html,
            )
            name = name_match.group(1).strip() if name_match else f"Ozon product {pid}"

            # We don't have reliable price data from regex, skip items without price
            # This strategy is mainly for capturing product IDs
            products.append(
                Product(
                    source="ozon",
                    product_id=pid,
                    name=name,
                    original_price=0,
                    sale_price=0,
                    url=f"https://www.ozon.ru{link}",
                    category=query,
                    fetched_at=datetime.now(),
                )
            )

        # Filter out products without price (useless for anomaly detection)
        return [p for p in products if p.sale_price > 100]

    @staticmethod
    def _parse_price_string(price_str: str) -> int:
        """Parse a price string like '1 234 ₽' into kopecks."""
        if not price_str:
            return 0
        cleaned = re.sub(r"[^\d]", "", price_str)
        if not cleaned:
            return 0
        return int(cleaned) * 100  # convert rubles to kopecks

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
