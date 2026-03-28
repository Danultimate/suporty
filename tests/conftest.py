import pytest
import os

# Point to a test env so real services aren't required
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://supporty:supporty@localhost:5432/supporty_test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("CRM_API_URL", "")
os.environ.setdefault("CRM_API_KEY", "")
