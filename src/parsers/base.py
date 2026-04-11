from abc import ABC, abstractmethod

from src.models.product import Product


class BaseParser(ABC):
    @abstractmethod
    async def search_products(self, query: str, max_pages: int = 3) -> list[Product]:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
