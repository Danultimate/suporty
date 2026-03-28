from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_ENV: str = "production"
    SECRET_KEY: str = "change-me-in-production"
    LOG_LEVEL: str = "INFO"

    # Database (PostgreSQL + pgvector)
    DATABASE_URL: str = "postgresql+asyncpg://supporty:supporty@db:5432/supporty"
    DATABASE_POOL_SIZE: int = 10

    # OpenAI (cloud LLM)
    OPENAI_API_KEY: str = ""
    CLOUD_LLM_MODEL: str = "gpt-4o"

    # Ollama (local LLM)
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    LOCAL_LLM_MODEL: str = "mistral"

    # RAG
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    RAG_TOP_K: int = 5

    # CRM stub
    CRM_API_URL: str = "http://crm-stub:8001"
    CRM_API_KEY: str = ""

    # Confidence threshold below which tickets escalate
    ESCALATION_THRESHOLD: float = 0.75

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
