from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_token: str = Field(alias="TELEGRAM_TOKEN")
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")

    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/content_factory.db",
        alias="DATABASE_URL",
    )

    require_owner_approval: bool = Field(default=False, alias="REQUIRE_OWNER_APPROVAL")
    rate_limit_per_minute: int = Field(default=5, alias="RATE_LIMIT_PER_MINUTE")

    initial_users: str = Field(default="", alias="INITIAL_USERS")

    vk_community_token: str = Field(default="", alias="VK_COMMUNITY_TOKEN")
    vk_group_id: str = Field(default="", alias="VK_GROUP_ID")

    # Cost estimates (RUB per 1M tokens / per minute audio)
    whisper_cost_per_minute_rub: float = 10.0
    claude_input_cost_per_1m_rub: float = 300.0
    claude_output_cost_per_1m_rub: float = 1500.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


UserRole = Literal["marketer", "foreman", "owner"]
PostMode = Literal["trend", "idea", "voice"]
PostStatus = Literal["draft", "pending_approval", "approved", "published", "rejected"]
TrendStatus = Literal["unused", "used", "planned"]
Platform = Literal["vk", "telegram", "shorts"]
RubricCode = Literal[
    "video_clip",
    "layout",
    "horror",
    "done",
    "expertise",
    "battle",
    "lifehack",
    "team",
    "status",
]
