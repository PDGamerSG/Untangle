"""Production paths must remain writable and use the configured real embedder."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from untangle import embed
from untangle.config import Settings


def test_vercel_embedding_cache_uses_temporary_storage(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("UNTANGLE_CACHE_DIR", raising=False)
    assert embed.cache_path("BAAI/bge-small-en-v1.5").is_relative_to(Path("/tmp/untangle"))


def test_embedding_cache_can_be_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("UNTANGLE_CACHE_DIR", str(tmp_path))
    assert embed.cache_path("BAAI/bge-small-en-v1.5").is_relative_to(tmp_path)


def test_real_embeddings_never_silently_become_fake(monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("model download failed")

    monkeypatch.setattr(embed, "FastEmbedder", unavailable)
    embed.make_embedder.cache_clear()
    with pytest.raises(RuntimeError, match="model download failed"):
        embed.make_embedder(Settings(embed_backend="fastembed"))


def test_model_download_caches_are_writable_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("UNTANGLE_CACHE_DIR", raising=False)
    for key in ("HF_HOME", "HF_HUB_CACHE", "HF_XET_CACHE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setitem(sys.modules, "fastembed", SimpleNamespace(TextEmbedding=lambda **kwargs: None))
    embed.FastEmbedder("BAAI/bge-small-en-v1.5", 384)
    assert Path(os.environ["HF_HOME"]).is_relative_to("/tmp/untangle")
    assert Path(os.environ["HF_XET_CACHE"]).is_relative_to("/tmp/untangle")
