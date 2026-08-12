# Chunking

## Why documents must be chunked

An embedding model produces **one vector per text**. If we embedded a whole
40-page policy as one vector:

- The vector would be a blurry average of every topic in the document.
- Every query would match the document equally well (or equally badly).
- Retrieval could only answer "the information is somewhere in this PDF".

Chunking splits the document into small pieces so each piece has a focused
meaning and its own vector. A question about diabetes then matches *the
paragraph about diabetes*, and the citation points at the exact page.

There is a second, practical reason: the retrieved chunks are pasted into
the LLM prompt. Prompts have size limits and cost money per token — you want
to send the 5 most relevant paragraphs, not 40 pages.

## Choosing a chunk size

Configured via environment variables (`app/core/config.py`):

```env
CHUNK_SIZE=500      # max characters per chunk
CHUNK_OVERLAP=100   # characters shared between consecutive chunks
```

**If chunks are too small** (say 50 characters):

- A sentence gets torn apart; each fragment loses the context that gives it
  meaning ("...after a waiting period of" — of *what*?).
- The embedding of a fragment is noisy, so retrieval quality drops.
- You need many more chunks to reconstruct an answer.

**If chunks are too large** (say 5000 characters):

- One chunk covers several topics; its embedding becomes an average and
  matches everything weakly — the same problem as embedding the whole
  document, in miniature.
- Retrieved chunks flood the LLM context with mostly irrelevant text, which
  dilutes the model's attention and increases cost.

500 characters ≈ a paragraph — big enough to carry meaning, small enough to
stay on one topic. It's a starting point, not a law; tune it by watching
retrieval quality in the debug endpoint.

## Why overlap is useful

Chunks are cut at (approximately) fixed positions, and important sentences
don't respect those positions:

```text
... The waiting period for | pre-existing diseases is 24 months ...
                           ^ cut here, the sentence is split
```

With a 100-character overlap, the tail of each chunk is repeated at the head
of the next one, so any sentence near a boundary survives **whole** in at
least one chunk:

```text
chunk 1: ... The waiting period for pre-existing
chunk 2: waiting period for pre-existing diseases is 24 months ...
```

The cost is mild duplication in storage — a fair trade for never losing a
boundary sentence.

## The implementation

`app/services/chunking_service.py` uses a sliding window over characters:

1. Take up to `CHUNK_SIZE` characters.
2. Pull the cut back to the last space, so words are never split.
3. Step forward by `CHUNK_SIZE - CHUNK_OVERLAP`, again aligned to a word
   boundary.
4. Chunks never cross page boundaries — every chunk belongs to exactly one
   page, which keeps citations exact.

Each chunk is stored (in `document_chunks`) with the metadata that makes
citations work: `page_number`, `section` (detected from "Section N: Title"
headings when present), `chunk_index` (reading order), and the original
text.

Deliberately **not** implemented yet: semantic chunking (splitting on topic
shifts detected via embeddings), sentence-aware splitting, or
structure-aware parsing of tables. Simple first; measure; then improve.
