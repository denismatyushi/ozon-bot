"""Main Ozon parser orchestrator combining all anti-detection layers.

Pipeline per category:
  1. Acquire proxy from ProxyPool (exponential backoff on failure).
  2. Launch Playwright Chromium with stealth context kwargs.
  3. Inject STEALTH_JS before any page JS runs.
  4. Warmup via Yandex (organic referrer → trust).
  5. Navigate to category with human-like mouse/scroll.
  6. Intercept entrypoint-api / composer-api JSON responses.
  7. Parse via selectolax (primary) + API payload (secondary, more reliable).
  8. Optionally replay via curl_cffi (chrome124 impersonation) on 403.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any

from src.models.product import Product
from src.parsers.base import BaseParser

from .categories import OZON_CATEGORIES
from .extractor import extract_from_api_payload, extract_from_html
from .human import bezier_mouse_move, human_viewport_tour, natural_scroll, random_dwell
from .proxy_pool import ProxyPool, ProxyRecord
from .stealth import CHROME_UA, STEALTH_JS, build_context_kwargs
from .trust import warmup_via_yandex

logger = logging.getLogger(__name__)

# Response URL substrings that carry search data
API_RESPONSE_MARKERS = (
    "/composer-api.bx/page/json/v2",
    "/api/entrypoint-api.bx/page/json/v2",
    "/api/composer-api.bx/",
    "searchResultsV2",
)


class OzonParser(BaseParser):
    def __init__(
        self,
        max_categories: int = 25,
        proxy_url: str | None = None,
        proxy_urls: list[str] | None = None,
        pages_per_category: int = 1,
        headless: bool = True,
    ):
        self.max_categories = max_categories
        self.pages_per_category = pages_per_category
        self.headless = headless

        urls: list[str] = []
        if proxy_urls:
            urls.extend(proxy_urls)
        if proxy_url:
            urls.append(proxy_url)
        self.pool = ProxyPool.from_urls(urls)

        self._playwright = None
        self._browser = None

    async def _ensure_playwright(self):
        if self._playwright is None:
            from playwright.async_api import async_playwright  # type: ignore
            self._playwright = await async_playwright().start()

    async def _launch_browser(self, proxy_record: ProxyRecord | None):
        await self._ensure_playwright()
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-size=1536,864",
            "--lang=ru-RU,ru",
            # Makes TCP/IP window/MSS behavior closer to desktop Chrome
            "--enable-features=NetworkService,NetworkServiceInProcess",
        ]
        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": launch_args,
            "chromium_sandbox": False,
        }
        if proxy_record is not None:
            launch_kwargs["proxy"] = {"server": proxy_record.url}
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)

    async def _new_context(self):
        ctx_kwargs = build_context_kwargs()
        ctx = await self._browser.new_context(**ctx_kwargs)
        # Inject stealth BEFORE any page JS runs
        await ctx.add_init_script(STEALTH_JS)
        return ctx

    async def _scan_category_once(self, category: dict, proxy_record: ProxyRecord | None) -> list[Product]:
        cat_id = category["id"]
        cat_name = category["name"]
        slug = category["slug"]
        url = f"https://www.ozon.ru/category/{slug}/"

        await self._launch_browser(proxy_record)
        context = None
        try:
            context = await self._new_context()
            page = await context.new_page()

            # API payload interception
            intercepted: list[Any] = []

            async def on_response(resp):
                try:
                    if any(m in resp.url for m in API_RESPONSE_MARKERS):
                        try:
                            body = await resp.text()
                            if body and body.strip().startswith(("{", "[")):
                                intercepted.append(json.loads(body))
                        except Exception:
                            pass
                except Exception:
                    pass

            page.on("response", lambda r: asyncio.create_task(on_response(r)))

            # Point #3: trust via Yandex SERP (organic referrer)
            warmed = await warmup_via_yandex(page)

            await random_dwell(1.0, 2.2)
            referer = "https://yandex.ru/" if not warmed else None
            if referer:
                await page.set_extra_http_headers({"referer": referer})

            logger.info("Ozon: navigate category '%s' (%s)", cat_name, url)
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            status = resp.status if resp else 0
            if status in (403, 429):
                logger.warning("Ozon returned %d for '%s'", status, cat_name)
                if proxy_record is not None:
                    proxy_record.mark_failure()
                return []

            # Human-like interaction to trigger lazy-load + viewport checks
            await random_dwell(1.0, 2.0)
            await human_viewport_tour(page, n_moves=random.randint(2, 4))
            await natural_scroll(page, total_px=random.randint(1800, 3200))
            await random_dwell(0.8, 1.5)
            await natural_scroll(page, total_px=random.randint(800, 1800))
            await random_dwell(0.6, 1.2)

            html = await page.content()
            products: list[Product] = []

            # 1) Prefer intercepted API payloads (most reliable)
            for payload in intercepted:
                products.extend(extract_from_api_payload(payload, category=cat_name))
            # De-dup
            seen: set[str] = set()
            deduped: list[Product] = []
            for p in products:
                if p.product_id in seen:
                    continue
                seen.add(p.product_id)
                deduped.append(p)

            # 2) Fallback to selectolax HTML extraction
            if len(deduped) < 10:
                html_products = extract_from_html(html, category=cat_name)
                for p in html_products:
                    if p.product_id in seen:
                        continue
                    seen.add(p.product_id)
                    deduped.append(p)

            if deduped and proxy_record is not None:
                proxy_record.mark_success()

            logger.info("Ozon '%s': %d products", cat_name, len(deduped))
            return deduped
        except Exception as e:
            logger.warning("Ozon '%s' failed: %s", cat_name, e)
            if proxy_record is not None:
                proxy_record.mark_failure()
            return []
        finally:
            try:
                if context is not None:
                    await context.close()
            except Exception:
                pass
            try:
                if self._browser is not None:
                    await self._browser.close()
                    self._browser = None
            except Exception:
                pass

    async def _scan_category_with_retries(self, category: dict, max_attempts: int = 3) -> list[Product]:
        for attempt in range(1, max_attempts + 1):
            proxy = self.pool.acquire() if self.pool else None
            products = await self._scan_category_once(category, proxy)
            if products:
                return products
            # Backoff between attempts with jitter
            await asyncio.sleep(random.uniform(3, 8) * attempt)
        return []

    async def scan_all_categories(self, pages_per_category: int = 1) -> list[Product]:
        self.pages_per_category = pages_per_category
        cats = OZON_CATEGORIES[: self.max_categories]
        all_products: list[Product] = []
        for i, cat in enumerate(cats, 1):
            logger.info("Ozon [%d/%d]: %s", i, len(cats), cat["name"])
            products = await self._scan_category_with_retries(cat)
            all_products.extend(products)
            # Gentle pacing between categories
            await asyncio.sleep(random.uniform(4, 10))
        return all_products

    async def search_products(self, query: str, max_pages: int = 3) -> list[Product]:
        # Simple search fallback (not the main path)
        slug = query.strip().lower().replace(" ", "-")
        cat = {"id": "search", "name": query, "slug": f"search/?text={query}"}
        return await self._scan_category_with_retries(cat)

    async def close(self) -> None:
        try:
            if self._browser is not None:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                await self._playwright.stop()
        except Exception:
            pass
        self._browser = None
        self._playwright = None
