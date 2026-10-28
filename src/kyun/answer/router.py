"""Question routing: classify the intent, pull candidate terms out of the question (paths, dotted config keys,
identifiers, quoted strings, `#123` references, dependency-like names and plain content words), sanitise them for
Lucene, and resolve them to graph entities with a match strength the confidence score can use.

Everything here is deterministic; no model is involved."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from kyun.answer.text import parse_at
from kyun.ids import tokens

if TYPE_CHECKING:
    from kyun.answer.retrieve import Recorder

log = logging.getLogger("kyun.answer.router")

INTENTS = ("why", "who_to_ask", "what_changed", "belief_at", "is_current", "list_decisions")

STOPWORDS = frozenset(
    """a an the and or but if then else of to in on at by for from with without as is are was were be been being am
    do does did done has have had having why what when where which who whom whose how it its this that these those
    there here we our us you your they their them he she his her i me my mine can could should would will shall may
    might must not no yes so such than too very just also still again ever never now currently current get got make
    made like about into over under before after since until during per via vs versus please tell explain show know
    reason reasons because cause caused did does kyun kya kyu kyon hai hain kaise kab kahan kaun kyunki ye yeh woh wo
    ka ki ke ko se me mein par bhi tha thi hum aap tum one some any all each every both either neither more most much
    many few less least own same other another really actually exactly thing things way ways code repo repository
    project file files""".split()
)

# Words a question uses that are not entity names but still help the decision full-text search.
_INTENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("who_to_ask", re.compile(
        r"\b(who (should|do|can|could|would|to|shall|must) (i|we|one|you)? ?(ask|talk|contact|ping|speak)|who knows|who (owns|owned|maintains|maintained|wrote|understands|is (the )?(owner|expert|maintainer|author))|whom (should|do|can) (i|we)|person to ask|expert on|kisse (puchu|puchen|pooche)|kaun (jaanta|janta))\b",
        re.IGNORECASE,
    )),
    ("list_decisions", re.compile(
        r"\b(list|show|enumerate|all|which|what) (the |all |every )?(recorded )?decisions?\b|\bdecisions? (about|on|for|regarding)\b",
        re.IGNORECASE,
    )),
    ("what_changed", re.compile(
        r"\b(what changed|what has changed|history of|timeline (of|for)|how (has|have|did) .{0,60}(change|evolve)|changes (to|in|of)|when did .{0,60}(change|become|switch|move)|evolution of|changelog for|kab badla|kya badla)\b",
        re.IGNORECASE,
    )),
    ("is_current", re.compile(
        r"\b((do|does|are|is|did|have|has) (we|it|this|that|they|the|our|anyone)? ?.{0,60}\bstill\b|\bstill (true|valid|the case|used|using|current|in (place|use|force|effect)|apply|applies|set|on|there)\b|is (this|that|it|the \w+) (current|up to date|up-to-date|in force|in effect|live)|abhi bhi)",
        re.IGNORECASE,
    )),
    ("belief_at", re.compile(
        r"\b(as of|at the time|back (in|on|then)|what (was|were|did) .{0,80}\b(in|on|at|before|around|during) (\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|on \d{4}-\d{2}-\d{2}|in (19|20)\d{2}\b|before (19|20)\d{2}\b)",
        re.IGNORECASE,
    )),
]

_QUOTED = re.compile(r"[\"'`“”‘’]([^\"'`“”‘’]{2,120})[\"'`“”‘’]")
_REF_NUMBER = re.compile(r"(?:#|\b(?:pr|pull request|issue|bug|ticket)\s*#?)(\d{1,7})\b", re.IGNORECASE)
_SCOPED_NPM = re.compile(r"@[\w-]+/[\w.-]+")
_PATH = re.compile(r"(?<![\w@/])((?:[\w.-]+/)+[\w.-]+)")
_FILE_EXT = (
    "go|py|ts|tsx|js|jsx|mjs|cjs|rs|java|kt|kts|rb|php|cs|c|cc|cpp|h|hpp|m|swift|scala|ex|exs|erl|yaml|yml|toml|json|"
    "md|env|ini|cfg|conf|txt|sql|sh|bash|ps1|proto|html|css|scss|lock|mod|sum|xml|gradle|properties|tf|dockerfile"
)
_FILENAME = re.compile(rf"\b([\w-]+\.(?:{_FILE_EXT}))\b", re.IGNORECASE)
_DOTTED = re.compile(r"\b([A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)+)\b")
_SNAKE = re.compile(r"\b([A-Za-z][\w]*_[\w]+)\b")
# camelCase / PascalCase, including a trailing or inner acronym (`MongoDB`, `PostgreSQL`, `resetDB`, `HTTPServer` is
# caught by the leading branch only when it continues in lower case)
_CAMEL = re.compile(r"\b([a-z]+(?:[A-Z][a-z0-9]*)+|[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+)\b")
_HYPHEN = re.compile(r"\b([a-z][a-z0-9]*(?:-[a-z0-9]+)+)\b")
_DATE_IN_TEXT = re.compile(
    r"(\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?Z?)?|\d{1,2}(?:st|nd|rd|th)? [A-Za-z]{3,9}\.? \d{4}|[A-Za-z]{3,9}\.? \d{1,2}(?:st|nd|rd|th)?,? \d{4}|[A-Za-z]{3,9}\.? \d{4}|\d{4}-\d{2}|\b(?:19|20)\d{2}\b)"
)
_ENGLISH_HYPHEN = frozenset({"side-by-side", "up-to-date", "long-term", "short-term", "built-in", "re-run", "e-mail", "follow-up", "trade-off", "trade-offs"})


@dataclass
class RouterDecision:
    """What the router decided about a question."""

    intent: str = "why"
    terms: list[str] = field(default_factory=list)  # content tokens, mention tokens first
    mentions: list[str] = field(default_factory=list)  # verbatim entity-like strings (paths, keys, identifiers)
    numbers: list[int] = field(default_factory=list)  # `#812` style PR/issue references
    at_ms: int | None = None
    lucene: str = ""  # sanitised full-text query (`app^3 OR concurrency^3 OR limit`)
    question: str = ""
    value_tokens: list[str] = field(default_factory=list)  # bare numbers/values ("5", "true") for is_current checks
    source: str | None = None  # 'kt' when the question asks what was said in a handover call

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent, "terms": self.terms, "mentions": self.mentions, "numbers": self.numbers,
            "at_ms": self.at_ms, "lucene": self.lucene,
        }


@dataclass
class ResolvedEntity:
    """A graph entity the question is (probably) about, with how strongly it matched."""

    id: str
    label: str
    name: str | None
    path: str | None
    key: str | None
    strength: float  # 1.0 exact path/key/name, else token-overlap fraction
    lucene_score: float
    matched: bool  # strength >= threshold
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def display(self) -> str:
        if self.label == "ConfigKey" and self.key:
            return f"{self.key} in {self.path}" if self.path else self.key
        return self.name or self.path or self.key or self.id


def detect_intent(question: str, *, at: str | int | None = None) -> str:
    """`belief_at` whenever an `at` date is given; otherwise the first matching pattern; `why` by default."""
    if at not in (None, ""):
        return "belief_at"
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(question):
            return intent
    return "why"


def extract_mentions(question: str) -> tuple[list[str], list[int]]:
    """Entity-like strings in order of appearance and `#N` references. Mentions are verbatim (case kept)."""
    mentions: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        value = value.strip().strip(".,;:!?")
        if len(value) < 2 or value.lower() in seen or value.lower() in STOPWORDS:
            return
        seen.add(value.lower())
        mentions.append(value)

    numbers = [int(n) for n in _REF_NUMBER.findall(question)]
    stripped = _REF_NUMBER.sub(" ", question)
    for m in _QUOTED.finditer(stripped):
        add(m.group(1))
    for m in _SCOPED_NPM.finditer(stripped):
        add(m.group(0))
    for m in _PATH.finditer(stripped):
        value = m.group(1)
        if re.search(r"\d{1,2}/\d{1,2}", value) or value.lower().startswith(("http", "www.")):
            continue  # dates like 14/03/2023 and URLs are not paths
        add(value)
    for m in _FILENAME.finditer(stripped):
        add(m.group(1))
    for m in _DOTTED.finditer(stripped):
        value = m.group(1)
        if _FILENAME.fullmatch(value) or value.lower() in ("e.g", "i.e", "etc"):
            continue
        add(value)
    for pattern in (_SNAKE, _CAMEL):
        for m in pattern.finditer(stripped):
            add(m.group(1))
    for m in _HYPHEN.finditer(stripped):
        if m.group(1).lower() not in _ENGLISH_HYPHEN:
            add(m.group(1))
    return mentions, list(dict.fromkeys(numbers))


def content_terms(question: str, mentions: list[str]) -> list[str]:
    """Lower-cased tokens worth searching: mention tokens first, then the question's remaining content words."""
    out: list[str] = []
    for mention in mentions:
        out.extend(t for t in tokens(mention).split() if t not in STOPWORDS and len(t) > 1)
    for t in tokens(question).split():
        if t in STOPWORDS or len(t) < 2:
            continue
        out.append(t)
    return list(dict.fromkeys(out))


def value_tokens(question: str) -> list[str]:
    """Bare values the question compares against ("still 5?", "true"): numbers and booleans."""
    found = re.findall(r"(?<![\w.#/-])(\d+(?:\.\d+)?[a-z]{0,3}|true|false|yes|no|on|off|enabled|disabled)(?![\w./-])", question, re.IGNORECASE)
    return [f.lower() for f in found if not re.fullmatch(r"(19|20)\d{2}", f)]


def lucene_query(terms: list[str], boosted: set[str] | None = None, *, boost: int = 3) -> str:
    """`a OR b^3 OR c` of plain tokens. `ids.tokens` already strips every character Lucene treats as syntax; this
    only drops operators that survive lower-casing and escapes defensively."""
    boosted = boosted or set()
    parts: list[str] = []
    for term in terms:
        clean = _escape(term.lower())
        if not clean or clean in ("and", "or", "not"):
            continue
        parts.append(f"{clean}^{boost}" if term in boosted else clean)
    return " OR ".join(dict.fromkeys(parts))


_LUCENE_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\\/&|])')


def _escape(term: str) -> str:
    return _LUCENE_SPECIAL.sub(r"\\\1", term).strip()


def route(question: str, *, at: str | int | None = None) -> RouterDecision:
    """Intent + terms + Lucene query for a question. `at` (ISO date) forces `belief_at`."""
    question = (question or "").strip()
    intent = detect_intent(question, at=at)
    mentions, numbers = extract_mentions(question)
    terms = content_terms(question, mentions)
    boosted = {t for m in mentions for t in tokens(m).split()}
    at_ms: int | None = None
    if at not in (None, ""):
        at_ms = parse_at(at)
    elif intent == "belief_at":
        at_ms = _date_in_question(question)
        if at_ms is None:
            intent = "why"
    if intent == "belief_at" and at_ms is not None:
        # the date words are not search terms
        terms = [t for t in terms if not re.fullmatch(r"(19|20)\d{2}|\d{1,2}", t) and t not in _MONTH_TOKENS]
    source = "kt" if _SPOKEN_SOURCE.search(question) else None
    if source:  # "according to the handover call" names where to look, not what to look for
        terms = [t for t in terms if t not in _SPOKEN_WORDS]
    decision = RouterDecision(
        intent=intent, terms=terms, mentions=mentions, numbers=numbers, at_ms=at_ms,
        lucene=lucene_query(terms, boosted), question=question, value_tokens=value_tokens(question), source=source,
    )
    log.debug("route %r -> %s", question, decision.to_dict())
    return decision


# Words that name a kind of thing rather than a thing: on their own they must not anchor an answer
# ("why does the app use Redis?" is about Redis, not about every `app.*` key).
GENERIC_TERMS = frozenset(
    """app apps application applications service services server servers system systems setting settings value values
    use uses used using set sets default defaults option options configuration configure configured feature features
    function functions logic module modules package packages library libraries version versions latest new old change
    changed changes work works working run runs running support supported supports handle handled handles call calls
    data type types name names time times number numbers stuff part parts kaam cheez chiz
    own owns owned owner owners ownership maintain maintains maintained maintainer maintainers responsible ask talk
    contact ping directory directories folder folders dir dirs path paths""".split()
)


def scrub_repo_terms(decision: RouterDecision, repo: str) -> RouterDecision:
    """Drop the repository's own name from the search terms: "why does listmonk use MongoDB?" is about MongoDB."""
    repo_tokens = set(tokens(repo).split())
    if not repo_tokens:
        return decision
    terms = [t for t in decision.terms if t not in repo_tokens]
    mentions = [m for m in decision.mentions if set(tokens(m).split()) - repo_tokens]
    if terms == decision.terms and mentions == decision.mentions:
        return decision
    boosted = {t for m in mentions for t in tokens(m).split()}
    return replace(decision, terms=terms, mentions=mentions, lucene=lucene_query(terms, boosted))


def specific_terms(decision: RouterDecision) -> list[str]:
    """The tokens an anchor must share with the question: identifier mentions plus the non-generic content words."""
    mention_tokens = [t for m in decision.mentions for t in tokens(m).split() if t not in STOPWORDS and len(t) > 1]
    return list(dict.fromkeys(mention_tokens + [t for t in decision.terms if t not in GENERIC_TERMS]))


_SPOKEN_SOURCE = re.compile(
    r"\b(handover|hand-over|kt (call|session)|knowledge transfer|(the|that|last|our) (call|meeting|standup|stand-up)|"
    r"was said|did .{1,40} say|according to (the )?(call|meeting|kt|handover)|bataya|kaha tha)\b",
    re.IGNORECASE,
)
_SPOKEN_WORDS = frozenset("handover hand over kt call session knowledge transfer meeting standup stand up according said say bataya kaha".split())


_MONTH_TOKENS = frozenset(
    "jan feb mar apr may jun jul aug sep sept oct nov dec january february march april june july august september "
    "october november december".split()
)


def _date_in_question(question: str) -> int | None:
    for m in _DATE_IN_TEXT.finditer(question):
        try:
            return parse_at(m.group(1), end_of_period=True)
        except ValueError:
            continue
    return None


# ----------------------------------------------------------------------------------------------------------------
# Entity resolution

MATCH_THRESHOLD = 0.34
QUESTION_COVERAGE = 0.34  # a partial match must account for at least a third of what the question specifically names
GENERIC_NAMES = frozenset(
    "sample example examples test tests testing config configs main index util utils utility common core base lib libs src "
    "app apps api cmd internal pkg docs doc readme setup build dist data assets static public scripts tools misc".split()
)


def match_strength(row: dict[str, Any], decision: RouterDecision) -> float:
    """1.0 when a mention equals the entity's path/key/name (or its file name); otherwise the fraction of the
    entity's own name tokens that the question contains."""
    name, path, key = row.get("name") or "", row.get("path") or "", row.get("key") or ""
    candidates = {c.lower() for c in (name, path, key) if c}
    if path:
        candidates.add(path.rsplit("/", 1)[-1].lower())
    for mention in decision.mentions:
        m = mention.lower().strip("/")
        if m in candidates or (path and path.lower().endswith("/" + m)):
            return 1.0
        if row.get("label") == "Dependency" and "/" in m and name.lower().endswith("/" + m):
            return 1.0  # `lib/pq` names the dependency `github.com/lib/pq`
        if row.get("label") == "ConfigKey" and key and len(m) > 3 and key.lower().endswith("." + m):
            return 1.0  # `max_send_errors` names `app.max_send_errors`
    label = row.get("label")
    if label == "File":
        base = path.rsplit("/", 1)[-1] if path else name
        base = base.rsplit(".", 1)[0] if "." in base else base
        own = set(tokens(base).split())
    elif label == "ConfigKey":
        own = set(tokens(key or name).split())
    else:
        own = set(tokens(name or key or path).split())
    own = {t for t in own if t not in STOPWORDS}
    if not own:
        return 0.0
    question_tokens = set(decision.terms)
    overlap = len(own & question_tokens)
    if overlap == 0:
        return 0.0
    shared = own & question_tokens
    if not shared & set(specific_terms(decision)):
        return 0.2  # only generic words ("app", "use") are shared: related, never an anchor for an answer
    strength = overlap / len(own)
    for mention in decision.mentions:
        mention_tokens = {t for t in tokens(mention).split() if t not in STOPWORDS}
        if mention_tokens and shared <= mention_tokens and len(shared) < len(mention_tokens):
            # the overlap is part of one named identifier: `db` from "MongoDB" does not make `resetDB` the subject
            strength *= len(shared) / len(mention_tokens)
            break
    # what the question asks about beyond the identifiers it names (those are judged by the mention rules above)
    mention_tokens_all = {t for m in decision.mentions for t in tokens(m).split()}
    # numbers are the values a question asks about ("why is it 1000?"), never the subject an entity must cover
    specific = {t for t in specific_terms(decision) if t not in mention_tokens_all and not t.isdigit()}
    if specific and len(shared & specific) / len(specific) < QUESTION_COVERAGE:
        # one word in common with a question about something else ("GraphQL API rate limit" -> `withListAPI`) is a
        # neighbour worth listing as related, not the thing the question asks about
        strength = min(strength, 0.3)
    if len(own) == 1:
        only = next(iter(own))
        mention_tokens = {m.lower() for m in decision.mentions}
        if only in GENERIC_NAMES and only not in mention_tokens:
            strength = 0.3  # `sample`, `config`, `main`: below the match threshold unless typed verbatim
        elif len(only) <= 2 or only not in mention_tokens:
            strength *= 0.6  # a one-token name shared with a longer mention (`sample` in `config.toml.sample`)
    return round(strength, 3)


def resolve_entities(
    recorder: Recorder, repo: str, decision: RouterDecision, *, limit: int = 5, threshold: float = MATCH_THRESHOLD, candidates: int = 25
) -> list[ResolvedEntity]:
    """Run `30_resolve_entities` and rank by match strength (ties by Lucene score). Returns matched entities first
    (at most `limit`), followed by a few unmatched "closest related" ones for refusals."""
    exact = list(dict.fromkeys(decision.mentions + [m.rsplit("/", 1)[-1] for m in decision.mentions if "/" in m]))
    rows = recorder.run("resolve_entities", {"repo": repo, "q": decision.lucene or "__none__", "exact": exact, "limit": candidates})
    if not rows:
        return []
    top_lucene = max(float(r.get("score") or 0.0) for r in rows) or 1.0
    resolved: list[ResolvedEntity] = []
    for row in rows:
        strength = match_strength(row, decision)
        lucene = float(row.get("score") or 0.0)
        resolved.append(
            ResolvedEntity(
                id=row["id"], label=row.get("label") or "Node", name=row.get("name"), path=row.get("path"), key=row.get("key"),
                strength=strength, lucene_score=lucene, matched=strength >= threshold,
                extra={k: row.get(k) for k in ("kind", "current_value", "current_version", "alive", "touch_count", "last_touched_at")},
            )
        )
    resolved.sort(key=lambda e: (e.strength + 0.1 * e.lucene_score / top_lucene, e.lucene_score), reverse=True)
    matched = [e for e in resolved if e.matched][:limit]
    related = [e for e in resolved if not e.matched][:3]
    return matched + related


def resolve_people(recorder: Recorder, repo: str, q: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """People in the repo whose name or login matches `q` (plain text; sanitised here)."""
    lucene = lucene_query([t for t in tokens(q).split() if t not in STOPWORDS])
    if not lucene:
        return []
    return recorder.run("resolve_people", {"repo": repo, "q": lucene, "limit": limit})


__all__ = [
    "INTENTS", "MATCH_THRESHOLD", "STOPWORDS", "ResolvedEntity", "RouterDecision", "content_terms", "detect_intent",
    "extract_mentions", "lucene_query", "match_strength", "resolve_entities", "resolve_people", "route", "value_tokens",
    "GENERIC_TERMS", "scrub_repo_terms", "specific_terms",
]
