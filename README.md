# Suporty — Autonomous Support Architect

Security-first middleware that automates enterprise support workflows using a LangGraph directed acyclic graph. Sensitive data never leaves the VPS.

---

## How it works

Every incoming ticket travels through a fixed graph:

```
classify → verify → fetch_context → rag_retrieve → resolve → END
                ↘                                 ↗
                 escalate ←────────────────────────
                 (unverified identity OR confidence < 0.75)
```

| Node | What it does |
|------|-------------|
| `classify` | Extracts intent, urgency, and confidence from the ticket text |
| `verify` | Checks user identity against the CRM (stub by default) |
| `fetch_context` | Pulls account and billing history to enrich the prompt |
| `rag_retrieve` | Semantic search over your docs via pgvector |
| `resolve` | Generates a resolution using the appropriate LLM |
| `escalate` | Routes to the human queue when confidence is too low or identity fails |

### LLM boundary

PII is scrubbed from the raw text before any model call. If PII was detected, the ticket is routed to a **local Ollama instance** (Mistral) so sensitive data never reaches a cloud API. Clean tickets use **GPT-4o**.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | LangGraph + LangChain |
| API | FastAPI (async) |
| Database | PostgreSQL 16 + pgvector |
| Local LLM | Ollama — Mistral |
| Cloud LLM | OpenAI GPT-4o |
| Proxy | Nginx |
| Runtime | Docker Compose |

---

## Deployment

### Prerequisites

```bash
# On the VPS (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sh
apt install docker-compose-plugin -y
ufw allow 80 && ufw allow 443
```

### One-shot deploy

```bash
git clone https://github.com/Danultimate/supporty.git
cd supporty
cp .env.example .env
nano .env          # set OPENAI_API_KEY and POSTGRES_PASSWORD
./deploy.sh
```

The script builds the image, pulls the Mistral model into Ollama, starts all services, and waits for the health check to pass.

### TLS (after deploy)

```bash
certbot --nginx -d yourdomain.com
```

Then uncomment the HTTPS server block in [docker/nginx.conf](docker/nginx.conf) and restart Nginx:

```bash
docker compose restart nginx
```

---

## Configuration

All settings are driven by environment variables. Copy `.env.example` to `.env` and fill in:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI key for cloud LLM and embeddings | — |
| `POSTGRES_PASSWORD` | PostgreSQL password | `supporty` |
| `LOCAL_LLM_MODEL` | Ollama model for sensitive flows | `mistral` |
| `CLOUD_LLM_MODEL` | OpenAI model for non-sensitive flows | `gpt-4o` |
| `ESCALATION_THRESHOLD` | Confidence below which tickets escalate | `0.75` |
| `CRM_API_URL` | CRM base URL (leave blank to use stub) | — |
| `CRM_API_KEY` | CRM auth token | — |
| `RAG_TOP_K` | Number of doc chunks injected per ticket | `5` |

---

## API

### `POST /api/v1/webhook/ticket`

Synchronous — waits for the graph to complete and returns the result.

```json
{
  "user_id": "usr123",
  "raw_text": "The API has been returning 504 errors since the last deploy.",
  "ticket_id": "optional-idempotency-key",
  "metadata": {}
}
```

Response:

```json
{
  "ticket_id": "uuid",
  "status": "resolved",
  "intent": "technical",
  "urgency": "high",
  "confidence": 0.91,
  "resolution": "Please try...",
  "escalation_reason": null
}
```

### `POST /api/v1/webhook/ticket/async`

Fire-and-forget — returns `202 accepted` immediately. Optionally POSTs the result to `callback_url` when done.

```json
{
  "user_id": "usr123",
  "raw_text": "...",
  "callback_url": "https://your-system.com/webhook/result"
}
```

### `GET /api/v1/health` · `GET /api/v1/readiness`

Liveness and readiness probes. Readiness checks the database connection.

---

## Indexing documents for RAG

Place your Markdown or plain-text docs in a `docs/` folder and run:

```bash
make index-docs
# or directly:
python scripts/index_docs.py --source ./docs --glob "**/*.md"
```

Options:

```
--source      Root directory of documents  (default: ./docs)
--glob        File glob pattern            (default: **/*.md)
--chunk-size  Words per chunk              (default: 512)
--dry-run     Parse without writing to DB
```

---

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

make test       # run the full test suite
make up         # start all Docker services
make logs       # tail app logs
make shell-db   # open psql in the DB container
make pull-model # pull the Ollama model into the running container
```

---

## CRM Integration

The CRM tool is a stub by default. To connect a real CRM, set `CRM_API_URL` and `CRM_API_KEY` in `.env`. The integration skeleton lives in [app/tools/crm.py](app/tools/crm.py) — implement `_real_crm_call` and `_real_context_call` for your specific API contract.

---

## Project structure

```
app/
├── main.py               FastAPI entry point, lifespan hooks
├── state.py              SupportState TypedDict
├── config.py             Pydantic settings (env-driven)
├── observability.py      Structured logging (structlog)
├── api/
│   ├── routes.py         Webhook endpoints
│   └── background.py     Async fire-and-forget processor
├── graph/
│   ├── graph.py          StateGraph wiring
│   ├── routing.py        Conditional edge functions
│   └── nodes/            One file per graph node
├── llm/
│   └── router.py         Local vs cloud LLM selector
├── middleware/
│   └── pii_scrubber.py   PII detection and redaction
├── db/
│   └── pgvector.py       Async pool, schema bootstrap, similarity search
└── tools/
    └── crm.py            CRM verify + context fetch (stub + real skeleton)

docker/
├── Dockerfile            Non-root Python image
└── nginx.conf            Rate limiting, security headers, TLS-ready

scripts/
└── index_docs.py         Document ingestion CLI
```
