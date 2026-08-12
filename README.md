# PolicyGPT

AI-powered insurance policy assistant. Upload insurance policy PDFs and ask
questions like *"Is diabetes covered?"* or *"What is the waiting period for
pre-existing diseases?"* — answers are grounded in the uploaded documents
using **embeddings + pgvector similarity search + RAG**, with citations back
to the exact page and section.

This is a learning project for embeddings, semantic search, vector databases,
RAG and LLMs. The implementation is deliberately simple and transparent: no
LangChain, no hidden retrieval logic.

## Status: all phases complete

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | FastAPI, PostgreSQL + pgvector, SQLAlchemy, Alembic, CRUD, Docker | ✅ done |
| 2 | PDF upload, page-aware extraction, Celery + Redis | ✅ done |
| 3 | Chunking (configurable size/overlap, page + section metadata) | ✅ done |
| 4 | Embeddings (Sentence Transformers, batched, stored in pgvector) | ✅ done |
| 5 | Semantic search API + debug retrieval endpoint | ✅ done |
| 6 | RAG: LLM interface, context builder, ask API, citations | ✅ done |

## Tech stack

- **API**: Python 3.12, FastAPI, Pydantic
- **Database**: PostgreSQL + pgvector, SQLAlchemy 2.0, Alembic
- **Background jobs** (Phase 2+): Celery + Redis
- **Embeddings** (Phase 4+): `sentence-transformers/all-MiniLM-L6-v2`
- **Infra**: Docker Compose

## Quick start

```bash
cp .env.example .env      # never commit .env
docker compose up --build
```

The API starts on <http://localhost:8001> (migrations apply automatically):

- Swagger UI: <http://localhost:8001/docs>
- ReDoc: <http://localhost:8001/redoc>
- Health check: <http://localhost:8001/health>

### Try it

```bash
# Create a policy
curl -s -X POST http://localhost:8001/api/v1/policies \
  -H "Content-Type: application/json" \
  -d '{"name": "Star Health Comprehensive", "provider": "Star Health", "policy_number": "SH-2026-001"}'

# List policies
curl -s http://localhost:8001/api/v1/policies
```

### Upload a policy PDF

```bash
# Upload (replace {policy_id} with the id from the create response)
curl -s -X POST http://localhost:8001/api/v1/policies/{policy_id}/documents \
  -F "file=@/path/to/policy.pdf"

# The response has "processing_status": "pending". A Celery worker extracts
# the text in the background; poll until it is "completed":
curl -s http://localhost:8001/api/v1/documents/{document_id}
```

Uploads are validated (`.pdf` extension, `%PDF-` magic bytes, max size from
`MAX_UPLOAD_SIZE_MB`) and stored under `uploads/{policy_id}/{document_id}.pdf`
via a storage abstraction that can be swapped for S3 later.

### Search and ask

```bash
# Raw semantic search — see which chunks match, with similarity scores (no LLM)
curl -s -X POST http://localhost:8001/api/v1/policies/{policy_id}/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Is diabetes covered?", "top_k": 5}'

# Ranked retrieval debugging
curl -s -X POST http://localhost:8001/api/v1/debug/search \
  -H "Content-Type: application/json" \
  -d '{"policy_id": "{policy_id}", "query": "Is maternity covered?"}'

# RAG answer with citations (requires LLM_API_KEY + LLM_MODEL in .env)
curl -s -X POST http://localhost:8001/api/v1/policies/{policy_id}/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Is diabetes covered?"}'
```

### Configuring the LLM

Set in `.env` (any OpenAI-compatible API works):

```env
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1   # or Groq, Together, local Ollama...
```

Without an LLM configured, `/ask` returns `503 llm_unavailable`; everything
else — including semantic search — works without it.

## API

All endpoints are versioned under `/api/v1`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | API + database health |
| POST | `/api/v1/policies` | Create a policy |
| GET | `/api/v1/policies` | List policies (paginated) |
| GET | `/api/v1/policies/{id}` | Get a policy |
| PATCH | `/api/v1/policies/{id}` | Update a policy |
| DELETE | `/api/v1/policies/{id}` | Delete a policy and its documents |
| POST | `/api/v1/policies/{id}/documents` | Upload a policy PDF (async processing) |
| GET | `/api/v1/policies/{id}/documents` | List a policy's documents |
| GET | `/api/v1/documents/{id}` | Get a document + processing status |
| POST | `/api/v1/policies/{id}/search` | Semantic search: top-K chunks + scores (no LLM) |
| POST | `/api/v1/debug/search` | Ranked retrieval results for learning/debugging |
| POST | `/api/v1/policies/{id}/ask` | RAG: grounded answer + citations |

Errors use one consistent shape and never leak stack traces:

```json
{"error": {"code": "policy_not_found", "message": "Policy '...' not found"}}
```

## Local development (without Docker)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Start only the database (published on host port 5433):
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/policygpt
export REDIS_URL=redis://localhost:6379/0
alembic upgrade head
uvicorn app.main:app --reload

# In a second terminal, run the background worker:
celery -A app.tasks.celery_app worker --loglevel=info
```

### Tests

```bash
pytest
```

API tests run against an in-memory SQLite database (no Docker needed) by
overriding the database dependency — see `tests/conftest.py`.

### Migrations

```bash
alembic upgrade head                          # apply
alembic revision --autogenerate -m "message"  # create after model changes
```

## Project structure

```text
app/
├── main.py              # App composition: routers, exception handlers
├── api/
│   ├── dependencies.py  # get_db dependency (per-request DB session)
│   └── routes/          # Thin HTTP handlers (health, policies, documents)
├── core/
│   ├── config.py        # Environment-driven settings (single source of truth)
│   ├── database.py      # Engine + session factory
│   ├── exceptions.py    # Domain exceptions -> consistent JSON errors
│   └── logging.py       # Structured logging setup
├── models/              # SQLAlchemy ORM models (Policy, Document)
├── schemas/             # Pydantic request/response models
├── services/            # Business logic (routes never touch the DB directly)
│                        #   incl. pdf_service (extraction), storage_service (S3-ready)
└── tasks/               # Celery app + background tasks (process_document)
alembic/                 # Migrations (0001 enables pgvector + creates tables)
tests/                   # pytest API tests
docs/                    # Concept docs (architecture now; more per phase)
```

## Documentation

- [docs/architecture.md](docs/architecture.md) — overall design and the two
  pipelines (ingestion and question answering).
- [docs/embeddings.md](docs/embeddings.md) — what embeddings are, cosine
  similarity, semantic vs keyword search.
- [docs/chunking.md](docs/chunking.md) — why chunking is needed, size/overlap
  trade-offs.
- [docs/vector-search.md](docs/vector-search.md) — pgvector operators, the
  actual SQL, exact vs indexed search.
- [docs/rag.md](docs/rag.md) — the RAG pipeline, prompt rules, prompt
  injection, citations.
