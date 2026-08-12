# PolicyGPT Architecture

PolicyGPT is a backend-only AI assistant for insurance policies. Users upload
policy PDFs and ask questions like *"Is diabetes covered?"*; answers are
grounded in the uploaded documents using embeddings, vector search and RAG.

This document describes the target architecture. Each phase of the project
fills in another part of it. **Phase 1 (current)** implements the shaded
foundation: API, database, models, migrations, Docker.

## The two pipelines

### 1. Ingestion pipeline (write path)

```text
PDF Upload
    ↓
FastAPI                    (Phase 1: API skeleton, Phase 2: upload endpoint)
    ↓
Store Document             (Phase 1: Document model, Phase 2: file storage)
    ↓
Celery Task                (Phase 2)
    ↓
PDF Text Extraction        (Phase 2, page-aware)
    ↓
Text Cleaning              (Phase 2)
    ↓
Chunking                   (Phase 3)
    ↓
Embedding Generation       (Phase 4)
    ↓
PostgreSQL + pgvector      (Phase 1: extension enabled, Phase 4: vectors stored)
```

The key design decision: **the API never processes PDFs synchronously**.
Uploading returns immediately with a `document_id`; a Celery worker does the
heavy lifting while the client polls `GET /api/v1/documents/{id}` for the
`processing_status` (`pending → processing → completed | failed`). That status
lifecycle already exists in Phase 1.

### 2. Question pipeline (read path)

```text
User Question
    ↓
FastAPI
    ↓
Question Embedding         (Phase 5)
    ↓
pgvector Similarity Search (Phase 5)
    ↓
Top-K Relevant Chunks      (Phase 5)
    ↓
Context Builder            (Phase 6)
    ↓
LLM                        (Phase 6, behind a replaceable interface)
    ↓
Answer + Citations         (Phase 6)
```

## Data model and traceability

Every answer must be traceable back to its source:

```text
Policy  →  Document  →  Page  →  Chunk
```

- **Policy** — the insurance policy the user asks questions about.
- **Document** — one uploaded PDF belonging to a policy, with its processing
  status and page count.
- **DocumentChunk** (Phase 3) — a small piece of a document's text carrying
  `page_number`, `section`, `chunk_index` and (from Phase 4) its embedding
  vector. This metadata is what makes citations like
  *"Page 18 — Pre-existing Diseases"* possible.

## Layering

```text
app/api/routes/    HTTP layer: parse input, call a service, shape the response
app/services/      Business logic: CRUD now; PDF, chunking, embeddings, RAG later
app/models/        SQLAlchemy ORM models (database truth)
app/schemas/       Pydantic models (API contract)
app/core/          Config, DB engine, logging, exceptions
app/tasks/         Celery tasks (Phase 2)
```

Rules the codebase follows:

- Route handlers contain no business logic; they delegate to services.
- Services raise domain exceptions (`PolicyNotFoundError`, ...); one exception
  handler in `app/main.py` converts them to a consistent JSON error shape.
  Stack traces are never exposed to clients.
- All configuration comes from the environment (`app/core/config.py`). The
  embedding dimension is defined exactly once there.
- The database session is injected per request via a FastAPI dependency,
  which also makes tests trivial to isolate.

## Infrastructure

Docker Compose runs four services (two active in Phase 1):

| Service    | Image                  | Role                                  |
|------------|------------------------|---------------------------------------|
| `api`      | built from `Dockerfile`| FastAPI app, runs migrations on start |
| `postgres` | `pgvector/pgvector:pg16` | Data + vector storage               |
| `redis`    | `redis:7-alpine`       | Celery broker and result backend      |
| `celery`   | built from `Dockerfile`| Background document processing worker |

pgvector is a Postgres extension that adds a `vector` column type and
similarity operators (cosine, L2, inner product). Using it means the vectors
live next to the relational data — one database, plain SQL, no separate
vector store to operate. The extension is enabled in the very first Alembic
migration so later phases can add the embedding column without infrastructure
changes.
