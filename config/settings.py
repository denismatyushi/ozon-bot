from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str

    # Wildberries
    WB_DEST: str = "-1257786"
    WB_SEARCH_QUERIES: str = "iphone,samsung,dyson,airpods,playstation"

    # Ozon
    OZON_SEARCH_QUERIES: str = "iphone,samsung,dyson,airpods,playstation"

    # Anomaly detection
    ANOMALY_THRESHOLD_PERCENT: float = 60.0
    ANOMALY_Z_SCORE_THRESHOLD: float = 2.5

    # Scheduling
    SCAN_INTERVAL_MINUTES: int = 10

    # Cross-reference
    CROSSREF_ENABLED: bool = False
    SERPAPI_KEY: str = ""

    # Storage
    DB_PATH: str = "data/prices.db"

    # Logging
    LOG_LEVEL: str = "INFO"

    @property
    def wb_queries_list(self) -> list[str]:
        return [q.strip() for q in self.WB_SEARCH_QUERIES.split(",") if q.strip()]

    @property
    def ozon_queries_list(self) -> list[str]:
        return [q.strip() for q in self.OZON_SEARCH_QUERIES.split(",") if q.strip()]


settings = Settings()
