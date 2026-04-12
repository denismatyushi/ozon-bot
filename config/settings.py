from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str
    TELEGRAM_API_BASE_URL: str | None = None

    # Proxy
    PROXY_URL: str | None = None

    # Wildberries
    WB_DEST: str = "-1257786"
    WB_MAX_CATEGORIES: int = 50
    WB_PAGES_PER_CATEGORY: int = 2

    # Ozon
    OZON_MAX_CATEGORIES: int = 25
    OZON_PAGES_PER_CATEGORY: int = 1

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


settings = Settings()
