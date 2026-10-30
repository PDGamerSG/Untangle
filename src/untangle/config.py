"""Runtime settings, read once from the environment (and `.env` in the project root when present)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def cache_root() -> Path:
    """Serverless deployments have a read-only checkout and writable temporary storage."""
    default = Path("/tmp/untangle") if os.environ.get("VERCEL") else PROJECT_ROOT / ".cache"
    return Path(os.environ.get("UNTANGLE_CACHE_DIR") or default)


def _load_env() -> None:
    for candidate in (Path.cwd() / ".env", PROJECT_ROOT / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            break


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


@dataclass(frozen=True)
class Settings:
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str | None = None

    github_token: str | None = None
    repo_cache: Path = field(default_factory=lambda: cache_root() / "repos")

    llm_backend: str = "fake"
    llm_model: str | None = None
    anthropic_api_key: str | None = None
    sarvam_api_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    embed_backend: str = "fake"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384

    sarvam_stt_model: str = "saaras:v4"
    sarvam_stt_mode: str = "codemix"

    api_host: str = "127.0.0.1"
    api_port: int = 8090
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    display_language: str = "en"

    @property
    def aura(self) -> bool:
        return "databases.neo4j.io" in self.neo4j_uri


@cache
def settings() -> Settings:
    _load_env()
    cache_dir = Path(_env("UNTANGLE_REPO_CACHE", str(cache_root() / "repos")))
    if not cache_dir.is_absolute():
        cache_dir = PROJECT_ROOT / cache_dir
    return Settings(
        neo4j_uri=_env("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=_env("NEO4J_USER", "neo4j"),
        neo4j_password=_env("NEO4J_PASSWORD", ""),
        neo4j_database=_env("NEO4J_DATABASE") or None,
        github_token=_env("GITHUB_TOKEN") or None,
        repo_cache=cache_dir,
        llm_backend=_env("LLM_BACKEND", "fake").lower(),
        llm_model=_env("LLM_MODEL") or None,
        anthropic_api_key=_env("ANTHROPIC_API_KEY") or None,
        sarvam_api_key=_env("SARVAM_API_KEY") or None,
        openai_api_key=_env("OPENAI_API_KEY") or None,
        openai_base_url=_env("OPENAI_BASE_URL") or None,
        embed_backend=_env("EMBED_BACKEND", "fake").lower(),
        embed_model=_env("EMBED_MODEL", "BAAI/bge-small-en-v1.5"),
        embed_dim=int(_env("EMBED_DIM", "384")),
        sarvam_stt_model=_env("SARVAM_STT_MODEL", "saaras:v4"),
        sarvam_stt_mode=_env("SARVAM_STT_MODE", "codemix"),
        api_host=_env("API_HOST", "127.0.0.1"),
        api_port=int(_env("API_PORT", "8090")),
        cors_origins=tuple(o.strip() for o in _env("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()),
        display_language=_env("UNTANGLE_DISPLAY_LANGUAGE", "en").strip().lower(),
    )
