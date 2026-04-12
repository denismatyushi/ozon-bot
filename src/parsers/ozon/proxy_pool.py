"""Proxy rotation with exponential backoff and failover."""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProxyRecord:
    url: str
    fail_count: int = 0
    success_count: int = 0
    cooldown_until: float = 0.0  # monotonic
    last_used: float = 0.0

    @property
    def is_available(self) -> bool:
        return time.monotonic() >= self.cooldown_until

    def mark_success(self):
        self.success_count += 1
        self.fail_count = 0
        self.cooldown_until = 0.0
        self.last_used = time.monotonic()

    def mark_failure(self):
        self.fail_count += 1
        # Exponential backoff: 10s, 30s, 90s, 270s, cap 900s
        delay = min(10 * (3 ** (self.fail_count - 1)), 900)
        self.cooldown_until = time.monotonic() + delay
        self.last_used = time.monotonic()
        logger.warning("Proxy %s -> cooldown %.0fs (fail #%d)", self._redact(), delay, self.fail_count)

    def _redact(self) -> str:
        # Hide credentials in logs
        if "@" in self.url:
            scheme, rest = self.url.split("://", 1) if "://" in self.url else ("", self.url)
            host = rest.split("@", 1)[1]
            return f"{scheme}://***@{host}" if scheme else f"***@{host}"
        return self.url


@dataclass
class ProxyPool:
    proxies: list[ProxyRecord] = field(default_factory=list)

    @classmethod
    def from_urls(cls, urls: list[str]) -> "ProxyPool":
        return cls(proxies=[ProxyRecord(url=u.strip()) for u in urls if u and u.strip()])

    def __bool__(self) -> bool:
        return bool(self.proxies)

    def acquire(self) -> ProxyRecord | None:
        """Return the best available proxy (least-recently-used among available)."""
        if not self.proxies:
            return None
        available = [p for p in self.proxies if p.is_available]
        if not available:
            # All on cooldown — pick the one closest to expiring
            return min(self.proxies, key=lambda p: p.cooldown_until)
        # Prefer those with more successes, then least-recently-used
        available.sort(key=lambda p: (-p.success_count, p.last_used))
        # Small random factor so identical records don't hammer one
        top = available[: max(1, len(available) // 2 + 1)]
        return random.choice(top)
