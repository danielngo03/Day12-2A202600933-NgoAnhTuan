from __future__ import annotations

import os
from functools import lru_cache

import requests
from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=4)
def _load_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


class MiniLMEmbeddings(Embeddings):
    """Local sentence-transformers embedding (all-MiniLM-L6-v2)."""

    def __init__(self, model_name: str):
        self.model = _load_model(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        embedding = self.model.encode([text], normalize_embeddings=True)
        return embedding[0].tolist()


class OpenRouterEmbeddings(Embeddings):
    """OpenRouter-hosted embedding model via OpenAI-compatible API."""

    def __init__(self, model_name: str, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _embed(self, texts: list[str]) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model_name, "input": texts}
        resp = requests.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        # Sort by index to preserve order
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Batch in chunks of 64 to avoid payload limits
        results: list[list[float]] = []
        chunk_size = 64
        for i in range(0, len(texts), chunk_size):
            results.extend(self._embed(texts[i : i + chunk_size]))
        return results

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]


def build_embeddings(settings=None, model_name: str | None = None, api_key: str | None = None, base_url: str | None = None) -> Embeddings:
    """Factory: returns appropriate Embeddings implementation based on settings or env."""
    resolved_model = model_name or (settings.embedding_model if settings else None) or "sentence-transformers/all-MiniLM-L6-v2"

    # If it's an OpenRouter model (free tier indicator or "/" suggests remote)
    _openrouter_models = {
        "nvidia/llama-nemotron-embed-vl-1b-v2:free",
        "nvidia/nemotron-embed",
    }
    if resolved_model in _openrouter_models or (settings and resolved_model == getattr(settings, "embedding_model", "") and "openrouter" in resolved_model.lower()):
        resolved_api_key = api_key or (settings.openrouter_api_key if settings else None) or os.getenv("OPENROUTER_API_KEY", "")
        resolved_base_url = base_url or (settings.openrouter_base_url if settings else None) or "https://openrouter.ai/api/v1"
        if not resolved_api_key:
            raise RuntimeError(f"OPENROUTER_API_KEY required for embedding model '{resolved_model}'.")
        return OpenRouterEmbeddings(model_name=resolved_model, api_key=resolved_api_key, base_url=resolved_base_url)

    # Default: local MiniLM
    return MiniLMEmbeddings(model_name=resolved_model)
