"""Configuration via environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _getenv(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


class Settings:
    """Application settings loaded from environment / .env file."""

    # --- LLM ---
    @property
    def llm_base_url(self) -> str:
        return _getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    @property
    def llm_api_key(self) -> str:
        return _getenv("LLM_API_KEY", "")

    @property
    def llm_model_id(self) -> str:
        return _getenv("LLM_MODEL_ID", "qwen3.6-flash")

    @property
    def llm_timeout(self) -> int:
        try: return int(_getenv("LLM_TIMEOUT", "300"))
        except ValueError: return 300

    @property
    def llm_temperature(self) -> float:
        try: return float(_getenv("LLM_TEMPERATURE", "0.0"))
        except ValueError: return 0.0

    # --- Search ---
    @property
    def search_api(self) -> str:
        return _getenv("SEARCH_API", "tavily")

    @property
    def tavily_api_key(self) -> str:
        return _getenv("TAVILY_API_KEY", "")

    @property
    def max_search_results(self) -> int:
        try: return int(_getenv("MAX_SEARCH_RESULTS", "5"))
        except ValueError: return 5

    # --- Research ---
    @property
    def max_iterations(self) -> int:
        try: return int(_getenv("MAX_RESEARCH_ITERATIONS", "2"))
        except ValueError: return 2

    @property
    def critic_score_threshold(self) -> float:
        try: return float(_getenv("CRITIC_SCORE_THRESHOLD", "4.0"))
        except ValueError: return 4.0

    # --- Postgres ---
    @property
    def pg_host(self) -> str:
        return _getenv("PG_HOST", "localhost")

    @property
    def pg_port(self) -> int:
        try: return int(_getenv("PG_PORT", "5432"))
        except ValueError: return 5432

    @property
    def pg_user(self) -> str:
        return _getenv("PG_USER", "deepresearch")

    @property
    def pg_password(self) -> str:
        return _getenv("PG_PASSWORD", "deepresearch")

    @property
    def pg_database(self) -> str:
        return _getenv("PG_DATABASE", "deepresearch")

    @property
    def pg_dsn(self) -> str:
        return (
            f"postgresql://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_database}"
        )

    # --- Redis ---
    @property
    def redis_host(self) -> str:
        return _getenv("REDIS_HOST", "localhost")

    @property
    def redis_port(self) -> int:
        try: return int(_getenv("REDIS_PORT", "6379"))
        except ValueError: return 6379

    @property
    def redis_cache_ttl(self) -> int:
        """TTL for search cache in seconds (default 1 hour)."""
        try: return int(_getenv("REDIS_CACHE_TTL", "3600"))
        except ValueError: return 3600

    # --- LangSmith ---
    @property
    def langsmith_api_key(self) -> str:
        return _getenv("LANGSMITH_API_KEY", "")

    @property
    def langsmith_project(self) -> str:
        return _getenv("LANGSMITH_PROJECT", "deep-research-agent")

    @property
    def langsmith_enabled(self) -> bool:
        return bool(self.langsmith_api_key)

    # --- Server ---
    @property
    def host(self) -> str:
        return _getenv("HOST", "0.0.0.0")

    @property
    def port(self) -> int:
        try: return int(_getenv("PORT", "8000"))
        except ValueError: return 8000

    @property
    def cors_origins(self) -> list[str]:
        raw = _getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174")
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def log_level(self) -> str:
        return _getenv("LOG_LEVEL", "INFO")


settings = Settings()
