# Vector Search

## What happens on every search

```text
query text ("Is diabetes covered?")
        ↓  embed with the SAME model used for the chunks
query embedding (384 floats)
        ↓
compare against every chunk embedding of the policy
        ↓
order by similarity
        ↓
LIMIT top_k
```

In PolicyGPT this is one explicit SQL query (`app/services/retrieval_service.py`):

```sql
SELECT *, embedding <=> '[0.02, -0.11, ...]' AS distance
FROM document_chunks
WHERE policy_id = :policy_id
ORDER BY distance
LIMIT :top_k;
```

No framework hides this — the SQLAlchemy expression in `search_chunks`
compiles to exactly that query.

## pgvector operators

pgvector adds a `vector` column type and distance operators to Postgres:

| Operator | Distance | Use when |
|----------|----------|----------|
| `<=>` | cosine distance | comparing meaning regardless of text length (**what we use**) |
| `<->` | L2 / Euclidean | vectors where absolute position matters |
| `<#>` | negative inner product | normalized vectors, fastest |

`<=>` returns a **distance** (0 = identical direction). We report
`similarity = 1 - distance` so that higher = better, which is more intuitive
in API responses.

## Why the vector DB is just Postgres

The embeddings live in the same database as policies and documents. That
means:

- One system to run, back up, and migrate.
- Chunk metadata (page, section) and the vector are in the same row — no
  syncing between a relational DB and a separate vector store.
- Filtering is plain SQL: `WHERE policy_id = ...` scopes search to one
  policy before any vector math happens.
- You can *look at* the data: `SELECT content, embedding FROM document_chunks LIMIT 1;`

Dedicated vector databases (Pinecone, Weaviate, Qdrant, ...) earn their keep
at millions of vectors and high query rates. At learning scale, pgvector is
simpler and just as instructive.

## Exact search now, indexes later

There is deliberately **no vector index** yet. The query above does a
sequential scan: it computes the distance to every chunk of the policy. For
thousands of chunks this takes single-digit milliseconds, and results are
*exact*.

At larger scale you'd add an approximate-nearest-neighbor index:

```sql
CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

HNSW/IVFFlat indexes make search sub-linear but *approximate* — they can
occasionally miss the true best match. Adding one is a single migration
later; skipping it now keeps behavior deterministic while learning.

## Observing retrieval

`POST /api/v1/debug/search` exists purely for this. Things worth trying:

- Ask the same question in different words — scores shift, ranking mostly
  survives.
- Ask about something not in the policy ("helicopter travel to Mars") — you
  still get top-k results (the query always returns the k *least distant*
  chunks), but with visibly **lower similarity scores**. This is why the RAG
  layer must be told to say "not found" instead of forcing an answer from
  weak matches.
- Compare `top_k: 3` vs `top_k: 10` — more context is not always better;
  the extra chunks are the weaker matches.
