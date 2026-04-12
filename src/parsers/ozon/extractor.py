"""High-speed extraction via selectolax + JSON payload scraper (ignores honeypots)."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Iterable

try:
    from selectolax.parser import HTMLParser
except Exception:
    HTMLParser = None  # type: ignore

from src.models.product import Product

logger = logging.getLogger(__name__)


PRICE_RE = re.compile(r"(\d[\d\s\u00a0]*)")


def _parse_price(text: str | None) -> int | None:
    if not text:
        return None
    m = PRICE_RE.search(text.replace("\u2009", " "))
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(1))
    if not digits:
        return None
    try:
        return int(digits) * 100  # kopecks
    except ValueError:
        return None


def _is_hidden(node) -> bool:
    """Honeypot detection — ignore display:none/visibility:hidden/opacity:0/size=0."""
    style = (node.attributes.get("style") or "").lower() if node.attributes else ""
    if "display:none" in style.replace(" ", "") or "visibility:hidden" in style.replace(" ", ""):
        return True
    if "opacity:0" in style.replace(" ", "") and "opacity:0." not in style.replace(" ", ""):
        return True
    cls = (node.attributes.get("class") or "").lower() if node.attributes else ""
    if "hidden" in cls.split():
        return True
    if node.attributes and node.attributes.get("aria-hidden") == "true":
        return True
    return False


def extract_from_html(html: str, category: str | None = None) -> list[Product]:
    """Parse Ozon SERP HTML with selectolax; skip hidden honeypot tiles."""
    if not html or HTMLParser is None:
        return []
    tree = HTMLParser(html)
    products: list[Product] = []
    seen: set[str] = set()

    # Ozon SPA emits tiles with class beginning 'tile-', 'tsBody' or data-widget='searchResultsV2'
    tiles = tree.css('[data-widget="searchResultsV2"] a[href*="/product/"]')
    if not tiles:
        tiles = tree.css('a[href*="/product/"]')

    for anchor in tiles:
        if _is_hidden(anchor):
            continue
        href = anchor.attributes.get("href") or ""
        m = re.search(r"/product/([^/?#]+)-(\d+)", href)
        if not m:
            # Ozon uses /product/<slug>-<id>/ or /product/<id>/
            m2 = re.search(r"/product/[^/]*?-(\d+)", href)
            if not m2:
                continue
            pid = m2.group(1)
        else:
            pid = m.group(2)
        if pid in seen:
            continue

        # Walk up to tile container
        tile = anchor
        for _ in range(6):
            if tile.parent is None:
                break
            tile = tile.parent
            if tile.tag == "body":
                break
        if _is_hidden(tile):
            continue

        # Title: prefer aria-label, then visible text inside
        name = anchor.attributes.get("aria-label") or ""
        if not name:
            txt = anchor.text(strip=True) or ""
            name = txt[:300]
        if not name:
            for span in tile.css("span"):
                if _is_hidden(span):
                    continue
                t = span.text(strip=True) or ""
                if len(t) > 15:
                    name = t[:300]
                    break
        if not name:
            continue

        # Prices: scan spans with digits and "₽"
        sale_price: int | None = None
        orig_price: int | None = None
        for span in tile.css("span"):
            if _is_hidden(span):
                continue
            txt = (span.text(strip=True) or "").replace("\u00a0", " ")
            if "₽" not in txt and "руб" not in txt.lower():
                continue
            price = _parse_price(txt)
            if price is None or price <= 1000:  # < 10 rub is noise
                continue
            # Strikethrough/old price heuristic: look for 'text-decoration: line-through' or class contains 'old'
            style = (span.attributes.get("style") or "").lower()
            cls = (span.attributes.get("class") or "").lower()
            is_old = "line-through" in style or "old" in cls or "strikethrough" in cls
            if is_old:
                if orig_price is None or price > orig_price:
                    orig_price = price
            else:
                if sale_price is None or price < sale_price:
                    sale_price = price

        if sale_price is None:
            continue
        if orig_price is None or orig_price < sale_price:
            orig_price = sale_price

        url = href if href.startswith("http") else f"https://www.ozon.ru{href}"
        seen.add(pid)
        try:
            products.append(Product(
                source="ozon",
                product_id=pid,
                name=name.strip(),
                original_price=orig_price,
                sale_price=sale_price,
                url=url,
                category=category,
                fetched_at=datetime.now(),
            ))
        except Exception as e:
            logger.debug("Skip product %s: %s", pid, e)

    return products


def _walk_json(obj: Any):
    """Yield all dicts in nested structure."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_json(v)


def extract_from_api_payload(payload: Any, category: str | None = None) -> list[Product]:
    """Extract products from intercepted entrypoint-api / composer-api JSON."""
    if payload is None:
        return []

    # Some Ozon responses have payload as string-encoded JSON inside 'state' widgets.
    products: list[Product] = []
    seen: set[str] = set()

    # First pass: try to locate widgetStates / widgets with searchResultsV2
    candidates: list[dict] = []

    def _collect(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and v.strip().startswith(("{", "[")) and "items" in v[:200]:
                    try:
                        parsed = json.loads(v)
                        candidates.append({"widget": k, "data": parsed})
                    except Exception:
                        pass
                _collect(v)
        elif isinstance(obj, list):
            for v in obj:
                _collect(v)

    _collect(payload)

    def _from_item(item: dict):
        pid = str(item.get("sku") or item.get("id") or item.get("productId") or "")
        if not pid or pid in seen:
            return
        name = item.get("title") or item.get("name") or ""
        if isinstance(name, dict):
            name = name.get("text") or ""
        # Price fields vary
        price_node = item.get("price") or item.get("priceV2") or {}
        sale = None
        orig = None
        if isinstance(price_node, dict):
            sale = _parse_price(str(price_node.get("price") or price_node.get("cardPrice") or ""))
            orig = _parse_price(str(price_node.get("originalPrice") or price_node.get("oldPrice") or ""))
        # Flat text prices
        if sale is None:
            for k in ("cardPrice", "price", "mainPrice"):
                v = item.get(k)
                if v:
                    sale = _parse_price(str(v))
                    if sale:
                        break
        if sale is None:
            return
        if orig is None:
            orig = sale
        link = item.get("link") or item.get("deepLink") or item.get("action", {}).get("link") or ""
        if isinstance(link, dict):
            link = link.get("link", "") or ""
        url = link if link.startswith("http") else f"https://www.ozon.ru{link or f'/product/{pid}'}"
        if not name or len(str(name).strip()) < 3:
            return
        seen.add(pid)
        try:
            products.append(Product(
                source="ozon",
                product_id=pid,
                name=str(name).strip()[:300],
                original_price=orig,
                sale_price=sale,
                url=url,
                category=category,
                fetched_at=datetime.now(),
            ))
        except Exception:
            pass

    # Search candidates for items
    for cand in candidates:
        for node in _walk_json(cand["data"]):
            items = node.get("items") if isinstance(node, dict) else None
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        _from_item(it)

    # Fallback: walk the whole raw payload
    if not products:
        for node in _walk_json(payload):
            if isinstance(node, dict) and ("sku" in node or "productId" in node):
                _from_item(node)

    return products
