"""Unit tests for the embeddings wrapper + resume cache."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from role_tracker.matching.embeddings import Embedder, load_or_embed_resume


def _fake_openai_client(vectors: list[list[float]]) -> MagicMock:
    """MagicMock that mimics openai.OpenAI's embeddings.create shape."""
    response = MagicMock()
    response.data = [MagicMock(embedding=v) for v in vectors]
    client = MagicMock()
    client.embeddings.create.return_value = response
    return client


def test_embed_returns_vectors_in_order() -> None:
    client = _fake_openai_client([[1.0, 0.0], [0.0, 1.0]])
    embedder = Embedder(api_key="x", model="test-model", client=client)
    result = embedder.embed(["foo", "bar"])
    assert result == [[1.0, 0.0], [0.0, 1.0]]
    client.embeddings.create.assert_called_once()


def test_embed_empty_input_skips_api_call() -> None:
    client = _fake_openai_client([])
    embedder = Embedder(api_key="x", model="test-model", client=client)
    assert embedder.embed([]) == []
    client.embeddings.create.assert_not_called()


def test_load_or_embed_resume_writes_cache_on_first_run(tmp_path: Path) -> None:
    client = _fake_openai_client([[0.1, 0.2, 0.3]])
    embedder = Embedder(api_key="x", model="test-model", client=client)
    cache = tmp_path / "resume_embedding.json"

    vector = load_or_embed_resume(embedder, "my resume text", cache)

    assert vector == [0.1, 0.2, 0.3]
    assert cache.exists()
    cached = json.loads(cache.read_text())
    assert cached["vector"] == [0.1, 0.2, 0.3]
    assert "hash" in cached


def test_load_or_embed_resume_reuses_cache_when_text_unchanged(tmp_path: Path) -> None:
    client = _fake_openai_client([[0.1, 0.2, 0.3]])
    embedder = Embedder(api_key="x", model="test-model", client=client)
    cache = tmp_path / "resume_embedding.json"

    load_or_embed_resume(embedder, "same text", cache)
    load_or_embed_resume(embedder, "same text", cache)

    # Only one API call even though we called load_or_embed twice.
    assert client.embeddings.create.call_count == 1


def test_load_or_embed_resume_reembeds_when_text_changes(tmp_path: Path) -> None:
    client = _fake_openai_client([[0.1, 0.2]])
    # Second call returns a different vector — set up side_effect.
    response_1 = MagicMock()
    response_1.data = [MagicMock(embedding=[0.1, 0.2])]
    response_2 = MagicMock()
    response_2.data = [MagicMock(embedding=[0.9, 0.8])]
    client.embeddings.create.side_effect = [response_1, response_2]

    embedder = Embedder(api_key="x", model="test-model", client=client)
    cache = tmp_path / "resume_embedding.json"

    v1 = load_or_embed_resume(embedder, "original text", cache)
    v2 = load_or_embed_resume(embedder, "edited text", cache)

    assert v1 == [0.1, 0.2]
    assert v2 == [0.9, 0.8]
    assert client.embeddings.create.call_count == 2
