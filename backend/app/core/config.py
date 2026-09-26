from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    APP_NAME: str = "EGX AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/egx_ai"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # AI Provider
    AI_PROVIDER: str = "ollama"
    AI_MODEL: str = "llama3"
    OPENAI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"


settings = Settings()
