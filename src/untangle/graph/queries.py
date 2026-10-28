"""Loader for `cypher/NN_name.cypher`: every query the product runs lives there, numbered, as the single
source of truth (a convention carried over from Helium). `load_cypher("why_path")` resolves `32_why_path`."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent


def cypher_dirs() -> list[Path]:
    dirs: list[Path] = []
    env = os.environ.get("KYUN_CYPHER_DIR")
    if env:
        dirs.append(Path(env))
    dirs.append(_PKG_DIR.parents[2] / "cypher")  # <repo>/cypher when running from a checkout
    dirs.append(_PKG_DIR / "cypher")  # bundled copy inside a wheel
    return [d for d in dirs if d.is_dir()]


@cache
def cypher_path(name: str) -> Path:
    for directory in cypher_dirs():
        exact = directory / f"{name}.cypher"
        if exact.is_file():
            return exact
        matches = sorted(directory.glob(f"[0-9][0-9]_{name}.cypher"))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"no cypher file for {name!r} in {[str(d) for d in cypher_dirs()]}")


def _strip_comments(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("//")]


@cache
def load_cypher(name: str) -> str:
    """Query text with `//` comment lines removed."""
    return "\n".join(_strip_comments(cypher_path(name).read_text(encoding="utf-8")))


def schema_statements(embed_dim: int) -> list[str]:
    """Each non-comment line of `00_schema.cypher` is one statement; the vector size is substituted."""
    text = cypher_path("00_schema").read_text(encoding="utf-8").replace("{{EMBED_DIM}}", str(int(embed_dim)))
    return _strip_comments(text)


def list_queries() -> list[str]:
    seen: dict[str, None] = {}
    for directory in cypher_dirs():
        for path in sorted(directory.glob("[0-9][0-9]_*.cypher")):
            seen.setdefault(path.stem, None)
    return list(seen)
