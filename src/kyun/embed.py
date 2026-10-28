"""Text embeddings for the vector-only baseline and chunk recall. `fastembed` runs BAAI/bge-small-en-v1.5
(384 dims) on CPU with ONNX; `fake` hashes tokens into a sparse-ish unit vector so the whole pipeline,
including the vector index, works offline and deterministically in tests."""

from __future__ import annotations

import hashlib
import logging
import math
import re
import sqlite3
from array import array
from functools import cache
from pathlib import Path

from kyun.config import PROJECT_ROOT, Settings, settings

log = logging.getLogger("kyun.embed")
_WORD = re.compile(r"[0-9A-Za-zऀ-ॿ]+")


class Embedder:
    backend = "fake"
    dim = 384

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class FakeEmbedder(Embedder):
    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dim
            words = [w.lower() for w in _WORD.findall(text or "")]
            for w in words:
                h = int(hashlib.blake2b(w.encode("utf-8"), digest_size=8).hexdigest(), 16)
                vec[h % self.dim] += 1.0
                vec[(h >> 20) % self.dim] += 0.5
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


class FastEmbedder(Embedder):
    backend = "fastembed"

    def __init__(self, model: str, dim: int):
        from fastembed import TextEmbedding  # imported lazily: optional dependency

        self.model_name, self.dim = model, dim
        self._model = TextEmbedding(model_name=model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in vec] for vec in self._model.embed(texts, batch_size=64)]


class CachedEmbedder(Embedder):
    """Wraps a real embedder with an on-disk cache keyed by (model, text), so re-ingesting a repository only embeds
    text it has not seen. SQLite in `.cache/embeddings/<model>.sqlite`, vectors stored as float32."""

    def __init__(self, inner: Embedder, path: Path):
        self.inner, self.backend, self.dim = inner, inner.backend, inner.dim
        self.model = getattr(inner, "model_name", inner.backend)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vec BLOB NOT NULL)")
        self.hits = self.misses = 0

    def _key(self, text: str) -> str:
        return hashlib.sha1(f"{self.model}\x1f{text}".encode()).hexdigest()

    def get(self, texts: list[str]) -> list[list[float] | None]:
        keys = [self._key(t) for t in texts]
        found: dict[str, list[float]] = {}
        for i in range(0, len(keys), 500):
            part = keys[i : i + 500]
            marks = ",".join("?" * len(part))
            for key, blob in self._db.execute(f"SELECT key, vec FROM vectors WHERE key IN ({marks})", part):
                found[key] = array("f", blob).tolist()
        return [found.get(k) for k in keys]

    def put(self, texts: list[str], vectors: list[list[float]]) -> None:
        self._db.executemany(
            "INSERT OR REPLACE INTO vectors (key, vec) VALUES (?, ?)",
            [(self._key(t), array("f", v).tobytes()) for t, v in zip(texts, vectors, strict=True)],
        )
        self._db.commit()

    def embed(self, texts: list[str]) -> list[list[float]]:
        cached = self.get(texts)
        todo = [i for i, v in enumerate(cached) if v is None]
        self.hits += len(texts) - len(todo)
        self.misses += len(todo)
        if todo:
            fresh = self.inner.embed([texts[i] for i in todo])
            self.put([texts[i] for i in todo], fresh)
            for i, v in zip(todo, fresh, strict=True):
                cached[i] = array("f", v).tolist()  # the same float32 values a later cache hit returns
        return [v for v in cached if v is not None]


def cache_path(model: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", model)
    return PROJECT_ROOT / ".cache" / "embeddings" / f"{slug}.sqlite"


@cache
def make_embedder(s: Settings | None = None) -> Embedder:
    s = s or settings()
    if s.embed_backend == "fastembed":
        try:
            return CachedEmbedder(FastEmbedder(s.embed_model, s.embed_dim), cache_path(s.embed_model))
        except Exception as exc:  # noqa: BLE001
            log.warning("fastembed unavailable (%s); using the fake embedder", exc)
    return FakeEmbedder(s.embed_dim)
