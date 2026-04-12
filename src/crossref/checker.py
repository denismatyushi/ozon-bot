import logging
import re

import aiohttp

from config.settings import settings
from src.models.product import AnomalyResult, CrossRefResult, ReferencePrice

logger = logging.getLogger(__name__)


class CrossRefChecker:
    """Cross-reference prices with external sources to verify anomalies."""

    def __init__(self, serpapi_key: str = ""):
        self.serpapi_key = serpapi_key
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _request_get(self, session: aiohttp.ClientSession, url: str, **kwargs):
        """Helper to inject proxy into all GET requests."""
        if settings.PROXY_URL:
            kwargs.setdefault("proxy", settings.PROXY_URL)
        return await session.get(url, **kwargs)

    async def verify(self, anomaly: AnomalyResult) -> CrossRefResult:
        """Verify an anomaly by checking prices on other sources."""
        product = anomaly.product
        ref_prices: list[ReferencePrice] = []

        # Try SerpApi Google Shopping if key is available
        if self.serpapi_key:
            serpapi_prices = await self._search_serpapi(product.name)
            ref_prices.extend(serpapi_prices)

        # Calculate if anomaly is confirmed
        avg_ref = 0.0
        is_confirmed = False

        if ref_prices:
            avg_ref = sum(p.price for p in ref_prices) / len(ref_prices)
            # Confirmed if sale price is less than 40% of average reference
            if avg_ref > 0 and product.sale_price < avg_ref * 0.4:
                is_confirmed = True
        else:
            # No reference data - can't confirm, but still flag
            is_confirmed = True  # Pass through if no cross-ref data

        return CrossRefResult(
            product=product,
            reference_prices=ref_prices,
            avg_reference_price=avg_ref,
            is_confirmed_anomaly=is_confirmed,
        )

    async def _search_serpapi(self, product_name: str) -> list[ReferencePrice]:
        """Search Google Shopping via SerpApi."""
        session = await self._get_session()
        prices: list[ReferencePrice] = []

        try:
            params = {
                "engine": "google_shopping",
                "q": product_name,
                "gl": "ru",
                "hl": "ru",
                "api_key": self.serpapi_key,
            }
            async with self._request_get(
                session,
                "https://serpapi.com/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.warning("SerpApi returned status %d", resp.status)
                    return prices

                data = await resp.json()

            for result in data.get("shopping_results", [])[:10]:
                price_val = result.get("extracted_price")
                if price_val and isinstance(price_val, (int, float)):
                    prices.append(
                        ReferencePrice(
                            source=result.get("source", "google_shopping"),
                            price=int(price_val * 100),  # to kopecks
                            url=result.get("link"),
                        )
                    )
        except Exception as e:
            logger.error("SerpApi search failed: %s", e)

        return prices

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
