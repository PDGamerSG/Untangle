"""One Neo4j database, one driver. Works unchanged against local Neo4j and AuraDB Free.

`Graph.query` runs a managed write transaction, `Graph.read` a managed read transaction (the server refuses
writes inside it) with an optional timeout. Results come back as `QueryResult` with `.rows` (lists) and
`.records` (dicts keyed by column). The handle shape follows Helium's `GraphHandle`; tenancy, CDC and
multi-database code were dropped because AuraDB Free has none of them."""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Iterable
from typing import Any

from neo4j import READ_ACCESS, WRITE_ACCESS, Driver, GraphDatabase, unit_of_work
from neo4j.exceptions import ClientError, Neo4jError, ServiceUnavailable

from untangle.config import settings
from untangle.graph.queries import load_cypher, schema_statements

log = logging.getLogger("untangle.graph")

UNIQUE_ID_LABELS = [
    "Repo", "Person", "Identity", "Commit", "File", "Module", "Symbol", "ConfigKey", "Dependency",
    "PullRequest", "Issue", "Comment", "Document", "Chunk", "Decision", "Meeting", "Utterance",
]
_INDEX_NAME = re.compile(r"CREATE\s+(?:FULLTEXT\s+|VECTOR\s+)?INDEX\s+(\w+)", re.IGNORECASE)


class GraphUnavailable(RuntimeError):
    """Neo4j is not reachable with the configured URI and credentials."""


class QueryResult:
    __slots__ = ("header", "rows", "summary")

    def __init__(self, rows: list[list[Any]], header: list[str], summary: Any = None):
        self.rows = rows
        self.header = header
        self.summary = summary

    @property
    def records(self) -> list[dict[str, Any]]:
        return [dict(zip(self.header, row, strict=False)) for row in self.rows]

    def scalar(self, default: Any = None) -> Any:
        return self.rows[0][0] if self.rows and self.rows[0] else default

    def __iter__(self):
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)


class Graph:
    """Thread-safe: the neo4j driver keeps a connection pool."""

    def __init__(self, uri: str, user: str, password: str, database: str | None = None, *, max_pool: int = 50):
        self.uri, self.user, self.database = uri, user, database
        self._driver: Driver = GraphDatabase.driver(
            uri, auth=(user, password), max_connection_pool_size=max_pool, notifications_min_severity="OFF"
        )
        self._lock = threading.Lock()
        self._capabilities: dict[str, Any] | None = None

    # -- transactions ---------------------------------------------------------------------------
    def _run(self, cypher: str, params: dict | None, timeout_ms: int | None, access: str) -> QueryResult:
        def work(tx):
            res = tx.run(cypher, params or {})
            header = list(res.keys())
            rows = [list(record.values()) for record in res]
            return QueryResult(rows, header, res.consume())

        if timeout_ms:
            work = unit_of_work(timeout=timeout_ms / 1000.0)(work)
        with self._driver.session(database=self.database, default_access_mode=access) as session:
            if access == READ_ACCESS:
                return session.execute_read(work)
            return session.execute_write(work)

    def query(self, cypher: str, params: dict | None = None, timeout: int | None = None) -> QueryResult:
        """Write transaction."""
        return self._run(cypher, params, timeout, WRITE_ACCESS)

    def read(self, cypher: str, params: dict | None = None, timeout: int | None = None) -> QueryResult:
        """Read transaction (timeout in ms). A write clause raises `neo4j.exceptions.ClientError`."""
        return self._run(cypher, params, timeout, READ_ACCESS)

    def run_named(self, name: str, params: dict | None = None, *, write: bool = False, timeout: int | None = None) -> QueryResult:
        """Run `cypher/NN_<name>.cypher`."""
        text = load_cypher(name)
        return self.query(text, params, timeout) if write else self.read(text, params, timeout)

    def write_batches(self, cypher: str, rows: Iterable[dict[str, Any]], *, batch_size: int = 500, key: str = "rows") -> int:
        """Run one UNWIND-style statement over `rows` in batches of `batch_size`; returns rows sent."""
        sent, batch = 0, []
        for row in rows:
            batch.append(row)
            if len(batch) >= batch_size:
                self.query(cypher, {key: batch})
                sent += len(batch)
                batch = []
        if batch:
            self.query(cypher, {key: batch})
            sent += len(batch)
        return sent

    def run_many(self, statements: list[str]) -> None:
        with self._driver.session(database=self.database, default_access_mode=WRITE_ACCESS) as session:
            for statement in statements:  # schema statements cannot share a transaction with each other on Aura
                session.run(statement).consume()

    # -- schema -----------------------------------------------------------------------------------
    def ensure_schema(self, embed_dim: int | None = None) -> dict[str, int]:
        dim = embed_dim or settings().embed_dim
        statements = schema_statements(dim)
        constraints = [
            f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE" for label in UNIQUE_ID_LABELS
        ]
        self.run_many(constraints + statements)
        try:
            self.query("CALL db.awaitIndexes(120)")
        except Neo4jError as exc:  # pragma: no cover - older servers
            log.warning("awaitIndexes failed: %s", exc)
        return {"constraints": len(constraints), "indexes": len([s for s in statements if _INDEX_NAME.search(s)])}

    def wipe_repo(self, repo: str) -> int:
        """Delete everything ingested for one repository (used by `untangle ingest --reset`), then the people and
        identities that no longer connect to anything (Person/Identity are shared across repositories, so they
        carry no `repo` and are only removed once nothing refers to them)."""
        total = 0
        while True:
            n = self.query(
                "MATCH (n {repo: $repo}) WITH n LIMIT 5000 DETACH DELETE n RETURN count(*) AS n", {"repo": repo}
            ).scalar(0)
            total += int(n or 0)
            if not n:
                break
        # the Repo node is named by `full_name`, not `repo`
        total += int(self.query("MATCH (r:Repo {full_name: $repo}) DETACH DELETE r RETURN count(*) AS n", {"repo": repo}).scalar(0) or 0)
        # speaker identities are scoped to a meeting (`<meeting id>/<label>`), and meeting ids carry the repository
        total += int(
            self.query(
                "MATCH (i:Identity {kind: 'speaker'}) WHERE i.value STARTS WITH $prefix DETACH DELETE i RETURN count(*) AS n",
                {"prefix": f"mtg:{repo}:"},
            ).scalar(0)
            or 0
        )
        total += int(
            self.query(
                "MATCH (p:Person) WHERE NOT EXISTS { (p)-[r]-() WHERE type(r) <> 'IDENTITY_OF' } "
                "OPTIONAL MATCH (i:Identity)-[:IDENTITY_OF]->(p) "
                "WITH p, collect(i) AS ids DETACH DELETE p FOREACH (i IN ids | DETACH DELETE i) RETURN count(*) AS n"
            ).scalar(0)
            or 0
        )
        return total

    # -- introspection ------------------------------------------------------------------------------
    def ping(self) -> bool:
        try:
            self._driver.verify_connectivity()
            return True
        except (ServiceUnavailable, Neo4jError, OSError):
            return False

    def capabilities(self) -> dict[str, Any]:
        """Edition, version, Aura flag, and whether the vector index procedure answers."""
        if self._capabilities is None:
            caps: dict[str, Any] = {"edition": None, "version": None, "aura": False, "vector": True}
            try:
                row = self.read(
                    "CALL dbms.components() YIELD name, versions, edition WHERE name = 'Neo4j Kernel' RETURN versions[0], edition"
                ).rows[0]
                caps["version"], caps["edition"] = row[0], row[1]
                caps["aura"] = str(row[0]).lower().endswith("-aura") or settings().aura
            except Exception as exc:  # noqa: BLE001
                log.warning("dbms.components failed: %s", exc)
            self._capabilities = caps
        return self._capabilities

    def stats(self, repo: str | None = None) -> dict[str, Any]:
        where = "WHERE n.repo = $repo" if repo else ""
        labels = self.read(
            f"MATCH (n) {where} UNWIND labels(n) AS l RETURN l AS label, count(*) AS n ORDER BY n DESC", {"repo": repo}
        ).records
        rels = self.read(
            f"MATCH (a)-[r]->() {'WHERE a.repo = $repo' if repo else ''} RETURN type(r) AS type, count(*) AS n ORDER BY n DESC",
            {"repo": repo},
        ).records
        return {
            "nodes": sum(int(r["n"]) for r in labels),
            "relationships": sum(int(r["n"]) for r in rels),
            "labels": {r["label"]: int(r["n"]) for r in labels},
            "relationship_types": {r["type"]: int(r["n"]) for r in rels},
        }

    def close(self) -> None:
        self._driver.close()


def connect(*, require: bool = True) -> Graph:
    """Graph from settings. With `require=True` a dead server raises `GraphUnavailable` at once."""
    s = settings()
    graph = Graph(s.neo4j_uri, s.neo4j_user, s.neo4j_password, s.neo4j_database)
    if require and not graph.ping():
        graph.close()
        raise GraphUnavailable(f"Neo4j at {s.neo4j_uri} does not answer (check NEO4J_URI / NEO4J_PASSWORD)")
    return graph


__all__ = ["ClientError", "Graph", "GraphUnavailable", "Neo4jError", "QueryResult", "UNIQUE_ID_LABELS", "connect"]
