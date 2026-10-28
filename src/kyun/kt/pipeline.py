"""`ingest_kt`: one handover call into the graph.

Writes, in order: the `Meeting` (+`ABOUT_REPO`), one `Person` per speaker label (resolved to an existing contributor
when the transcript gives a GitHub login or an e-mail; `Identity` of kind `speaker` either way), the `Utterance`
rows with `HAS`, `SPOKEN_BY` and `NEXT`, `MENTIONS` links to the repository's entities, the extracted `kt`
decisions through `21_record_decision` (same `key` convention as the code-history decisions, so a spoken config
value confirms or supersedes the committed one) and `22_link_decision` (ABOUT / DECIDED_IN / EVIDENCED_BY /
STATED_BY), and finally one `Chunk` per utterance with an embedding for the vector baseline.

Entity matching is guarded for precision: an utterance MENTIONS an entity only when the text contains one of its
identifiers as a whole token, and an identifier only counts when it is unambiguous - it contains `_`, `.` or `/`
(`app.concurrency`, `queries.sql`, `internal/manager`) or has at least two tokens (`NewManager`, "lib pq").
The catalogue comes from `47_kt_repo_keyterms` (entities ranked by how often their file was touched); terms the model
produces that are not in the catalogue are resolved through the `entity_search` full-text index (`48_kt_resolve_entities`)
with the same guard."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from kyun import ids
from kyun.embed import Embedder, make_embedder
from kyun.graph.db import Graph, Neo4jError
from kyun.graph.queries import load_cypher
from kyun.kt.extract import Extraction, KtDecision, extract_decisions
from kyun.kt.transcript import (
    Utterance,
    as_utterances,
    clean_label,
    clean_text,
    guess_language,
    has_devanagari,
    parse_started_at,
)
from kyun.llm import LLM

log = logging.getLogger("kyun.kt.pipeline")

MENTION_LABELS = ("File", "Symbol", "ConfigKey", "Dependency")
ABOUT_LABELS = (*MENTION_LABELS, "Module")
_LABEL_PRIORITY = {"ConfigKey": 0, "File": 1, "Module": 2, "Dependency": 3, "Symbol": 4}
_HOST_PREFIXES = ("github.com/", "gitlab.com/", "bitbucket.org/", "golang.org/x/", "gopkg.in/", "google.golang.org/")
_VERSION_SEGMENT = re.compile(r"^v\d+$")
KT_CONFIDENCE_DEFAULT = 0.6
CATALOGUE_LIMIT = 5000


# ---------- entities ----------


def guard_ok(alias: str) -> bool:
    """Precision guard: `_`, `.` or `/` in the identifier, or at least two tokens."""
    return any(c in alias for c in "_./") or len(ids.tokens(alias).split()) >= 2


def dependency_short_name(name: str) -> str:
    """`github.com/labstack/echo/v4` -> `echo`, `@types/node` -> `node`, `lib/pq` -> `pq`."""
    parts = [p for p in name.split("/") if p and not _VERSION_SEGMENT.match(p)]
    return (parts[-1] if parts else name).lstrip("@")


def build_aliases(label: str, name: str | None, path: str | None, key: str | None) -> tuple[str, ...]:
    """Identifiers an utterance may use for this entity, all passing the guard. Spoken forms (`app concurrency`,
    `lib pq`) are included as two-token phrases because speech-to-text drops the punctuation."""
    cands: list[str | None] = []
    if label == "ConfigKey" and key:
        cands += [key, key.rsplit(".", 1)[-1] if "." in key else None, ids.tokens(key)]
    elif label == "File":
        cands += [path, name]
    elif label == "Module":
        cands += [path, name]
    elif label == "Symbol":
        cands += [name, ids.tokens(name or "")]
    elif label == "Dependency" and name:
        short = name
        for host in _HOST_PREFIXES:
            if short.startswith(host):
                short = short[len(host) :]
                break
        segs = [s for s in short.split("/") if s]
        last_two = "/".join(segs[-2:]) if len(segs) >= 2 else None
        cands += [name, short, last_two, ids.tokens(last_two or short)]
    out: list[str] = []
    for c in cands:
        c = clean_text(c)
        if c and guard_ok(c) and c.lower() not in {o.lower() for o in out} and c not in (".", "/"):
            out.append(c)
    return tuple(out)


@dataclass(frozen=True)
class EntityRef:
    id: str
    label: str
    name: str
    path: str | None
    key: str | None
    tokens: str | None
    aliases: tuple[str, ...]

    @property
    def canonical(self) -> str:
        """The `subject` form shared with the code-history decisions: `config.toml::app.concurrency`, a file or
        module path, `path::Symbol`, a dependency name."""
        if self.label == "ConfigKey":
            return f"{self.path}::{self.key}" if self.path else str(self.key)
        if self.label in ("File", "Module"):
            return self.path or self.name
        if self.label == "Symbol":
            return f"{self.path}::{self.name}" if self.path else self.name
        return self.name

    @classmethod
    def from_row(cls, r: Mapping[str, Any]) -> EntityRef:
        label = str(r.get("label") or "")
        name = str(r.get("name") or r.get("key") or r.get("path") or "")
        return cls(str(r["id"]), label, name, r.get("path"), r.get("key"), r.get("tokens"), build_aliases(label, name, r.get("path"), r.get("key")))


def _alias_pattern(alias: str) -> re.Pattern[str]:
    if " " in alias:
        return re.compile(r"(?<!\w)" + r"\W+".join(re.escape(p) for p in alias.split()) + r"(?!\w)", re.IGNORECASE)
    return re.compile(r"(?<![\w./-])" + re.escape(alias) + r"(?![\w./-])", re.IGNORECASE)


class Matcher:
    """Whole-token matching of a text against the entity catalogue."""

    def __init__(self, entities: Iterable[EntityRef]):
        self.entities = list(entities)
        self._by_alias: dict[str, EntityRef] = {}
        self._patterns: list[tuple[str, re.Pattern[str], EntityRef]] = []
        for e in sorted(self.entities, key=lambda e: _LABEL_PRIORITY.get(e.label, 9)):
            for alias in e.aliases:
                self._by_alias.setdefault(alias.lower(), e)
                self._patterns.append((alias, _alias_pattern(alias), e))

    @property
    def aliases(self) -> list[str]:
        return [alias for alias, _, _ in self._patterns]

    def exact(self, term: str) -> EntityRef | None:
        return self._by_alias.get(clean_text(term).lower())

    def find(self, text: str, labels: Sequence[str] | None = None) -> list[tuple[EntityRef, str]]:
        """(entity, matched alias) pairs in order of first appearance, one per entity; longer matches win."""
        low = text.lower()
        hits: list[tuple[int, int, EntityRef, str]] = []
        for alias, pat, e in self._patterns:
            if labels and e.label not in labels:
                continue
            if alias.lower().split(" ")[0] not in low:
                continue
            m = pat.search(text)
            if m:
                hits.append((m.start(), -(m.end() - m.start()), e, alias))
        hits.sort(key=lambda h: (h[0], h[1], _LABEL_PRIORITY.get(h[2].label, 9)))
        out: list[tuple[EntityRef, str]] = []
        seen: set[str] = set()
        last_end = -1
        for start, neg_len, e, alias in hits:
            end = start - neg_len
            if start < last_end or e.id in seen:
                continue
            seen.add(e.id)
            last_end = end
            out.append((e, alias))
        return out


def entity_catalogue(graph: Graph, repo: str, *, limit: int = CATALOGUE_LIMIT) -> list[EntityRef]:
    """The repository's entities (most-touched first) via `47_kt_repo_keyterms`."""
    rows = graph.run_named("kt_repo_keyterms", {"repo": repo, "limit": int(limit)}).records
    return [EntityRef.from_row(r) for r in rows if r.get("id")]


def keyterms_from_catalogue(entities: Sequence[EntityRef], *, limit: int = 50) -> list[str]:
    """Spoken-form names for Sarvam `keyterms`: config keys, file basenames, symbol names, dependency short names."""
    out: list[str] = []
    seen: set[str] = set()
    for e in entities:
        if e.label == "ConfigKey":
            term = e.key or e.name
        elif e.label == "Dependency":
            term = dependency_short_name(e.name)
            if len(term) < 3:  # "pq" alone is not a useful keyterm; "lib/pq" is what people say
                term = "/".join(e.name.rstrip("/").split("/")[-2:])
        elif e.label == "Module":
            term = e.name
        else:
            term = e.name
        term = clean_text(term)
        if len(term) < 3 or term.lower() in seen:
            continue
        seen.add(term.lower())
        out.append(term)
        if len(out) >= limit:
            break
    return out


def keyterms_for_repo(graph: Graph, repo: str, *, limit: int = 50) -> list[str]:
    """Most-touched file basenames, symbol names, config keys and dependency names of `repo` (<= `limit`)."""
    return keyterms_from_catalogue(entity_catalogue(graph, repo, limit=max(limit * 4, 200)), limit=limit)


def resolve_term(term: str, matcher: Matcher, graph: Graph | None = None, repo: str | None = None, *, labels: Sequence[str] = ABOUT_LABELS) -> EntityRef | None:
    """A spoken/model term -> entity: exact alias in the catalogue, else a `entity_search` hit that passes the guard
    (the term equals one of the hit's aliases, or all of the term's >= 2 tokens are in the hit's tokens)."""
    term = clean_text(term)
    if not term:
        return None
    hit = matcher.exact(term)
    if hit and hit.label in labels:
        return hit
    found = [e for e, _ in matcher.find(term, labels) if e.aliases]
    for e in found:  # the term is just the identifier with punctuation spoken away ("app concurrency")
        if ids.tokens(e.aliases[0]) == ids.tokens(term):
            return e
    if graph is None or repo is None or not guard_ok(term):
        return None
    toks = [t for t in ids.tokens(term).split() if len(t) > 1]
    if not toks:
        return None
    q = " OR ".join(re.sub(r"[^0-9A-Za-zऀ-ॿ]", "", t) for t in toks)
    try:
        rows = graph.run_named("kt_resolve_entities", {"repo": repo, "q": q, "limit": 10}).records
    except Neo4jError as exc:
        log.warning("entity_search failed for %r: %s", term, exc)
        return None
    term_lc, term_tokens = term.lower(), set(toks)
    for r in rows:
        e = EntityRef.from_row(r)
        if e.label not in labels:
            continue
        if term_lc in {a.lower() for a in e.aliases}:
            return e
        have = set((e.tokens or ids.tokens(e.name)).split())
        if len(term_tokens) >= 2 and term_tokens <= have:
            return e
    return None


# ---------- speakers ----------


def _speaker_entry(value: Any) -> dict[str, str | None]:
    if isinstance(value, Mapping):
        return {"name": clean_text(value.get("name")) or None, "login": clean_text(value.get("login")) or None, "email": clean_text(value.get("email")) or None}
    return {"name": clean_text(value) or None, "login": None, "email": None}


def speaker_rows(meeting_id: str, speakers: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for label, info in speakers.items():
        name, login, email = info.get("name"), info.get("login"), info.get("email")
        login = login.lstrip("@") if login else None
        if login:
            fallback = ids.person_id(login=login)
        elif email:
            fallback = ids.person_id(email=email)
        elif name:
            fallback = ids.person_id(name=name)
        else:
            fallback = ids.person_id(name=f"{meeting_id}/{label}")
        identity_value = f"{meeting_id}/{label}"
        rows.append(
            {
                "label": label, "name": name or label, "login": login, "login_lc": login.lower() if login else None,
                "email": email, "email_lc": email.lower() if email else None, "fallback_id": fallback,
                "identity_id": ids.identity_id("speaker", identity_value), "identity_value": identity_value,
                "tokens": ids.tokens(" ".join(x for x in (name, login) if x)) or None,
            }
        )
    return rows


# ---------- decisions ----------

_TEXT = {
    "config_value": "{s} is {o}",
    "owner": "{s} is owned by {o}",
    "deprecated": "{s} is deprecated",
    "workaround_for": "{s} is a workaround for {o}",
    "constraint": "{s} constraint: {o}",
    "chose": "{s}: chose {o}",
    "kt_said": "{s}: {o}",
}


def decision_sentence(subject: str, predicate: str, obj: str, speaker: str, title: str) -> str:
    body = _TEXT.get(predicate, "{s}: {o}").format(s=subject, o=obj)
    if predicate == "deprecated" and obj and obj.lower() != subject.lower():
        body += f": {obj}"
    return f'{body} (said by {speaker} in KT "{title}")'


def meeting_slug(title: str, started_at: int | None, anchor: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (title or "meeting").lower()).strip("-")[:60] or "meeting"
    if started_at:
        stamp = time.strftime("%Y%m%d", time.gmtime(started_at / 1000))
        return f"{base}-{stamp}"
    return f"{base}-{ids.digest(title or '', anchor, n=8)}"


# ---------- the pipeline ----------


def ingest_kt(
    graph: Graph,
    repo: str,
    *,
    title: str,
    utterances: Iterable[Utterance | Mapping[str, Any]],
    speakers: Mapping[str, Any] | None = None,
    started_at: int | str | None = None,
    language: str | None = None,
    audio_uri: str | None = None,
    llm: LLM | None = None,
    embedder: Embedder | None = None,
    source: str = "transcript-json",
    sarvam: Any | None = None,
    translate: bool = True,
    summary: str | None = None,
    catalogue_limit: int = CATALOGUE_LIMIT,
    now: int | None = None,
) -> dict[str, Any]:
    """Load one call. `utterances` are normalised rows (`kyun.kt.transcript`); `speakers` maps labels to
    `{name, login, email}` (or a bare name); `started_at` is epoch ms or ISO-8601; `sarvam` is a `SarvamClient`
    (or anything with `translate(text, ...)` / `identify_language(text)`) used for `text_en` and language id when
    given. Returns a summary dict with the meeting id, counts and the recorded decisions."""
    now = int(now or time.time() * 1000)
    rows = as_utterances(utterances)
    if not rows:
        raise ValueError("ingest_kt: the transcript has no utterances")
    title = clean_text(title) or "Handover call"
    speakers_map: dict[str, dict[str, str | None]] = {clean_label(k): _speaker_entry(v) for k, v in (speakers or {}).items()}
    for label in dict.fromkeys(u.speaker_label for u in rows):
        speakers_map.setdefault(label, {"name": None, "login": None, "email": None})
    started = started_at if isinstance(started_at, int) else parse_started_at(started_at)
    duration_ms = max(u.end_ms for u in rows)
    meeting_start = started if started else now - duration_ms
    mid = ids.meeting_id(repo, meeting_slug(title, started, rows[0].text))
    display = {label: (info.get("name") or label) for label, info in speakers_map.items()}

    # entities of the repository (may be empty when the code history has not been ingested yet)
    try:
        catalogue = entity_catalogue(graph, repo, limit=catalogue_limit)
    except Neo4jError as exc:
        log.warning("entity catalogue unavailable for %s: %s", repo, exc)
        catalogue = []
    matcher = Matcher(catalogue)
    keyterms = keyterms_from_catalogue(catalogue, limit=50)

    # language: given > per-utterance > Sarvam text-lid > script guess
    language = language or next((u.language for u in rows if u.language), None)
    if not language and sarvam is not None:
        try:
            language = sarvam.identify_language(" ".join(u.text for u in rows[:5])[:1000]).get("language_code")
        except Exception as exc:  # noqa: BLE001 - LID is best effort
            log.warning("language identification failed: %s", exc)
    language = language or guess_language(" ".join(u.text for u in rows)) or None
    for u in rows:
        u.language = u.language or language

    # English rendering (best effort; stops after three consecutive failures)
    text_en: dict[int, str] = {}
    failures = 0
    if sarvam is not None and translate:
        for u in rows:
            if u.language == "en-IN" and not has_devanagari(u.text):
                text_en[u.seq] = u.text
                continue
            try:
                text_en[u.seq] = sarvam.translate(u.text, source="auto", target="en-IN", mode="code-mixed")
                failures = 0
            except Exception as exc:  # noqa: BLE001
                failures += 1
                log.warning("translate failed for utterance %d: %s", u.seq, exc)
                if failures >= 3:
                    log.warning("giving up on translation after three consecutive failures")
                    break

    # -- writes ------------------------------------------------------------------------------------
    graph.run_named(
        "kt_upsert_meeting",
        {"m": {"id": mid, "repo": repo, "title": title, "started_at": meeting_start, "duration_ms": duration_ms, "language": language, "source": source, "audio_uri": audio_uri, "summary": summary}, "now": now},
        write=True,
    )
    person_by_label: dict[str, str] = {}
    for r in graph.run_named("kt_upsert_speakers", {"rows": speaker_rows(mid, speakers_map)}, write=True).records:
        person_by_label[str(r["label"])] = str(r["person_id"])

    utt_rows = [
        {
            "id": ids.utterance_id(mid, u.seq), "repo": repo, "meeting_id": mid, "seq": u.seq, "text": u.text,
            "text_en": text_en.get(u.seq), "start_ms": u.start_ms, "end_ms": u.end_ms, "speaker_label": u.speaker_label,
            "speaker_name": display.get(u.speaker_label), "language": u.language, "person_id": person_by_label.get(u.speaker_label),
        }
        for u in rows
    ]
    graph.write_batches(load_cypher("kt_upsert_utterances"), utt_rows)
    graph.run_named("kt_link_utterance_next", {"meeting_id": mid}, write=True)

    mention_rows: list[dict[str, Any]] = []
    for u in rows:
        for e, alias in matcher.find(u.text, MENTION_LABELS):
            mention_rows.append({"utterance_id": ids.utterance_id(mid, u.seq), "entity_id": e.id, "term": alias})
    mentions = 0
    if mention_rows:
        mentions = int(graph.write_batches(load_cypher("kt_link_mentions"), mention_rows))

    extraction = extract_decisions(rows, keyterms=keyterms, terms=matcher.aliases, llm=llm, speakers=speakers_map)
    decision_rows, link_rows, recorded = _decision_rows(repo, mid, title, rows, extraction, matcher, graph, person_by_label, display, meeting_start, now)
    results: list[dict[str, Any]] = []
    graph.run_named("prune_kt_meeting", {"meeting_id": mid, "keep": [r["id"] for r in decision_rows]}, write=True)
    if decision_rows:
        for r in graph.run_named("record_decision", {"rows": decision_rows, "now": now}, write=True).records:
            results.append({"id": r["id"], "status": r["status"], "superseded": list(r["superseded"] or [])})
        graph.query(load_cypher("link_decision"), {"rows": link_rows, "now": now})
    by_id = {r["id"]: r for r in results}
    for d in recorded:
        d.update(by_id.get(d["id"], {}))
    reconcile_rows = [
        {"kt_id": d["id"], "code_key": d["code_key"], "object": d["object"],
         "dotted_key": d["subject"].split("::", 1)[1] if "::" in d["subject"] else None}
        for d in recorded if d["predicate"] == "config_value"
    ]
    if reconcile_rows:
        graph.run_named("clear_kt_reconcile", {"ids": [r["kt_id"] for r in reconcile_rows]}, write=True)
        for r in graph.run_named("reconcile_kt", {"repo": repo, "rows": reconcile_rows, "now": now}, write=True).records:
            for d in recorded:
                if d["id"] == r["kt_id"]:
                    d.setdefault(r["relation"], []).append(r["code_id"])

    chunks = _write_chunks(graph, repo, mid, rows, text_en, display, embedder, now)
    log.info("KT %s: %d utterances, %d mentions, %d decisions (%s), %d chunks", mid, len(rows), mentions, len(recorded), extraction.signal, chunks)
    return {
        "meeting_id": mid, "repo": repo, "title": title, "source": source, "language": language, "started_at": meeting_start,
        "duration_ms": duration_ms, "utterances": len(rows), "speakers": person_by_label, "mentions": mentions,
        "translated": len(text_en), "keyterms": keyterms, "decisions": recorded, "decision_signal": extraction.signal,
        "llm": {"backend": extraction.backend, "model": extraction.model, "used": extraction.llm_used, "errors": extraction.errors},
        "chunks": chunks,
    }


def _decision_rows(
    repo: str, mid: str, title: str, rows: Sequence[Utterance], extraction: Extraction, matcher: Matcher, graph: Graph,
    person_by_label: Mapping[str, str], display: Mapping[str, str], meeting_start: int, now: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_seq = {u.seq: u for u in rows}
    decision_rows: list[dict[str, Any]] = []
    link_rows: list[dict[str, Any]] = []
    recorded: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    first_by_key: dict[str, int] = {}  # non-value predicates: one decision per key per meeting, later evidence merged
    for d in extraction.decisions:
        entity = _resolve_decision_entity(d, matcher, graph, repo)
        subject = entity.canonical if entity else d.subject
        seqs = sorted(s for s in set(d.utterance_seqs) if s in by_seq)
        if not seqs:
            seqs = [u.seq for u in rows if d.subject.lower() in u.text.lower()][:1]
        if not seqs:
            log.info("dropping decision without evidence: %s %s %s", d.subject, d.predicate, d.object)
            continue
        first = by_seq[seqs[0]]
        speaker_label = d.speaker_label if d.speaker_label in person_by_label else first.speaker_label
        # Spoken statements get their own key space: a later call can update an earlier call, but speech never
        # supersedes what the repository records (24_reconcile_kt links the two as CONFIRMS / CONTRADICTS instead).
        code_key = f"{subject}|{d.predicate}".lower()
        key = f"kt|{code_key}"
        if d.predicate != "config_value" and key in first_by_key:
            earlier = recorded[first_by_key[key]]
            for s in seqs:
                if s not in earlier["utterance_seqs"]:
                    earlier["utterance_seqs"].append(s)
                    link_rows.append({"decision_id": earlier["id"], "rel": "EVIDENCED_BY", "target_id": ids.utterance_id(mid, s), "props": {}})
            continue
        did = ids.decision_id(repo, "kt", key, f"{mid}#{seqs[0]}")
        if did in seen_ids:
            continue
        seen_ids.add(did)
        if d.predicate != "config_value":
            first_by_key[key] = len(recorded)
        text = decision_sentence(subject, d.predicate, d.object, display.get(speaker_label, speaker_label), title)
        valid_from = meeting_start + first.start_ms
        decision_rows.append(
            {
                "id": did, "repo": repo, "kind": "kt", "key": key, "subject": subject, "predicate": d.predicate, "object": d.object,
                "text": text, "rationale": d.rationale, "valid_from": valid_from, "confidence": round(float(d.confidence), 3),
                "signal": extraction.signal, "created_at": now,
            }
        )
        link_rows.append({"decision_id": did, "rel": "DECIDED_IN", "target_id": mid, "props": {}})
        if entity:
            link_rows.append({"decision_id": did, "rel": "ABOUT", "target_id": entity.id, "props": {}})
        for s in seqs:
            link_rows.append({"decision_id": did, "rel": "EVIDENCED_BY", "target_id": ids.utterance_id(mid, s), "props": {}})
        person = person_by_label.get(speaker_label)
        if person:
            link_rows.append({"decision_id": did, "rel": "STATED_BY", "target_id": person, "props": {}})
        recorded.append(
            {
                "id": did, "key": key, "code_key": code_key, "subject": subject, "predicate": d.predicate, "object": d.object, "rationale": d.rationale,
                "text": text, "speaker_label": speaker_label, "speaker": display.get(speaker_label, speaker_label), "person_id": person,
                "utterance_seqs": seqs, "about": entity.id if entity else None, "about_label": entity.label if entity else None,
                "valid_from": valid_from, "confidence": round(float(d.confidence), 3), "signal": extraction.signal,
            }
        )
    return decision_rows, link_rows, recorded


def _resolve_decision_entity(d: KtDecision, matcher: Matcher, graph: Graph, repo: str) -> EntityRef | None:
    for term in [*d.about_terms, d.subject]:
        e = resolve_term(term, matcher, graph, repo)
        if e:
            return e
    return None


def _write_chunks(graph: Graph, repo: str, mid: str, rows: Sequence[Utterance], text_en: Mapping[int, str], display: Mapping[str, str], embedder: Embedder | None, now: int) -> int:
    embedder = embedder or make_embedder()
    texts = []
    for u in rows:
        t = f"{display.get(u.speaker_label, u.speaker_label)}: {u.text}"
        if text_en.get(u.seq) and text_en[u.seq] != u.text:
            t = f"{t}\n{text_en[u.seq]}"
        texts.append(t)
    vectors = embedder.embed(texts) if texts else []
    chunk_rows = [
        {"id": ids.chunk_id(ids.utterance_id(mid, u.seq), 0), "repo": repo, "text": texts[i], "source_id": ids.utterance_id(mid, u.seq), "seq": u.seq, "created_at": now, "embedding": vectors[i]}
        for i, u in enumerate(rows)
    ]
    return int(graph.write_batches(load_cypher("kt_upsert_utterance_chunks"), chunk_rows, batch_size=200)) if chunk_rows else 0


__all__ = [
    "ABOUT_LABELS",
    "CATALOGUE_LIMIT",
    "MENTION_LABELS",
    "EntityRef",
    "Matcher",
    "build_aliases",
    "decision_sentence",
    "dependency_short_name",
    "entity_catalogue",
    "guard_ok",
    "ingest_kt",
    "keyterms_for_repo",
    "keyterms_from_catalogue",
    "meeting_slug",
    "resolve_term",
    "speaker_rows",
]
