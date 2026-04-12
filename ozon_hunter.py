import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from aiogram import Bot
from curl_cffi.requests import AsyncSession
from dotenv import load_dotenv

load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ozon_hunter")

# Configuration - STRICTLY from environment
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PROXY = os.getenv("PROXY_URL")

# Ozon API constants
OZON_HOME = "https://www.ozon.ru/"
BASE_URL = "https://www.ozon.ru/api/composer-api.bx/v3"
COUPONS_PAGE_URL = f"{BASE_URL}/view/pages/main-coupons"
APPLY_PROMO_URL = f"{BASE_URL}/action/applyPromoCode"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "application/json",
    "X-O3-App-Name": "ozonapp_ios",
    "X-O3-App-Version": "16.36.0",
}

class OzonHunter:
    def __init__(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            raise ValueError("TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set in environment")

        self.session = AsyncSession(
            impersonate="safari18_0_ios",
            headers=HEADERS,
            proxies={"http": PROXY, "https": PROXY} if PROXY else None,
            timeout=30
        )
        self.bot = Bot(token=TELEGRAM_TOKEN)

    async def initialize_session(self):
        """Establish session cookies by visiting the main page."""
        try:
            logger.info("Initializing session via Ozon homepage...")
            # We use the same headers and impersonation to get valid cookies
            resp = await self.session.get(OZON_HOME)
            if resp.status_code == 200:
                logger.info("Session initialized successfully. Cookies: %s", self.session.cookies.get_dict().keys())
            else:
                logger.warning("Failed to initialize session: %d", resp.status_code)
        except Exception as e:
            logger.error("Error during session initialization: %s", e)

    async def fetch_promo_codes(self) -> List[str]:
        """Fetch Ozon's coupon page and extract potential promo codes."""
        try:
            logger.info("Fetching coupons from %s", COUPONS_PAGE_URL)
            response = await self.session.get(COUPONS_PAGE_URL)
            if response.status_code != 200:
                logger.error("Failed to fetch coupons: %d", response.status_code)
                return []

            data = response.json()
            codes = self._extract_codes_recursive(data)
            # Filter unique and likely promo codes
            unique_codes = list(set(c for c in codes if len(c) >= 5))
            logger.info("Extracted %d unique potential codes", len(unique_codes))
            return unique_codes
        except Exception as e:
            logger.error("Error fetching promo codes: %s", e)
            return []

    def _extract_codes_recursive(self, data: Any) -> List[str]:
        """Recursively scan JSON for keys that look like promo codes."""
        codes = []
        if isinstance(data, dict):
            for key in ["promoCode", "code", "couponCode", "id"]:
                if key in data and isinstance(data[key], str):
                    val = data[key].strip()
                    if re.match(r'^[A-Z0-9]{5,20}$', val):
                        codes.append(val)

            for key, value in data.items():
                if key in ["text", "title", "subtitle"] and isinstance(value, str):
                    matches = re.findall(r'\b[A-Z0-9]{5,15}\b', value)
                    codes.extend(matches)

                if isinstance(value, (dict, list)):
                    codes.extend(self._extract_codes_recursive(value))
        elif isinstance(data, list):
            for item in data:
                codes.extend(self._extract_codes_recursive(item))
        return codes

    async def verify_promo_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Verify the promo code via the Ozon action API."""
        try:
            payload = {"code": code}
            logger.info("Verifying code: %s", code)
            response = await self.session.post(APPLY_PROMO_URL, json=payload)

            if response.status_code == 200:
                result = response.json()
                # Check for success indicators in the response
                if result.get("success") is True or result.get("applied") is True or "benefits" in result:
                    return result
            else:
                logger.warning("Verification failed for %s: status %d", code, response.status_code)
            return None
        except Exception as e:
            logger.error("Error verifying code %s: %s", code, e)
            return None

    async def notify(self, code: str, details: Dict[str, Any]):
        """Send a Telegram alert for a valid promo code."""
        message = (
            f"🎯 <b>NEW OZON PROMO CODE FOUND!</b>\n\n"
            f"🎫 Code: <code>{code}</code>\n"
            f"✅ Status: Valid\n"
        )

        if "message" in details:
            message += f"📝 Info: {details['message']}\n"
        elif "benefits" in details:
            message += "🎁 Benefits found in response!\n"

        message += f"\n<a href='https://www.ozon.ru/cart'>Go to Ozon Cart</a>"

        try:
            await self.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode="HTML"
            )
            logger.info("Notification sent for code %s", code)
        except Exception as e:
            logger.error("Failed to send Telegram message: %s", e)

    async def run(self):
        await self.initialize_session()
        codes = await self.fetch_promo_codes()
        for code in codes:
            details = await self.verify_promo_code(code)
            if details:
                await self.notify(code, details)
            await asyncio.sleep(2)

        await self.close()

    async def close(self):
        await self.session.close()
        await self.bot.session.close()

if __name__ == "__main__":
    hunter = OzonHunter()
    try:
        asyncio.run(hunter.run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.critical("Fatal error: %s", e)
