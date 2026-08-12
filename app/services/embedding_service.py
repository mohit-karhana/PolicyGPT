"""Embedding generation with Sentence Transformers.

An embedding is a list of floats (here: 384 of them) that represents the
MEANING of a text. Texts about similar things get vectors that point in
similar directions, which is what lets "Is diabetes covered?" find a
paragraph that says "pre-existing conditions such as diabetes..." even
though they share almost no words. See docs/embeddings.md.

The model is loaded once per process (lru_cache) and reused — loading takes
seconds, encoding takes milliseconds, so reloading per request would be
catastrophic for latency.
"""

import math
from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = get_logger(__name__)


class EmbeddingService:
    def __init__(self, model_name: str) -> None:
        # Imported lazily: sentence_transformers pulls in PyTorch, which is
        # slow to import and unnecessary for code paths that never embed.
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s", model_name)
        self._model: SentenceTransformer = SentenceTransformer(model_name)
        logger.info("Embedding model loaded: dimension=%d", self.dimension)

    @property
    def dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text (e.g. a search query)."""
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed many texts in one batched forward pass (much faster than
        one-by-one).

        Vectors are L2-normalized so cosine similarity is a plain dot
        product and scores are directly comparable across queries.
        """
        vectors = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        logger.info("Embeddings generated: texts=%d dim=%d", len(texts), self.dimension)
        return [vector.tolist() for vector in vectors]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Process-wide singleton. Never construct EmbeddingService directly."""
    service = EmbeddingService(settings.embedding_model)
    if service.dimension != settings.embedding_dimension:
        raise RuntimeError(
            f"Model '{settings.embedding_model}' produces {service.dimension}-d "
            f"vectors but EMBEDDING_DIMENSION={settings.embedding_dimension}. "
            "Update EMBEDDING_DIMENSION and migrate the embedding column."
        )
    return service


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two vectors: 1=same direction, 0=unrelated,
    -1=opposite. Included as a reference implementation of what pgvector's
    `<=>` operator computes (as a distance: 1 - similarity).
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
