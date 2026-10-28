"""docs: ADR parsing (status, date, sections, supersession), document selection and ADR decision rows."""

from __future__ import annotations

from ingest_fixture import ADR_0001_SUPERSEDED, ADR_0002
from kyun.ingest.docs import (
    adr_decisions,
    canonical_status,
    doc_kind,
    is_adr_path,
    parse_date,
    parse_document,
    resolve_supersessions,
    select_doc_paths,
    split_sections,
)


def test_adr_paths_and_kinds():
    assert is_adr_path("docs/adr/0001-use-postgres.md") and is_adr_path("adr/ADR-0007-queue.md") and is_adr_path("decisions/0003-x.md")
    assert not is_adr_path("docs/adr/README.md") and not is_adr_path("docs/guide.md")
    assert doc_kind("CHANGELOG.md") == "changelog" and doc_kind("README.md") == "readme" and doc_kind("docs/design/queue.md") == "design"
    assert doc_kind("docs/install.md") == "doc"


def test_parse_classic_adr_with_superseded_status():
    doc = parse_document("docs/adr/0001-use-postgres.md", ADR_0001_SUPERSEDED)
    assert doc.kind == "adr" and doc.adr_number == 1 and doc.title == "Use Postgres"
    assert doc.status == "superseded" and doc.superseded_by_ref == "0002-switch-to-pgx.md"
    assert doc.date == parse_date("2023-12-20")
    assert doc.context.startswith("We need a relational store") and doc.decision == "Use PostgreSQL through lib/pq."
    assert doc.consequences == "One database to operate."
    assert [h for h, _ in doc.sections] == ["1. Use Postgres", "Status", "Date", "Context", "Decision", "Consequences"]


def test_parse_madr_front_matter():
    doc = parse_document("docs/adr/0002-switch-to-pgx.md", ADR_0002)
    assert doc.title == "Switch to pgx" and doc.status == "accepted" and doc.adr_number == 2
    assert doc.date == parse_date("2024-03-01") and doc.decision.startswith("Use jackc/pgx")
    assert doc.context == "lib/pq is in maintenance mode."


def test_status_and_date_helpers():
    assert canonical_status("Accepted") == "accepted" and canonical_status("Superseded by ADR-0007") == "superseded"
    assert canonical_status("**Proposed**") == "proposed" and canonical_status(None) is None
    assert parse_date("2024-03-01") == 1709251200000 and parse_date("March 1, 2024") == 1709251200000
    assert parse_date("01/03/2024") == 1709251200000 and parse_date("whenever") is None
    assert split_sections("intro\n# A\nbody a\n```\n# not a heading\n```\n## B\n") == [("", "intro"), ("A", "body a\n```\n# not a heading\n```"), ("B", "")]


def test_resolve_supersessions_by_link_and_number():
    a = parse_document("docs/adr/0001-a.md", "# 1. A\n\n## Status\n\nSuperseded by [ADR-0002](0002-b.md)\n")
    b = parse_document("docs/adr/0002-b.md", "# 2. B\n\n## Status\n\nSuperseded by ADR-0003\n")
    c = parse_document("docs/adr/0003-c.md", "# 3. C\n\n## Status\n\nAccepted\n")
    resolve_supersessions([a, b, c])
    assert a.superseded_by_path == "docs/adr/0002-b.md" and b.superseded_by_path == "docs/adr/0003-c.md" and c.superseded_by_path is None


def test_select_doc_paths_prefers_adrs_and_caps():
    paths = ["docs/adr/0001-x.md", "README.md", "CHANGELOG.md", "docs/guide.md", "docs/design/queue.md", "src/main.go", "node_modules/x/README.md", "web/README.md"]
    chosen = select_doc_paths(paths, max_docs=5)
    assert chosen == ["docs/adr/0001-x.md", "CHANGELOG.md", "README.md", "web/README.md", "docs/design/queue.md"]
    assert "docs/guide.md" in select_doc_paths(paths) and "node_modules/x/README.md" not in select_doc_paths(paths)


def test_adr_decisions_link_supersession():
    a = parse_document("docs/adr/0001-use-postgres.md", ADR_0001_SUPERSEDED)
    b = parse_document("docs/adr/0002-switch-to-pgx.md", ADR_0002)
    resolve_supersessions([a, b])
    rows = adr_decisions("o/r", [a, b], added_at={"docs/adr/0001-use-postgres.md": 5}, added_by={"docs/adr/0001-use-postgres.md": "person:email:ada@example.com"},
                         known_paths={"cmd/server.go"})
    by_path = {r.subject: r for r in rows}
    old, new = by_path["Use Postgres"], by_path["Switch to pgx"]
    assert old.kind == "adr" and old.key == "adr|use-postgres|adr_status" and old.object == "superseded" and old.signal == "adr_status"
    assert old.valid_from == parse_date("2023-12-20") and "Use PostgreSQL" in old.rationale
    assert ("STATED_BY", "person:email:ada@example.com", {}) in old.links
    assert ("DECIDED_IN", "doc:o/r:docs/adr/0001-use-postgres.md", {}) in old.links
    assert ("ABOUT", "file:o/r:cmd/server.go", {}) in new.links
    sup = [link for link in new.links if link[0] == "SUPERSEDES"]
    assert sup == [("SUPERSEDES", old.id, {"signal": "adr_status", "at": new.valid_from})]
