"""curl_cffi-based HTTP client with chrome124 JA4/TLS impersonation."""
from __future__ import annotations

import logging
from typing import Any

from .stealth import CHROME_UA, CLIENT_HINTS_HEADERS

logger = logging.getLogger(__name__)

try:
    from curl_cffi.requests import AsyncSession  # type: ignore
    CURL_CFFI_AVAILABLE = True
except Exception as e:  # pragma: no cover
    AsyncSession = None  # type: ignore
    CURL_CFFI_AVAILABLE = False
    logger.warning("curl_cffi not available: %s", e)


class ImpersonatedClient:
    """Thin wrapper over curl_cffi.AsyncSession with chrome124 impersonation."""

    def __init__(self, proxy: str | None = None, impersonate: str = "chrome124"):
        self.proxy = proxy
        self.impersonate = impersonate
        self._session: Any = None

    async def __aenter__(self):
        if not CURL_CFFI_AVAILABLE:
            raise RuntimeError("curl_cffi not installed")
        kwargs: dict[str, Any] = {
            "impersonate": self.impersonate,
            "timeout": 30,
        }
        if self.proxy:
            kwargs["proxies"] = {"http": self.proxy, "https": self.proxy}
        self._session = AsyncSession(**kwargs)
        return self

    async def __aexit__(self, *exc):
        try:
            if self._session is not None:
                await self._session.close()
        except Exception:
            pass

    async def get(self, url: str, *, referer: str | None = None,
                  cookies: dict | None = None, extra_headers: dict | None = None) -> Any:
        if self._session is None:
            raise RuntimeError("Client not entered")
        headers = {"user-agent": CHROME_UA, **CLIENT_HINTS_HEADERS}
        if referer:
            headers["referer"] = referer
            headers["sec-fetch-site"] = "same-origin" if "ozon.ru" in referer else "cross-site"
        if extra_headers:
            headers.update(extra_headers)
        return await self._session.get(url, headers=headers, cookies=cookies)
