"""Environment-driven application configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SOLOMON_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8080
    llm_base_url: str = "https://api.openai.com"
    default_model: str = "gpt-4o-mini"
    default_api_key: str = ""
    system_prompt: str = (
        "You are Solomon, a helpful assistant. Keep answers accurate, concise, and actionable."
    )
    skills_dir: str = "skills"
    data_dir: str = "data"
    cors_origin: str = "*"
    request_timeout_seconds: int = 30
    require_auth: bool = False
    app_api_token: str = ""
    session_ttl_seconds: int = 86400


_config: AppConfig | None = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig()
    return _config
