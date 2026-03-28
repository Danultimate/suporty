.PHONY: help up down build logs test index-docs shell-db pull-model

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  up          Start all services"
	@echo "  down        Stop all services"
	@echo "  build       Rebuild the app image"
	@echo "  logs        Tail app logs"
	@echo "  test        Run test suite (no Docker needed)"
	@echo "  index-docs  Index docs/ into pgvector (requires .env)"
	@echo "  pull-model  Pull the Ollama model into the running container"
	@echo "  shell-db    Open a psql shell into the database container"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build --no-cache app

logs:
	docker compose logs -f app

test:
	pytest tests/ -v --tb=short

index-docs:
	@echo "Indexing docs/ → pgvector..."
	python scripts/index_docs.py --source ./docs --glob "**/*.md"

pull-model:
	docker compose exec ollama ollama pull $${LOCAL_LLM_MODEL:-mistral}

shell-db:
	docker compose exec db psql -U $${POSTGRES_USER:-supporty} -d $${POSTGRES_DB:-supporty}
