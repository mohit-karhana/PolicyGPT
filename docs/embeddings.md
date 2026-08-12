# Embeddings

## The core idea

Computers can't compare *meaning* directly. An embedding model converts text
into a vector (a list of numbers) such that **texts with similar meaning get
vectors pointing in similar directions**:

```text
Text
 ↓
Embedding Model          (sentence-transformers/all-MiniLM-L6-v2)
 ↓
Vector                   (384 floats, e.g. [0.021, -0.117, 0.539, ...])
 ↓
Vector Database          (PostgreSQL + pgvector, document_chunks.embedding)
 ↓
Similarity Search        (cosine similarity between query and chunks)
```

This is what lets *"Is diabetes covered?"* find a paragraph that says
*"pre-existing conditions such as diabetes mellitus are subject to a waiting
period"* — the two share almost no words, but they mean related things, so
their vectors are close.

## How text becomes a vector

`all-MiniLM-L6-v2` is a small transformer network. It tokenizes the text,
runs it through 6 transformer layers, and pools the output into a single
**384-dimensional** vector. Each dimension is not individually meaningful —
meaning is encoded in the *direction* of the whole vector.

In PolicyGPT this happens in `app/services/embedding_service.py`:

- `embed_text(text)` — one text, one vector (used for search queries).
- `embed_documents(texts)` — many texts in one batched forward pass (used
  when ingesting documents; batching is much faster than one-by-one).

The model loads once per process (`get_embedding_service` is cached) because
loading takes seconds while encoding takes milliseconds.

## Vector dimensions

The dimension (384) is a property of the model. It is configured exactly
once, as `EMBEDDING_DIMENSION` in settings, and everything reads it from
there: the pgvector column type, the migration, and a startup check that the
loaded model actually produces vectors of that size. Switching to a model
with a different dimension means changing the setting and migrating the
column — vectors of different sizes (or from different models!) cannot be
compared.

## Cosine similarity

Similarity between two vectors is measured by the angle between them:

```text
cosine_similarity(a, b) = (a · b) / (|a| · |b|)

 1.0  → same direction   (same meaning)
 0.0  → perpendicular    (unrelated)
-1.0  → opposite
```

It compares **direction, not length** — a long paragraph and a short
sentence about the same topic can still score high. A reference
implementation lives in `embedding_service.cosine_similarity`, and pgvector
computes the same thing in SQL as a *distance* with the `<=>` operator
(`distance = 1 - similarity`).

PolicyGPT normalizes all vectors to length 1 at encoding time
(`normalize_embeddings=True`), which makes cosine similarity numerically
equal to a simple dot product and keeps scores comparable across queries.

## Semantic vs keyword similarity

| Query | Keyword search finds | Semantic search finds |
|-------|----------------------|----------------------|
| "Is sugar disease covered?" | nothing (no word overlap) | the diabetes clause |
| "room rent cap" | only exact phrase "room rent" | "daily room charges limited to 2% of sum insured" |

Embeddings are not magic: they can miss exact identifiers (policy numbers,
specific drug names) that keyword search handles trivially. That's why
production systems often combine both ("hybrid search") — a later
optimization for PolicyGPT.

## Try it yourself

Use the debug endpoint to see raw similarity scores:

```bash
curl -s -X POST http://localhost:8001/api/v1/debug/search \
  -H "Content-Type: application/json" \
  -d '{"policy_id": "<id>", "query": "Is diabetes covered?"}'
```

Rephrase the query ("sugar illness", "diabetic treatment") and watch how the
scores change while the top result usually stays the same — that's semantic
similarity at work.
