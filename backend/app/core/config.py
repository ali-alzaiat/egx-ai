from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Repo-root .env (shared with docker compose and the Vite proxy), then backend/.env.
    model_config = {
        "env_file": ("../.env", ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    APP_NAME: str = "EGX AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/egx_ai"

    # Connection pool. Tests set DATABASE_NULLPOOL: pytest-asyncio gives each
    # test its own event loop, and pooled asyncpg connections are loop-bound.
    DATABASE_NULLPOOL: bool = False
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # AI Provider
    AI_PROVIDER: str = "ollama"
    AI_MODEL: str = "llama3"
    OPENAI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Market refresh job
    SYNC_JOB_TIMEOUT_SECONDS: int = 1800

    # Auth: shared bearer token (>= 32 chars) required on every API route
    # except health. Empty means every protected request is refused.
    API_TOKEN: str = ""

    # Interactive API docs (/docs, /redoc, /openapi.json) are off unless enabled.
    API_DOCS_ENABLED: bool = False

    # Camelot shells out to Ghostscript, which has a history of exploitable bugs
    # on hostile PDFs; keep it off unless uploads come from trusted sources.
    CAMELOT_ENABLED: bool = False


settings = Settings()
