"""Optional rationale extraction from the most-discussed merged pull requests with `untangle.llm.make_llm()`.

The model reads a PR's title, body, reviews and comments and returns decisions as strict JSON. Every decision
must quote the thread verbatim; the quote is located in the PR body or a comment and that node becomes the
EVIDENCED_BY target. No matching quote, no decision: the graph never carries a claim it cannot show.
With the fake backend (no key configured) the stage is a silent no-op."""

from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from untangle import ids
from untangle.ingest.decisions import DecisionRow, make_decision
from untangle.ingest.github_api import PullRecord
from untangle.llm import LLM, LLMUnavailable, make_llm

log = logging.getLogger("untangle.ingest.extract_llm")

MAX_PROMPT_CHARS = 14_000
MAX_BODY_CHARS = 3000
MAX_COMMENT_CHARS = 700
MIN_QUOTE_CHARS = 12
PREDICATES = ("chose", "constraint", "workaround_for", "deprecated", "owner")

SYSTEM_PROMPT = """You extract engineering decisions from a GitHub pull request thread.
Return one JSON object: {"decisions": [{"subject": str, "predicate": "chose"|"constraint"|"workaround_for"|"deprecated"|"owner",
"object": str, "rationale": str, "about_paths": [file paths from the thread], "quotes": [verbatim snippets copied exactly from the thread],
"confidence": 0..1}]}.
Rules: only decisions the thread actually states (a choice, a constraint, a workaround for a bug, a deprecation, an owner);
subject is the thing decided about (a file, setting, library, component); object is the choice; rationale is the stated reason;
every decision needs at least one quote copied character-for-character from the thread (no paraphrase);
return {"decisions": []} when nothing is decided. Nothing but the JSON object."""


class ExtractedDecision(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    predicate: Literal["chose", "constraint", "workaround_for", "deprecated", "owner"]
    object: str = Field(min_length=1, max_length=500)
    rationale: str | None = Field(default=None, max_length=2000)
    about_paths: list[str] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)
    confidence: float = 0.6


class Extraction(BaseModel):
    decisions: list[ExtractedDecision] = Field(default_factory=list)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def thread_prompt(pr: PullRecord) -> str:
    parts = [f"PR #{pr.number}: {pr.title}", "", "BODY:", (pr.body or "")[:MAX_BODY_CHARS], ""]
    for r in pr.reviews:
        if r.body.strip():
            parts.append(f"REVIEW by {r.author_login or 'unknown'} ({r.state}): {r.body[:MAX_COMMENT_CHARS]}")
    for c in pr.review_comments:
        where = f" on {c.path}:{c.line}" if c.path else ""
        parts.append(f"REVIEW COMMENT by {c.author_login or 'unknown'}{where}: {c.body[:MAX_COMMENT_CHARS]}")
    for c in pr.comments:
        parts.append(f"COMMENT by {c.author_login or 'unknown'}: {c.body[:MAX_COMMENT_CHARS]}")
    text = "\n".join(parts)
    return text[:MAX_PROMPT_CHARS]


def _evidence_index(repo: str, pr: PullRecord) -> list[tuple[str, str, str | None]]:
    """`(node id, normalised body, author login)` for everything in the thread a quote can land in."""
    index = [(ids.pr_id(repo, pr.number), _norm(f"{pr.title}\n{pr.body}"), pr.author_login)]
    for r in pr.reviews:
        if r.body.strip():
            index.append((ids.comment_id(repo, "pr_review", r.id), _norm(r.body), r.author_login))
    for c in pr.review_comments + pr.comments:
        index.append((ids.comment_id(repo, c.kind, c.id), _norm(c.body), c.author_login))
    return index


def locate_quotes(quotes: list[str], index: list[tuple[str, str, str | None]]) -> list[tuple[str, str | None]]:
    """Node ids (and their authors) whose body contains a quote (whitespace/case-insensitive)."""
    hits: list[tuple[str, str | None]] = []
    for quote in quotes:
        q = _norm(quote)
        if len(q) < MIN_QUOTE_CHARS:
            continue
        for node_id, body, author in index:
            if q in body and all(node_id != h[0] for h in hits):
                hits.append((node_id, author))
    return hits


def most_discussed(prs: list[PullRecord], top_n: int) -> list[PullRecord]:
    merged = [pr for pr in prs if pr.merged]
    merged.sort(key=lambda pr: (-pr.discussion_size, -(pr.merged_at or 0), -pr.number))
    return merged[:top_n]


def extract_pr_rationales(
    repo: str,
    prs: list[PullRecord],
    *,
    top_n: int,
    llm: LLM | None = None,
    known_paths: set[str] | None = None,
    person_id_for_login: dict[str, str] | None = None,
) -> list[DecisionRow]:
    """`rationale` decisions (signal `llm_pr_thread`) for the `top_n` most-discussed merged PRs."""
    if top_n <= 0:
        return []
    llm = llm or make_llm()
    if not llm.available:
        log.info("LLM backend is fake; skipping rationale extraction")
        return []
    known_paths = known_paths or set()
    person_id_for_login = person_id_for_login or {}
    rows: list[DecisionRow] = []
    for pr in most_discussed(prs, top_n):
        try:
            extraction = llm.complete_json(SYSTEM_PROMPT, thread_prompt(pr), Extraction)
        except (LLMUnavailable, ValidationError, ValueError) as exc:
            log.warning("PR #%s: extraction failed (%s)", pr.number, str(exc)[:160])
            continue
        index = _evidence_index(repo, pr)
        for i, dec in enumerate(extraction.decisions):
            hits = locate_quotes(dec.quotes, index)
            if not hits:
                log.debug("PR #%s: dropping decision %r (no verbatim quote found)", pr.number, dec.subject)
                continue
            key = f"{dec.subject.strip()}|{dec.predicate}"
            row = make_decision(
                repo, "rationale", key, f"{pr.number}:{i}",
                subject=dec.subject.strip(), predicate=dec.predicate, object=dec.object.strip(),
                text=_sentence(dec.subject.strip(), dec.predicate, dec.object.strip(), pr.number),
                rationale=(dec.rationale or "").strip() or None, valid_from=pr.merged_at or pr.created_at or 0,
                confidence=min(0.8, max(0.5, float(dec.confidence or 0.6))), signal="llm_pr_thread",
            )
            row.link("DECIDED_IN", ids.pr_id(repo, pr.number))
            for node_id, _author in hits:
                row.link("EVIDENCED_BY", node_id)
            stated_by = next((a for _, a in hits if a), None) or pr.author_login
            if stated_by:
                row.link("STATED_BY", person_id_for_login.get(stated_by.lower(), ids.person_id(login=stated_by)))
            for path in dec.about_paths:
                p = path.strip().lstrip("./")
                if p in known_paths:
                    row.link("ABOUT", ids.file_id(repo, p))
            rows.append(row)
    log.info("extracted %d rationale decisions from %d PR threads", len(rows), min(top_n, len(prs)))
    return rows


def _sentence(subject: str, predicate: str, obj: str, number: int) -> str:
    verb = {
        "chose": "chose", "constraint": "is constrained by", "workaround_for": "works around", "deprecated": "deprecated",
        "owner": "is owned by",
    }[predicate]
    return f"{subject} {verb} {obj} (PR #{number})"


__all__ = ["ExtractedDecision", "Extraction", "SYSTEM_PROMPT", "extract_pr_rationales", "locate_quotes", "most_discussed", "thread_prompt"]
