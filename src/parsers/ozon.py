import asyncio
import json
import logging
import re
from datetime import datetime

import aiohttp

from config.settings import settings
from src.models.product import Product
from src.parsers.base import BaseParser

logger = logging.getLogger(__name__)

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

# Popular Ozon categories
OZON_CATEGORIES = [
    {"id": "15500", "name": "Elektronika", "slug": "elektronika"},
    {"id": "15548", "name": "Smartfony", "slug": "smartfony"},
    {"id": "15549", "name": "Noutbuki", "slug": "noutbuki-15549"},
    {"id": "15553", "name": "Planshety", "slug": "planshety-15553"},
    {"id": "15557", "name": "Naushniki", "slug": "naushniki-15557"},
    {"id": "15621", "name": "Televizory", "slug": "televizory-15621"},
    {"id": "6500", "name": "Bytovaya tekhnika", "slug": "bytovaya-tehnika-6500"},
    {"id": "6501", "name": "Krupnaya bytovaya tekhnika", "slug": "krupnaya-bytovaya-tehnika-6501"},
    {"id": "7000", "name": "Odezhda", "slug": "odezhda-muzhskaya-7000"},
    {"id": "7500", "name": "Obuv", "slug": "obuv-muzhskaya-7500"},
    {"id": "9000", "name": "Dom i sad", "slug": "dom-i-sad-9000"},
    {"id": "6000", "name": "Krasota i zdorovie", "slug": "krasota-i-zdorovie-6000"},
    {"id": "10000", "name": "Sport", "slug": "sport-10000"},
    {"id": "12000", "name": "Detskie tovary", "slug": "detskie-tovary-12000"},
    {"id": "13000", "name": "Produkty pitaniya", "slug": "produkty-pitaniya-13000"},
    {"id": "14000", "name": "Avtotovary", "slug": "avtotovary-14000"},
    {"id": "15000", "name": "Knigi", "slug": "knigi-15000"},
    {"id": "17000", "name": "Igry i konsoli", "slug": "igry-i-konsoli-17000"},
    {"id": "18000", "name": "Kanceltorvary", "slug": "kanctovary-18000"},
    {"id": "9200", "name": "Mebel", "slug": "mebel-9200"},
    {"id": "8000", "name": "Aksessuary", "slug": "aksessuary-8000"},
    {"id": "16000", "name": "Zootovary", "slug": "zootovary-16000"},
    {"id": "40000", "name": "Stroitelstvo i remont", "slug": "stroitelstvo-i-remont-40000"},
    {"id": "15726", "name": "Igrovye noutbuki", "slug": "igrovye-noutbuki-15726"},
    {"id": "15678", "name": "Pylososy", "slug": "pylososy-15678"},
]


class OzonParser(BaseParser):
    """Ozon parser — browses category pages by discount AND by cheapest price."""

    def __init__(self, max_categories: int = 25):
        self.max_categories = max_categories
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=HEADERS)
        return self._session

    async def _request_get(self, session: aiohttp.ClientSession, url: str, **kwargs):
        """Helper to inject proxy into all GET requests."""
        if settings.PROXY_URL:
            kwargs.setdefault("proxy", settings.PROXY_URL)
        return await session.get(url, **kwargs)

    async def scan_all_categories(self, pages_per_category: int = 1) -> list[Product]:
        """Browse Ozon categories by discount and by cheapest price."""
        all_products: dict[str, Product] = {}  # dedup by product_id

        for cat in OZON_CATEGORIES[: self.max_categories]:
            # Pass 1: sorted by discount
            products = await self._fetch_category(cat, pages_per_category, sorting="discount")
            for p in products:
                all_products[p.product_id] = p

            # Pass 2: sorted by cheapest — catches pricing errors
            products = await self._fetch_category(cat, 1, sorting="price")
            for p in products:
                if p.product_id not in all_products:
                    all_products[p.product_id] = p

            await asyncio.sleep(2)

        return list(all_products.values())

    async def search_products(self, query: str, max_pages: int = 2) -> list[Product]:
        return []

    async def _fetch_category(self, cat: dict, max_pages: int, sorting: str = "discount") -> list[Product]:
        session = await self._get_session()
        products: list[Product] = []
        cat_name = cat["name"]

        for page in range(1, max_pages + 1):
            url = f"https://www.ozon.ru/category/{cat['slug']}-{cat['id']}/?sorting={sorting}&page={page}"
            html = await self._fetch_page(session, url)
            if not html:
                break

            page_products = self._extract_products_from_html(html, cat_name)
            products.extend(page_products)

            if not page_products:
                break
            await asyncio.sleep(3)

        if products:
            logger.info("Ozon '%s' (sort=%s): %d products", cat_name, sorting, len(products))
        return products

    async def _fetch_page(self, session: aiohttp.ClientSession, url: str) -> str | None:
        try:
            async with self._request_get(
                session, url, timeout=aiohttp.ClientTimeout(total=20), allow_redirects=True
            ) as resp:
                if resp.status == 403:
                    logger.warning("Ozon blocked request (403)")
                    return None
                if resp.status == 429:
                    logger.warning("Ozon rate limited, waiting 10s...")
                    await asyncio.sleep(10)
                    return None
                if resp.status != 200:
                    logger.error("Ozon error: status %d for %s", resp.status, url)
                    return None
                return await resp.text()
        except Exception as e:
            logger.error("Ozon request failed: %s", e)
            return None

    # ── HTML extraction ─────────────────────────────────────────

    def _extract_products_from_html(self, html: str, category: str) -> list[Product]:
        products: list[Product] = []

        # Strategy 1: data-state JSON blocks
        json_blocks = re.findall(r'data-state="({[^"]*?searchResultsV2[^"]*?})"', html)
        if not json_blocks:
            json_blocks = re.findall(r'data-state="({[^"]*?&quot;items&quot;[^"]*?})"', html)

        for block in json_blocks:
            try:
                block_unescaped = (
                    block.replace("&quot;", '"')
                    .replace("&amp;", "&")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                )
                data = json.loads(block_unescaped)
                items = data.get("items", [])
                for item in items:
                    product = self._parse_state_item(item, category)
                    if product:
                        products.append(product)
            except (json.JSONDecodeError, KeyError):
                continue

        if products:
            return products

        # Strategy 2: __NEXT_DATA__
        next_data = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if next_data:
            try:
                data = json.loads(next_data.group(1))
                products = self._extract_from_next_data(data, category)
                if products:
                    return products
            except json.JSONDecodeError:
                pass

        return []

    def _parse_state_item(self, item: dict, category: str) -> Product | None:
        try:
            main_state = item.get("mainState", [])
            product_id = str(item.get("id", ""))
            if not product_id:
                return None

            name = ""
            sale_price = 0
            original_price = 0

            for atom in main_state:
                if (atom.get("id") == "name" or atom.get("type") == "textAtom") and not name:
                    text = atom.get("atom", {}).get("textAtom", {}).get("text", "")
                    if text:
                        name = text

            for atom in main_state:
                if atom.get("type") == "priceV2":
                    price_data = atom.get("atom", {}).get("priceV2", {})
                    price_list = price_data.get("price", [{}])
                    price_str = price_list[0].get("text", "") if price_list else ""
                    orig_list = price_data.get("originalPrice", [{}])
                    orig_str = orig_list[0].get("text", "") if orig_list else ""

                    sale_price = self._parse_price_string(price_str)
                    original_price = self._parse_price_string(orig_str) if orig_str else sale_price

            if not name or sale_price <= 100:
                return None
            if original_price <= 0:
                original_price = sale_price

            # No discount filter here — we collect ALL products
            # The anomaly detector decides what's anomalous

            return Product(
                source="ozon",
                product_id=product_id,
                name=name,
                original_price=original_price,
                sale_price=sale_price,
                url=f"https://www.ozon.ru/product/{product_id}/",
                category=category,
                fetched_at=datetime.now(),
            )
        except Exception:
            return None

    def _extract_from_next_data(self, data: dict, category: str) -> list[Product]:
        products: list[Product] = []
        self._find_products_recursive(data, products, category, depth=0)
        return products

    def _find_products_recursive(self, obj, products: list, category: str, depth: int):
        if depth > 10:
            return
        if isinstance(obj, dict):
            if "id" in obj and ("price" in obj or "finalPrice" in obj):
                product = self._parse_generic_item(obj, category)
                if product:
                    products.append(product)
            else:
                for v in obj.values():
                    if isinstance(v, (dict, list)):
                        self._find_products_recursive(v, products, category, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    self._find_products_recursive(item, products, category, depth + 1)

    def _parse_generic_item(self, item: dict, category: str) -> Product | None:
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

            return Product(
                source="ozon",
                product_id=product_id,
                name=name,
                original_price=original_price if original_price > 0 else sale_price,
                sale_price=sale_price,
                url=f"https://www.ozon.ru/product/{product_id}/",
                category=category,
                fetched_at=datetime.now(),
            )
        except Exception:
            return None

    @staticmethod
    def _parse_price_string(price_str: str) -> int:
        if not price_str:
            return 0
        cleaned = re.sub(r"[^\d]", "", price_str)
        if not cleaned:
            return 0
        return int(cleaned) * 100

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
