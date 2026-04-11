import logging
import math
import re

from src.models.product import AnomalyResult, Product

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Normalize product name for fuzzy matching between marketplaces."""
    name = name.lower()
    name = re.sub(r"[^a-zа-яё0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _word_set(name: str) -> set[str]:
    """Get significant words from a product name (skip short noise words)."""
    return {w for w in _normalize_name(name).split() if len(w) >= 3}


def _similarity(name_a: str, name_b: str) -> float:
    """Jaccard similarity between word sets of two product names."""
    words_a = _word_set(name_a)
    words_b = _word_set(name_b)
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


class AnomalyDetector:
    def __init__(
        self,
        threshold_percent: float = 60.0,
        z_score_threshold: float = 2.5,
        iqr_multiplier: float = 2.0,
        cross_price_ratio: float = 3.0,
    ):
        self.threshold_percent = threshold_percent
        self.z_score_threshold = z_score_threshold
        self.iqr_multiplier = iqr_multiplier
        self.cross_price_ratio = cross_price_ratio  # flag if other marketplace price is 3x+ higher

    def detect(
        self,
        products: list[Product],
        price_history: dict[str, list[int]] | None = None,
    ) -> list[AnomalyResult]:
        if not products:
            return []

        price_history = price_history or {}
        results: list[AnomalyResult] = []

        # Split products by source for cross-marketplace comparison
        wb_products = [p for p in products if p.source == "wildberries"]
        ozon_products = [p for p in products if p.source == "ozon"]

        # Build cross-marketplace price index
        cross_index = self._build_cross_index(wb_products, ozon_products)

        # Precompute category IQR stats
        category_prices: dict[str, list[int]] = {}
        for p in products:
            cat = p.category or "unknown"
            category_prices.setdefault(cat, []).append(p.sale_price)

        category_stats = {}
        for cat, prices in category_prices.items():
            if len(prices) >= 5:
                category_stats[cat] = self._compute_iqr(prices)

        for product in products:
            triggered_layers: list[str] = []
            z_score = None
            iqr_lower = None
            cross_price = None
            cross_source = None

            # Layer 1: Discount threshold (big sales/mistakes marked as discount)
            if product.discount_percent >= self.threshold_percent:
                triggered_layers.append("discount_threshold")

            # Layer 2: Historical z-score (price dropped vs history)
            key = f"{product.source}:{product.product_id}"
            history = price_history.get(key, [])
            if len(history) >= 5:
                mean = sum(history) / len(history)
                std = math.sqrt(sum((x - mean) ** 2 for x in history) / len(history))
                if std > 0:
                    z_score = (product.sale_price - mean) / std
                    if z_score < -self.z_score_threshold:
                        triggered_layers.append("z_score")

            # Layer 3: Category IQR (outlier vs peers in same category)
            cat = product.category or "unknown"
            if cat in category_stats:
                q1, q3, iqr = category_stats[cat]
                iqr_lower = q1 - self.iqr_multiplier * iqr
                if iqr_lower > 0 and product.sale_price < iqr_lower:
                    triggered_layers.append("category_iqr")

            # Layer 4: Cross-marketplace comparison (PRICING ERROR detection)
            # If similar product on another marketplace costs 3x+ more — likely a mistake
            cross_key = f"{product.source}:{product.product_id}"
            if cross_key in cross_index:
                other = cross_index[cross_key]
                if other.sale_price > product.sale_price * self.cross_price_ratio:
                    triggered_layers.append("cross_marketplace")
                    cross_price = float(other.sale_price)
                    cross_source = other.source

            if triggered_layers:
                confidence = self._compute_confidence(triggered_layers, product)
                results.append(
                    AnomalyResult(
                        product=product,
                        triggered_layers=triggered_layers,
                        discount_percent=product.discount_percent,
                        z_score=z_score,
                        iqr_lower_bound=iqr_lower,
                        cross_marketplace_price=cross_price,
                        cross_marketplace_source=cross_source,
                        confidence=confidence,
                    )
                )

        logger.info("Anomaly detection: %d/%d products flagged", len(results), len(products))
        return results

    def _build_cross_index(
        self,
        wb_products: list[Product],
        ozon_products: list[Product],
    ) -> dict[str, Product]:
        """For each product on one marketplace, find the best match on the other.

        Returns a dict: "source:product_id" -> matching Product from other marketplace.
        Only includes matches where the price difference is significant.
        """
        cross: dict[str, Product] = {}

        # Match WB products against Ozon and vice versa
        for source_list, other_list in [
            (wb_products, ozon_products),
            (ozon_products, wb_products),
        ]:
            for product in source_list:
                best_match = None
                best_sim = 0.0

                for other in other_list:
                    # Same category increases match quality
                    sim = _similarity(product.name, other.name)

                    # Boost if brand matches
                    if (
                        product.brand
                        and other.brand
                        and product.brand.lower() == other.brand.lower()
                    ):
                        sim += 0.2

                    if sim > best_sim and sim >= 0.4:
                        best_sim = sim
                        best_match = other

                if best_match:
                    key = f"{product.source}:{product.product_id}"
                    cross[key] = best_match

        logger.info("Cross-marketplace index: %d matches", len(cross))
        return cross

    def _compute_confidence(self, layers: list[str], product: Product) -> str:
        score = len(layers)
        if "cross_marketplace" in layers:
            score += 1  # Cross-check is strong evidence
        if product.discount_percent >= 80:
            score += 1
        if product.reviews_count and product.reviews_count > 10:
            score += 1
        if score >= 3:
            return "HIGH"
        if score >= 2:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _compute_iqr(prices: list[int]) -> tuple[float, float, float]:
        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        q1 = sorted_prices[n // 4]
        q3 = sorted_prices[3 * n // 4]
        iqr = q3 - q1
        return float(q1), float(q3), float(iqr)
