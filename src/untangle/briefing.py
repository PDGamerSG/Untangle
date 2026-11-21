"""Day-one briefing: an orientation for someone new to a repository, built only from what the graph records.

It answers the questions a newcomer asks in their first week, each with sources:

- Which parts of the code see the most change, and who wrote most of it?
- Which decisions should I read before I change anything? (active decisions guarded by an incident, a linked
  issue, a revert, a handover statement or a long history of replaced values)
- What changed recently? (the latest supersessions)
- Who do I ask about what? (people ranked by authored commits, with the areas they wrote most of)
- What can I ask Untangle about this repository? (questions built from the decisions above)

Everything is deterministic and needs no model call. Authorship is a contact suggestion, not proof of ownership."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from untangle.answer.models import CypherCall, DecisionCard, Ref
from untangle.answer.retrieve import Recorder, version_from_row
from untangle.answer.text import fmt_date, iso
from untangle.graph.db import Graph
from untangle.preflight import _bot, _guards, _ref_name

ROOT = "(root)"
NESTED = ["src", "lib", "packages", "apps", "internal", "cmd", "pkg", "services", "modules", "crates", "plugins", "libs"]
TIMEOUT_MS = 20000


class AreaPerson(BaseModel):
    id: str
    name: str | None = None
    login: str | None = None
    commits: int
    share: float


class AreaBrief(BaseModel):
    name: str
    files: int
    commits: int
    last_changed_iso: str | None = None
    decisions: int = 0
    people: list[AreaPerson] = Field(default_factory=list)


class Guarded(BaseModel):
    decision: DecisionCard
    guards: list[str] = Field(default_factory=list)
    weight: int = 0


class Change(BaseModel):
    newer: DecisionCard
    older: DecisionCard
    at_iso: str | None = None
    signal: str | None = None
    source: Ref | None = None


class PersonBrief(BaseModel):
    id: str
    name: str | None = None
    login: str | None = None
    commits: int
    areas: list[str] = Field(default_factory=list)


class BriefingResponse(BaseModel):
    repo: str
    description: str | None = None
    url: str | None = None
    languages: list[str] = Field(default_factory=list)
    head_sha: str | None = None
    indexed_at_iso: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    summary: list[str] = Field(default_factory=list)
    areas: list[AreaBrief] = Field(default_factory=list)
    guarded: list[Guarded] = Field(default_factory=list)
    changes: list[Change] = Field(default_factory=list)
    people: list[PersonBrief] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)
    cypher: list[CypherCall] = Field(default_factory=list)
    ms: float | None = None


def _card(row: dict[str, Any]) -> DecisionCard:
    from untangle.answer.service import decision_card

    return decision_card(version_from_row({**row, "about": row.get("about") or []}))


def briefing(repo: str, *, graph: Graph | None = None) -> BriefingResponse:
    from untangle.answer import service
    from untangle.answer.service import decision_card, ref_card

    started = time.perf_counter()
    graph = graph or service.get_graph()
    rec = Recorder(graph, timeout_ms=TIMEOUT_MS)
    overview = rec.run("repository_overview", {"repo": repo})
    if not overview:
        raise service.NotFound(f"Repository {repo} has not been ingested.")
    meta = overview[0]
    counts = {k: int(v or 0) for k, v in (meta.get("counts") or {}).items()}

    areas: list[AreaBrief] = []
    for row in rec.run("briefing_areas", {"repo": repo, "nested": NESTED, "limit": 14}):
        commits = int(row.get("commits") or 0)
        people = [AreaPerson(id=p["id"], name=p.get("name"), login=p.get("login"), commits=int(p["commits"]),
                             share=round(int(p["commits"]) / commits, 2) if commits else 0.0)
                  for p in row.get("people") or [] if p and p.get("id") and not _bot(p.get("login") or p.get("name"))]
        areas.append(AreaBrief(name=row["area"], files=int(row.get("files") or 0), commits=commits,
                               last_changed_iso=iso(row.get("last_changed")), decisions=int(row.get("decisions") or 0), people=people))

    guarded: list[Guarded] = []
    for row in rec.run("briefing_guarded", {"repo": repo, "limit": 12}):
        v = version_from_row(row)
        guards, _ = _guards(v, int(row.get("earlier") or 0))
        guarded.append(Guarded(decision=decision_card(v), guards=guards, weight=int(row.get("weight") or 0)))

    changes: list[Change] = []
    for row in rec.run("briefing_changes", {"repo": repo, "limit": 10}):
        source = row.get("source")
        changes.append(Change(newer=_card(row["newer"]), older=_card(row["older"]), at_iso=iso(row.get("at")), signal=row.get("signal"),
                              source=ref_card(source) if source and source.get("id") else None))

    recent = [r for r in rec.run("repo_people", {"repo": repo, "now": int(time.time() * 1000), "limit": 12})
              if not _bot(r.get("login") or r.get("name"))]
    people = _people(areas, recent)

    return BriefingResponse(
        repo=meta.get("repo") or repo, description=meta.get("description"), url=meta.get("url"), languages=list(meta.get("languages") or []),
        head_sha=meta.get("head_sha"), indexed_at_iso=iso(meta.get("ingested_at")), counts=counts,
        summary=_summary(meta.get("repo") or repo, counts, areas, guarded, people), areas=areas, guarded=guarded, changes=changes,
        people=people, questions=_questions(guarded, changes, areas), limits=_limits(counts),
        cypher=rec.calls, ms=round((time.perf_counter() - started) * 1000, 1),
    )


def _people(areas: list[AreaBrief], recent: list[dict[str, Any]]) -> list[PersonBrief]:
    """People to ask: the most active recent authors (34_repo_people weights commits by recency, so current
    maintainers rank above early authors), then anyone who wrote the most of an area, each with their areas."""
    out: dict[str, PersonBrief] = {}
    for row in recent[:6]:
        n = sum(int(p.get("n") or 0) for p in row.get("parts") or [])
        out[row["id"]] = PersonBrief(id=row["id"], name=row.get("name"), login=row.get("login"), commits=n)
    for area in areas:
        if area.people and area.people[0].id not in out:
            lead = area.people[0]
            out[lead.id] = PersonBrief(id=lead.id, name=lead.name, login=lead.login, commits=lead.commits)
    for area in areas:
        for p in area.people:
            if p.id in out and area.name not in out[p.id].areas:
                out[p.id].areas.append(area.name)
    return list(out.values())[:8]


def _summary(repo: str, counts: dict[str, int], areas: list[AreaBrief], guarded: list[Guarded], people: list[PersonBrief]) -> list[str]:
    lines = []
    files = counts.get("current_files") or counts.get("files") or 0
    lines.append(
        f"{repo} has {files:,} current files in {len(areas)} main areas, with {counts.get('commits', 0):,} commits, "
        f"{counts.get('prs', 0):,} pull requests and {counts.get('issues', 0):,} issues indexed."
    )
    if areas:
        busiest = areas[0]
        name = "top-level files" if busiest.name == ROOT else busiest.name
        lead = busiest.people[0] if busiest.people else None
        lines.append(
            f"Most change happens in {name} ({busiest.commits:,} commits)"
            + (f"; {lead.name or lead.login} wrote {round(lead.share * 100)}% of them." if lead else ".")
        )
    active = counts.get("decisions", 0)
    if guarded:
        lines.append(f"{active:,} decisions are recorded. {len(guarded)} of the active ones are backed by an incident, an issue, a revert, "
                     "a handover statement or a long history, so read them before changing what they describe.")
    elif active:
        lines.append(f"{active:,} decisions are recorded, but none carries a linked incident, issue or revert yet, so treat reasons as thin.")
    if people:
        names = ", ".join(p.name or p.login or p.id for p in people[:3])
        lines.append(f"The people with the most authored history are {names}.")
    if counts.get("meetings"):
        lines.append(f"{counts['meetings']} handover call{'s are' if counts['meetings'] != 1 else ' is'} linked to the code.")
    return lines


def _subject(card: DecisionCard) -> str | None:
    for a in card.about:
        if a.label in ("ConfigKey", "Dependency"):
            return a.key or a.name
    for a in card.about:
        if a.path:
            return a.path
    return None


def _questions(guarded: list[Guarded], changes: list[Change], areas: list[AreaBrief]) -> list[str]:
    out: list[str] = []
    for g in guarded:
        d = g.decision
        subject = _subject(d)
        removed = (d.object or "").strip().lower() == "removed"
        pr = d.decided_in.number if d.decided_in and d.decided_in.kind == "PullRequest" else None
        if d.kind == "revert" and d.subject:
            out.append(f"Why was {d.subject[:14]} reverted?")
        elif subject and d.kind == "config_value":
            out.append(f"Why was {subject} removed?" if removed else f"Why is {subject} {d.object}?")
        elif subject and d.kind == "dependency":
            out.append(f"Why was {subject} removed?" if removed else f"Why do we pin {subject} at {d.object}?")
        elif subject and pr:
            out.append(f"Why was {subject} changed in PR #{pr}?")
        elif subject:
            out.append(f"Why was {subject} changed?")
        if len(out) >= 3:
            break
    for c in changes:
        subject = _subject(c.newer)
        if subject and c.newer.kind == "config_value":
            q = f"What changed in {subject}?"
            if q not in out:
                out.append(q)
                break
    for area in areas[:3]:
        if area.name != ROOT and len(out) < 6:
            out.append(f"Who should I ask about {area.name}?")
    return list(dict.fromkeys(out))[:6]


def _limits(counts: dict[str, int]) -> list[str]:
    out = ["Authorship counts show who wrote the history, not who owns the code today or who is available.",
           "Decisions come from configuration and dependency diffs, pull requests, reverts, documents and handover calls. "
           "Reasons nobody wrote down are not here."]
    if counts.get("prs", 0) == 0:
        out.append("No pull requests are indexed for this repository, so most decisions lack discussion.")
    return out


def briefing_markdown(b: BriefingResponse) -> str:
    """The briefing as a Markdown document with links, for a wiki page, a handover note or a coding agent."""
    lines = [f"# Day-one briefing: {b.repo}", ""]
    if b.description:
        lines += [b.description, ""]
    meta = []
    if b.head_sha:
        meta.append(f"snapshot `{b.head_sha[:7]}`")
    if b.indexed_at_iso:
        meta.append(f"indexed {b.indexed_at_iso[:10]}")
    if meta:
        lines += ["_" + ", ".join(meta) + "_", ""]
    lines += [*[f"- {s}" for s in b.summary], ""]
    if b.areas:
        lines += ["## Code areas", "", "| Area | Files | Commits | Last change | Main authors | Active decisions |", "|---|---|---|---|---|---|"]
        for a in b.areas:
            authors = ", ".join(f"{p.name or p.login} ({round(p.share * 100)}%)" for p in a.people[:2]) or "-"
            lines.append(f"| {a.name} | {a.files} | {a.commits} | {(a.last_changed_iso or '')[:10] or '-'} | {authors} | {a.decisions} |")
        lines.append("")
    if b.guarded:
        lines += ["## Read before changing", ""]
        for g in b.guarded:
            src = g.decision.decided_in
            link = f" ([{_ref_name({'id': src.id, 'labels': [src.kind], 'number': src.number, 'title': src.title})}]({src.url}))" if src and src.url else ""
            lines.append(f"- **{g.decision.text or g.decision.object}**{link}")
            for guard in g.guards[:3]:
                lines.append(f"  - {guard}")
        lines.append("")
    if b.changes:
        lines += ["## Recently replaced", ""]
        for c in b.changes:
            when = fmt_date(c.at_iso) or (c.at_iso or "")[:10]
            lines.append(f"- {when}: {c.older.text or c.older.object} → {c.newer.text or c.newer.object}" + (f" ([source]({c.source.url}))" if c.source and c.source.url else ""))
        lines.append("")
    if b.people:
        lines += ["## Who to ask", ""]
        for p in b.people:
            lines.append(f"- **{p.name or p.login}**" + (f" (@{p.login})" if p.login and p.name else "") + f": {p.commits} recent commits" + (f", mostly in {', '.join(p.areas[:3])}" if p.areas else ""))
        lines.append("")
    if b.questions:
        lines += ["## Questions to ask Untangle", "", *[f"- {q}" for q in b.questions], ""]
    lines += ["## Limits", "", *[f"- {x}" for x in b.limits], ""]
    return "\n".join(lines)


__all__ = ["BriefingResponse", "briefing", "briefing_markdown"]

