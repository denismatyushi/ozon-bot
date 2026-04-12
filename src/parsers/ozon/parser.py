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
import socket
from typing import Any
from urllib.parse import unquote, urlparse

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


def _redact_proxy(url: str) -> str:
    try:
        p = urlparse(url)
        host = p.hostname or ""
        port = f":{p.port}" if p.port else ""
        cred = "***@" if p.username or p.password else ""
        return f"{p.scheme}://{cred}{host}{port}"
    except Exception:
        return "<unparseable>"


async def _proxy_tcp_reachable(url: str, timeout: float = 5.0) -> tuple[bool, str]:
    """Check if we can open a TCP socket to the proxy host:port."""
    try:
        p = urlparse(url)
        host = p.hostname
        port = p.port
        if not host or not port:
            return False, "missing host/port"
        loop = asyncio.get_event_loop()

        def _connect():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            try:
                s.connect((host, port))
                return True, "ok"
            except Exception as e:
                return False, f"{type(e).__name__}: {e}"
            finally:
                try:
                    s.close()
                except Exception:
                    pass

        return await loop.run_in_executor(None, _connect)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _build_playwright_proxy(proxy_url: str) -> dict[str, str]:
    """Parse proxy URL and return Playwright-compatible dict.

    Chromium does NOT accept user:pass@host in the server URL — credentials
    must be passed as separate 'username'/'password' keys, otherwise the
    browser raises ERR_PROXY_CONNECTION_FAILED.
    """
    parsed = urlparse(proxy_url)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or ""
    port = parsed.port
    server = f"{scheme}://{host}" + (f":{port}" if port else "")
    result: dict[str, str] = {"server": server}
    if parsed.username:
        result["username"] = unquote(parsed.username)
    if parsed.password:
        result["password"] = unquote(parsed.password)
    return result


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
            launch_kwargs["proxy"] = _build_playwright_proxy(proxy_record.url)
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
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            status = resp.status if resp else 0
            blocked = status in (403, 429)

            if blocked:
                body = ""
                try:
                    body = await resp.text()
                except Exception:
                    pass
                is_challenge = (
                    "Antibot" in body
                    or "abt-complaints" in body
                    or "challenge" in body.lower()[:2000]
                )
                snippet = (body or "")[:300].replace("\n", " ")
                logger.warning("Ozon %d (challenge=%s): %s", status, is_challenge, snippet)

                if is_challenge:
                    # Solve Ozon Antibot challenge: let JS compute token + set cookie,
                    # generate some user activity, then retry navigation.
                    logger.info("Ozon: solving Antibot challenge for '%s'", cat_name)
                    # 1) Let challenge JS finish
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15_000)
                    except Exception:
                        pass
                    await random_dwell(2.0, 4.0)
                    # 2) Human activity — challenge JS often watches for real mouse events
                    await human_viewport_tour(page, n_moves=random.randint(3, 5))
                    await random_dwell(1.0, 2.5)

                    current = page.url
                    # Auto-redirect to ?__rr=N means Ozon validated our token and
                    # navigated us to the real target — STAY THERE, don't reload.
                    auto_redirected = (
                        "ozon.ru" in current
                        and "abt" not in current
                        and current.rstrip("/") != url.rstrip("/")
                    )
                    if auto_redirected:
                        logger.info("Ozon: challenge passed, staying on %s", current)
                        blocked = False
                        # Let dynamic content finish populating
                        try:
                            await page.wait_for_load_state("networkidle", timeout=10_000)
                        except Exception:
                            pass
                    else:
                        # Still on the challenge page — retry clean URL; cookie should ride
                        logger.info("Ozon: re-navigating after challenge")
                        try:
                            resp2 = await page.goto(
                                url, wait_until="domcontentloaded",
                                timeout=60_000, referer="https://yandex.ru/",
                            )
                            status = resp2.status if resp2 else 0
                            logger.info("Ozon: retry status=%d, final URL=%s", status, page.url)
                            if status not in (403, 429):
                                blocked = False
                            else:
                                try:
                                    body2 = (await resp2.text() or "")[:200]
                                    logger.warning("Ozon still blocked after challenge: %s",
                                                   body2.replace("\n", " "))
                                except Exception:
                                    pass
                        except Exception as e:
                            logger.warning("Ozon retry after challenge failed: %s", e)
                else:
                    # Hard block — give a grace period anyway in case of partial challenge
                    try:
                        await page.wait_for_load_state("networkidle", timeout=8_000)
                    except Exception:
                        pass
                    await random_dwell(2.0, 4.0)

            # Human-like interaction to trigger lazy-load + viewport checks
            await random_dwell(1.0, 2.0)
            await human_viewport_tour(page, n_moves=random.randint(2, 4))
            await natural_scroll(page, total_px=random.randint(1800, 3200))
            await random_dwell(0.8, 1.5)
            await natural_scroll(page, total_px=random.randint(800, 1800))
            await random_dwell(0.6, 1.2)

            # Give product tiles a bit more time to populate (lazy-load after scroll)
            try:
                await page.wait_for_load_state("networkidle", timeout=8_000)
            except Exception:
                pass

            html = await page.content()
            has_widget = '"searchResultsV2"' in html or "searchResultsV2" in html
            has_product_links = "/product/" in html
            logger.info(
                "Ozon '%s' page ready: html=%d bytes, API payloads=%d, "
                "has_widget=%s, has_product_links=%s, url=%s",
                cat_name, len(html), len(intercepted), has_widget, has_product_links, page.url,
            )
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
            elif not deduped and blocked and proxy_record is not None:
                # Still got 403 and no data — burn the proxy slot
                proxy_record.mark_failure()

            logger.info("Ozon '%s': %d products%s", cat_name, len(deduped),
                        " (from blocked page)" if deduped and blocked else "")
            return deduped
        except Exception as e:
            msg = str(e)
            logger.warning("Ozon '%s' failed: %s", cat_name, msg)
            if proxy_record is not None:
                proxy_record.mark_failure()
            # Re-raise only connection-level proxy failures so caller can fallback to direct
            if "ERR_PROXY_CONNECTION_FAILED" in msg or "ERR_TUNNEL_CONNECTION_FAILED" in msg:
                raise RuntimeError("proxy_unreachable") from e
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
        proxy_unreachable_streak = 0
        for attempt in range(1, max_attempts + 1):
            # After 2 consecutive proxy connection failures, try without proxy
            use_proxy = proxy_unreachable_streak < 2
            proxy = self.pool.acquire() if (self.pool and use_proxy) else None
            if not use_proxy:
                logger.warning("Ozon '%s' attempt %d: direct connection (proxy unreachable)",
                               category["name"], attempt)
            try:
                products = await self._scan_category_once(category, proxy)
                proxy_unreachable_streak = 0
                if products:
                    return products
            except RuntimeError as e:
                if str(e) == "proxy_unreachable":
                    proxy_unreachable_streak += 1
                else:
                    raise
            # Backoff between attempts with jitter
            await asyncio.sleep(random.uniform(3, 8) * attempt)
        return []

    async def _preflight_proxy_check(self) -> None:
        """Test each proxy at TCP level; disable unreachable ones before scan."""
        if not self.pool:
            logger.info("Ozon: no proxy configured — direct connection")
            return
        healthy: list[ProxyRecord] = []
        for rec in self.pool.proxies:
            parsed = _build_playwright_proxy(rec.url)
            logger.info("Ozon: testing proxy %s (scheme=%s, auth=%s)",
                        _redact_proxy(rec.url),
                        urlparse(rec.url).scheme,
                        bool(parsed.get("username")))
            ok, info = await _proxy_tcp_reachable(rec.url)
            if ok:
                logger.info("  -> reachable")
                healthy.append(rec)
            else:
                logger.warning("  -> UNREACHABLE: %s", info)
        if not healthy:
            logger.error(
                "Ozon: no healthy proxies — running DIRECT. "
                "Check OZON_PROXY_URL: credentials, scheme (http/socks5), "
                "port, and whether proxy whitelists runner IP."
            )
            self.pool = ProxyPool(proxies=[])
        else:
            self.pool = ProxyPool(proxies=healthy)
            logger.info("Ozon: %d/%d proxies healthy", len(healthy),
                        len(healthy) + (len(self.pool.proxies) - len(healthy)))

    async def scan_all_categories(self, pages_per_category: int = 1) -> list[Product]:
        self.pages_per_category = pages_per_category
        await self._preflight_proxy_check()
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
