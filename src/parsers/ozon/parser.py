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
import urllib.parse
from typing import Any
from urllib.parse import unquote, urlparse

from src.models.product import Product
from src.parsers.base import BaseParser

from .categories import OZON_CATEGORIES
from .extractor import extract_from_api_payload, extract_from_html
from .http_client import CURL_CFFI_AVAILABLE, ImpersonatedClient
from .human import bezier_mouse_move, human_viewport_tour, natural_scroll, random_dwell
from .proxy_pool import ProxyPool, ProxyRecord
from .stealth import CHROME_UA, CLIENT_HINTS_HEADERS, STEALTH_JS, build_context_kwargs
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

    async def _try_api_first(
        self,
        category: dict,
        proxy_record: ProxyRecord | None,
    ) -> list[Product]:
        """Hit Ozon's composer-api JSON endpoint directly via curl_cffi.

        Strategy:
          1. GET ozon.ru homepage first — lets curl_cffi's session jar collect
             `__Secure-ETC`, `abt_data` and other session cookies that the API
             endpoint checks. Without this step the API returns the same
             Antibot challenge HTML as the regular page load.
          2. GET the composer-api / entrypoint-api JSON endpoints with
             established cookies. These are the same endpoints the frontend
             fires via XHR, and they bypass the JS challenge if the TLS/JA4
             fingerprint matches Chrome (via curl_cffi chrome124 impersonation).
          3. Also try the /search/?text= endpoint as a secondary probe — if
             category page is guarded, search sometimes isn't.

        Returns products on success. On any failure returns [] so the caller
        falls back to Playwright.
        """
        if not CURL_CFFI_AVAILABLE:
            logger.warning("Ozon API-first skipped: curl_cffi not available")
            return []

        slug = category["slug"]
        cat_name = category["name"]
        cat_path = f"/category/{slug}/"

        endpoints = [
            f"https://www.ozon.ru/api/composer-api.bx/page/json/v2?url={cat_path}",
            f"https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url={cat_path}",
            # Search fallback — often less guarded than category pages
            f"https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=/search/?text={urllib.parse.quote(cat_name)}&from_global=true",
        ]

        proxy = proxy_record.url if proxy_record else None
        logger.info(
            "Ozon API-first '%s' [v2] proxy=%s",
            cat_name, "yes" if proxy else "direct",
        )

        extra_headers = {
            "accept": "application/json",
            "accept-language": "ru-RU,ru;q=0.9,en;q=0.8",
            "x-o3-app-name": "dweb_client",
            "x-o3-page-type": "category",
        }

        try:
            async with ImpersonatedClient(proxy=proxy, impersonate="chrome124") as client:
                # Step 1: warm up session cookies
                try:
                    warm = await client.get("https://www.ozon.ru/")
                    wstatus = getattr(warm, "status_code", 0)
                    wtext = getattr(warm, "text", "") or ""
                    is_challenge = (
                        "Antibot" in wtext[:3000] or "abt-complaints" in wtext[:3000]
                    )
                    logger.info(
                        "Ozon API-first '%s' warmup: status=%d len=%d challenge=%s",
                        cat_name, wstatus, len(wtext), is_challenge,
                    )
                    # Even on challenge HTML, cookies might be set — proceed anyway
                except Exception as e:
                    logger.info("Ozon API-first '%s' warmup failed: %s", cat_name, e)

                # Step 2: hit API endpoints with established cookies
                referer = f"https://www.ozon.ru{cat_path}"
                for url in endpoints:
                    try:
                        resp = await client.get(
                            url, referer=referer, extra_headers=extra_headers,
                        )
                        status = getattr(resp, "status_code", 0)
                        text = getattr(resp, "text", "") or ""
                        tag = url.split("?")[0].rsplit("/", 2)[-2:]
                        logger.info(
                            "Ozon API-first '%s' %s: status=%d len=%d",
                            cat_name, "/".join(tag), status, len(text),
                        )
                        if status != 200 or not text:
                            continue
                        if "Antibot" in text[:3000] or "abt-complaints" in text[:3000]:
                            logger.info(
                                "Ozon API-first '%s': got challenge page from API",
                                cat_name,
                            )
                            continue
                        try:
                            payload = json.loads(text)
                        except Exception as e:
                            logger.info(
                                "Ozon API-first '%s': non-JSON body (%s)",
                                cat_name, e,
                            )
                            continue
                        products = extract_from_api_payload(payload, category=cat_name)
                        logger.info(
                            "Ozon API-first '%s': %d products from JSON",
                            cat_name, len(products),
                        )
                        if products:
                            return products
                    except Exception as e:
                        logger.info(
                            "Ozon API-first '%s' endpoint failed: %s",
                            cat_name, e,
                        )
                        continue
        except Exception as e:
            logger.info("Ozon API-first '%s' client failed: %s", cat_name, e)

        return []

    async def _solve_challenge(self, page, url: str, cat_name: str) -> bool:
        """Try several strategies to pass the Antibot challenge.

        Returns True if we're still blocked afterwards, False if we've landed
        on a real (non-challenge) page.
        """
        logger.info("Ozon: solving Antibot challenge for '%s'", cat_name)
        start_url = page.url

        async def _on_real_page() -> bool:
            """Heuristic: are we on a real category page, not a challenge?"""
            try:
                body = await page.content()
                if "Antibot" in body[:3000] or "abt-complaints" in body[:3000]:
                    return False
                # Has at least some category-looking content
                return "/product/" in body or "searchResultsV2" in body
            except Exception:
                return False

        # Strategy 1: wait up to 30s for JS-driven auto-redirect. Perform occasional
        # human activity so the anti-bot watchdog sees engagement.
        deadline = asyncio.get_event_loop().time() + 30
        while asyncio.get_event_loop().time() < deadline:
            await random_dwell(1.5, 3.0)
            try:
                await human_viewport_tour(page, n_moves=random.randint(1, 2))
            except Exception:
                pass
            if page.url != start_url:
                logger.info("Ozon: challenge redirected to %s", page.url)
                break
            if await _on_real_page():
                logger.info("Ozon: challenge resolved in place (%s)", page.url)
                break

        if await _on_real_page():
            try:
                await page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
            return False

        # Strategy 2: try to click any "continue"/"I'm human" button on the challenge page.
        click_selectors = [
            "button:has-text('Продолжить')",
            "button:has-text('Я не робот')",
            "button:has-text('Перейти')",
            "input[type=submit]",
            "a.btn",
            "a[href*='category']",
        ]
        for sel in click_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    logger.info("Ozon: clicking challenge element %s", sel)
                    await el.click(timeout=5_000)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15_000)
                    except Exception:
                        pass
                    break
            except Exception:
                continue

        if await _on_real_page():
            return False

        # Strategy 3: reload the page — cookie set by challenge JS often only
        # takes effect on a fresh request. Keep the same context (same cookies).
        try:
            logger.info("Ozon: reloading after challenge")
            resp = await page.reload(wait_until="domcontentloaded", timeout=45_000)
            await random_dwell(1.5, 3.0)
            if resp and resp.status not in (403, 429):
                return False
            if await _on_real_page():
                return False
        except Exception as e:
            logger.warning("Ozon reload failed: %s", e)

        # Strategy 4: goto original URL fresh with Yandex referer
        try:
            logger.info("Ozon: final retry goto")
            resp = await page.goto(url, wait_until="domcontentloaded",
                                   timeout=45_000, referer="https://yandex.ru/")
            if resp and resp.status not in (403, 429):
                return False
            if await _on_real_page():
                return False
            try:
                body = (await resp.text() or "")[:200] if resp else ""
                logger.warning("Ozon still blocked after all strategies: %s",
                               body.replace("\n", " "))
            except Exception:
                pass
        except Exception as e:
            logger.warning("Ozon final retry failed: %s", e)

        return True  # still blocked

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
                    blocked = await self._solve_challenge(page, url, cat_name)
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
        # Fast path: try Ozon JSON API first via curl_cffi chrome124 impersonation.
        # Attempt with proxy, then direct, before spinning up heavy Playwright.
        api_proxy = self.pool.acquire() if self.pool else None
        products = await self._try_api_first(category, api_proxy)
        if products:
            if api_proxy is not None:
                api_proxy.mark_success()
            return products
        # Try direct (no proxy) if proxy attempt returned nothing
        if api_proxy is not None:
            products = await self._try_api_first(category, None)
            if products:
                return products

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
