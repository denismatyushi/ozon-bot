import logging
import math

from src.models.product import AnomalyResult, Product

logger = logging.getLogger(__name__)


class AnomalyDetector:
    def __init__(
        self,
        threshold_percent: float = 60.0,
        z_score_threshold: float = 2.5,
        iqr_multiplier: float = 2.0,
    ):
        self.threshold_percent = threshold_percent
        self.z_score_threshold = z_score_threshold
        self.iqr_multiplier = iqr_multiplier

    def detect(
        self,
        products: list[Product],
        price_history: dict[str, list[int]] | None = None,
    ) -> list[AnomalyResult]:
        """Run anomaly detection on a batch of products.

        Args:
            products: List of products from current scan.
            price_history: Dict of product_key -> list of historical prices (kopecks).
        """
        if not products:
            return []

        price_history = price_history or {}
        results: list[AnomalyResult] = []

        # Precompute category stats for IQR layer
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

            # Layer 1: Absolute discount threshold
            if product.discount_percent >= self.threshold_percent:
                triggered_layers.append("discount_threshold")

            # Layer 2: Historical z-score
            key = f"{product.source}:{product.product_id}"
            history = price_history.get(key, [])
            if len(history) >= 5:
                mean = sum(history) / len(history)
                std = math.sqrt(sum((x - mean) ** 2 for x in history) / len(history))
                if std > 0:
                    z_score = (product.sale_price - mean) / std
                    if z_score < -self.z_score_threshold:
                        triggered_layers.append("z_score")

            # Layer 3: Category IQR
            cat = product.category or "unknown"
            if cat in category_stats:
                q1, q3, iqr = category_stats[cat]
                iqr_lower = q1 - self.iqr_multiplier * iqr
                if product.sale_price < iqr_lower:
                    triggered_layers.append("category_iqr")

            if triggered_layers:
                confidence = self._compute_confidence(triggered_layers, product)
                results.append(
                    AnomalyResult(
                        product=product,
                        triggered_layers=triggered_layers,
                        discount_percent=product.discount_percent,
                        z_score=z_score,
                        iqr_lower_bound=iqr_lower,
                        confidence=confidence,
                    )
                )

        logger.info("Anomaly detection: %d/%d products flagged", len(results), len(products))
        return results

    def _compute_confidence(self, layers: list[str], product: Product) -> str:
        score = len(layers)
        if product.discount_percent >= 80:
            score += 1
        if product.reviews_count and product.reviews_count > 10:
            score += 1  # Established product with suspiciously low price
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
