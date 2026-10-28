"""Shared fixtures. `graph` connects to the configured Neo4j and skips the test when it is unreachable;
it ensures the schema once per session and wipes the `test/*` repositories it creates."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("LLM_BACKEND", "fake")
os.environ.setdefault("EMBED_BACKEND", "fake")
os.environ.setdefault("EMBED_DIM", "384")

from untangle.graph.db import Graph, GraphUnavailable, connect  # noqa: E402

_CREATED: list[str] = []  # test repos this session created; only these are wiped at the end (parallel runs share the DB)


@pytest.fixture(scope="session")
def graph() -> Graph:
    try:
        g = connect(require=True)
    except GraphUnavailable as exc:
        pytest.skip(str(exc))
    g.ensure_schema()
    yield g
    for repo in _CREATED:
        g.wipe_repo(repo)
    g.close()


@pytest.fixture
def test_repo(graph: Graph):
    """A unique `test/<name>` repo id, cleaned after the test."""
    import uuid

    name = f"test/{uuid.uuid4().hex[:8]}"
    _CREATED.append(name)
    yield name
    graph.wipe_repo(name)
