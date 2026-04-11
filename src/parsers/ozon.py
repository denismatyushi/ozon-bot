import asyncio
import json
import logging
import random
import re
from datetime import datetime
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from src.models.product import Product
from src.parsers.base import BaseParser

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

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

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']});
window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : originalQuery(parameters);
"""


def _parse_proxy_url(proxy_url: str) -> dict:
    """Convert proxy URL to Playwright proxy config."""
    parsed = urlparse(proxy_url)
    config: dict = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        config["username"] = parsed.username
    if parsed.password:
        config["password"] = parsed.password
    return config


class OzonParser(BaseParser):
    """Ozon parser — Playwright + proxy to bypass CDN/WAF IP blocking."""

    def __init__(self, max_categories: int = 25, proxy_url: str | None = None):
        self.max_categories = max_categories
        self._proxy_url = proxy_url
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    async def _ensure_page(self):
        if self._page and not self._page.is_closed():
            return self._page

        self._pw = await async_playwright().start()

        launch_args = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        }

        if self._proxy_url:
            launch_args["proxy"] = _parse_proxy_url(self._proxy_url)
            logger.info("Ozon: using proxy %s", self._proxy_url.split("@")[-1])
        else:
            logger.warning(
                "Ozon: no proxy configured (OZON_PROXY_URL). "
                "Ozon blocks cloud IPs — set a proxy with a Russian IP."
            )

        self._browser = await self._pw.chromium.launch(**launch_args)
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        await self._context.add_init_script(_STEALTH_JS)
        self._page = await self._context.new_page()

        # Warmup: visit main page, pass JS challenge, get cookies
        try:
            resp = await self._page.goto(
                "https://www.ozon.ru/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await self._page.wait_for_timeout(3000)
            cookies = await self._context.cookies()
            logger.info(
                "Ozon warmup: status=%s, cookies=%d",
                resp.status if resp else "?", len(cookies),
            )
            if resp and resp.status == 403:
                logger.error(
                    "Ozon warmup got 403 — the IP is blocked. "
                    "Set OZON_PROXY_URL to a proxy with a Russian IP."
                )
        except Exception as exc:
            logger.error("Ozon warmup failed: %s", exc)

        return self._page

    # ── Scanning ────────────────────────────────────────────────

    async def scan_all_categories(self, pages_per_category: int = 1) -> list[Product]:
        all_products: dict[str, Product] = {}

        for cat in OZON_CATEGORIES[: self.max_categories]:
            products = await self._fetch_category(cat, pages_per_category, sorting="discount")
            for p in products:
                all_products[p.product_id] = p

            products = await self._fetch_category(cat, 1, sorting="price")
            for p in products:
                if p.product_id not in all_products:
                    all_products[p.product_id] = p

            await asyncio.sleep(random.uniform(1.5, 3))

        return list(all_products.values())

    async def search_products(self, query: str, max_pages: int = 2) -> list[Product]:
        return []

    async def _fetch_category(
        self, cat: dict, max_pages: int, sorting: str = "discount"
    ) -> list[Product]:
        products: list[Product] = []
        cat_name = cat["name"]

        for page_num in range(1, max_pages + 1):
            url = (
                f"https://www.ozon.ru/category/{cat['slug']}-{cat['id']}"
                f"/?sorting={sorting}&page={page_num}"
            )
            page_products = await self._load_and_extract(url, cat_name)
            products.extend(page_products)
            if not page_products:
                break
            await asyncio.sleep(random.uniform(2, 4))

        if products:
            logger.info("Ozon '%s' (sort=%s): %d products", cat_name, sorting, len(products))
        return products

    # ── Page loading ────────────────────────────────────────────

    async def _load_and_extract(self, url: str, category: str) -> list[Product]:
        page = await self._ensure_page()
        api_items: list[dict] = []

        async def _on_response(response):
            try:
                if response.status != 200:
                    return
                ct = response.headers.get("content-type", "")
                if "json" not in ct:
                    return
                resp_url = response.url
                if "composer-api" not in resp_url and "entrypoint-api" not in resp_url:
                    return
                body = await response.json()
                for key, value in body.get("widgetStates", {}).items():
                    if "searchResultsV2" not in key:
                        continue
                    parsed = json.loads(value) if isinstance(value, str) else value
                    api_items.extend(parsed.get("items", []))
            except Exception:
                pass

        page.on("response", _on_response)
        try:
            products = await self._navigate_and_collect(page, url, category, api_items)
        finally:
            page.remove_listener("response", _on_response)
        return products

    async def _navigate_and_collect(
        self, page, url: str, category: str, api_items: list[dict]
    ) -> list[Product]:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                if resp and resp.status == 403:
                    wait = (2 ** attempt) + random.uniform(2, 5)
                    logger.warning(
                        "Ozon 403 (attempt %d/%d), waiting %.1fs",
                        attempt + 1, MAX_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                try:
                    await page.wait_for_selector(
                        "[data-widget='searchResultsV2']", timeout=8000
                    )
                except Exception:
                    await page.wait_for_timeout(3000)

                # Method 1: intercepted API JSON
                products: list[Product] = []
                for item in api_items:
                    p = self._parse_state_item(item, category)
                    if p:
                        products.append(p)
                if products:
                    return products

                # Method 2: rendered HTML
                html = await page.content()
                products = self._extract_products_from_html(html, category)
                if products:
                    return products

                # Method 3: DOM evaluation
                return await self._extract_via_js(page, category)

            except Exception as exc:
                logger.error("Ozon page error (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, exc)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(random.uniform(2, 4))
                    continue
                return []

        logger.warning("Ozon: retries exhausted for %s", url)
        return []

    # ── Extraction ──────────────────────────────────────────────

    async def _extract_via_js(self, page, category: str) -> list[Product]:
        try:
            raw = await page.evaluate("""() => {
                const cards = document.querySelectorAll('[data-state]');
                const results = [];
                for (const card of cards) {
                    try {
                        const state = JSON.parse(card.getAttribute('data-state'));
                        if (state && state.items) {
                            results.push(...state.items);
                        } else if (state && state.id && state.mainState) {
                            results.push(state);
                        }
                    } catch {}
                }
                return results;
            }""")
            products = []
            for item in raw or []:
                p = self._parse_state_item(item, category)
                if p:
                    products.append(p)
            return products
        except Exception:
            return []

    def _extract_products_from_html(self, html: str, category: str) -> list[Product]:
        products: list[Product] = []

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
                for item in data.get("items", []):
                    product = self._parse_state_item(item, category)
                    if product:
                        products.append(product)
            except (json.JSONDecodeError, KeyError):
                continue

        if products:
            return products

        next_data = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
        )
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
        for resource in (self._page, self._context, self._browser):
            try:
                if resource:
                    await resource.close()
            except Exception:
                pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
        self._page = self._context = self._browser = self._pw = None
