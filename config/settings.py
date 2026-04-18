from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_API_BASE_URL: str | None = None

    # Proxy
    PROXY_URL: str | None = None

    # Storage
    DB_PATH: str = "data/english_school.db"

    # Daily reminder (server time, hour 0-23). Bot nudges students who didn't
    # do their lesson today.
    REMINDER_HOUR: int = 19

    # Logging
    LOG_LEVEL: str = "INFO"


settings = Settings()
