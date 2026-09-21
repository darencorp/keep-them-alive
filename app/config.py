from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    telegram_bot_token: str = ""
    db_path: Path = BASE_DIR / "data" / "keep_them_alive.db"
    timezone: str = "UTC"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
