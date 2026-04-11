from datetime import datetime

from pydantic import BaseModel, computed_field


class Product(BaseModel):
    source: str  # "wildberries" | "ozon"
    product_id: str
    name: str
    brand: str | None = None
    original_price: int  # kopecks
    sale_price: int  # kopecks
    url: str
    image_url: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    category: str | None = None
    fetched_at: datetime = datetime.now()

    @computed_field
    @property
    def discount_percent(self) -> float:
        if self.original_price <= 0:
            return 0.0
        return round((1 - self.sale_price / self.original_price) * 100, 1)

    @computed_field
    @property
    def sale_price_rub(self) -> float:
        return self.sale_price / 100

    @computed_field
    @property
    def original_price_rub(self) -> float:
        return self.original_price / 100


class ReferencePrice(BaseModel):
    source: str
    price: int  # kopecks
    url: str | None = None


class CrossRefResult(BaseModel):
    product: Product
    reference_prices: list[ReferencePrice]
    avg_reference_price: float = 0.0
    is_confirmed_anomaly: bool = False


class AnomalyResult(BaseModel):
    product: Product
    triggered_layers: list[str]
    discount_percent: float
    z_score: float | None = None
    iqr_lower_bound: float | None = None
    confidence: str  # "HIGH" | "MEDIUM" | "LOW"
