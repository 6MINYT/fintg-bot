from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PARSER_MODES = {"rules", "rules_then_ollama", "ollama"}


class Settings(BaseSettings):
    bot_token: str
    database_url: str = "postgresql+asyncpg://fintg:fintg@localhost:5432/fintg"
    app_timezone: str = "Europe/Warsaw"
    parser_mode: str = "rules"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_timeout_seconds: int = 20
    admin_telegram_ids: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, value: str) -> str:
        if not value or value == "put-your-telegram-bot-token-here":
            raise ValueError("BOT_TOKEN must be set")
        return value

    @field_validator("parser_mode")
    @classmethod
    def validate_parser_mode(cls, value: str) -> str:
        if value not in PARSER_MODES:
            allowed = ", ".join(sorted(PARSER_MODES))
            raise ValueError(f"PARSER_MODE must be one of: {allowed}")
        return value

    @field_validator("ollama_timeout_seconds")
    @classmethod
    def validate_ollama_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("OLLAMA_TIMEOUT_SECONDS must be greater than 0")
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
