"""OpenAI embeddings wrapper with on-disk cache for the resume vector."""

import hashlib
import json
from pathlib import Path
from typing import Protocol

from openai import OpenAI


class EmbeddingsClient(Protocol):
    """Minimal surface we use from openai.OpenAI — makes testing trivial."""

    def create(self, *, model: str, input: list[str]) -> object: ...


class Embedder:
    """Thin wrapper that batches texts into one API call."""

    def __init__(
        self,
        api_key: str,
        model: str,
        client: OpenAI | None = None,
    ) -> None:
        self._model = model
        self._client = client or OpenAI(api_key=api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, in the same order."""
        if not texts:
            return []
        response = self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in response.data]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_or_embed_resume(
    embedder: Embedder,
    resume_text: str,
    cache_path: Path,
) -> list[float]:
    """Return the resume embedding, recomputing only if the text changed.

    The cache file stores both the text hash and the vector, so editing the
    resume (even by one character) triggers a re-embed on the next run.
    """
    text_hash = _hash_text(resume_text)

    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        if cached.get("hash") == text_hash:
            return cached["vector"]

    vector = embedder.embed([resume_text])[0]
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"hash": text_hash, "vector": vector}))
    return vector
