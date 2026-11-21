"""Shared fixtures. `graph` connects to the configured Neo4j and skips the test when it is unreachable;
it ensures the schema once per session and wipes the `test/*` repositories it creates."""

from __future__ import annotations

import os

import pytest
from fastapi import Request  # module level: FastAPI resolves the override's string annotations from these globals

os.environ.setdefault("LLM_BACKEND", "fake")
os.environ.setdefault("EMBED_BACKEND", "fake")
os.environ.setdefault("EMBED_DIM", "384")

from untangle.graph.db import Graph, GraphUnavailable, connect  # noqa: E402

_CREATED: list[str] = []  # test repos this session created; only these are wiped at the end (parallel runs share the DB)


def _remote_database() -> bool:
    from untangle.config import settings

    uri = settings().neo4j_uri
    return not any(host in uri for host in ("localhost", "127.0.0.1", "[::1]")) and os.environ.get("UNTANGLE_TEST_REMOTE_DB") != "1"


@pytest.fixture(scope="session")
def graph() -> Graph:
    # The tests create and wipe repositories and prune people. A `.env` that points at the production database must
    # not turn `pytest` into a production write; set UNTANGLE_TEST_REMOTE_DB=1 only for a disposable remote database.
    if _remote_database():
        pytest.skip("Neo4j tests only run against a local database (set NEO4J_URI=bolt://localhost:7687)")
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


@pytest.fixture(autouse=True)
def signed_in(request):
    """API tests act as a signed-in administrator (no quotas) unless marked `real_auth`, which exercises the real
    session check. Authentication itself is covered in tests/test_auth.py."""
    if request.node.get_closest_marker("real_auth"):
        yield None
        return
    from untangle.api import main as api
    from untangle.api.auth import enforce_access
    from untangle.auth.service import User

    user = User(id="user:test-admin", email="admin@untangle.test", name="Test admin", role="admin", created_at=0)

    def as_user(req: Request) -> None:
        req.state.user = user

    api.app.dependency_overrides[enforce_access] = as_user
    yield user
    api.app.dependency_overrides.pop(enforce_access, None)
