"""Decision extraction from handover-call utterances.

Two extractors behind one shape (`KtDecision`):

* **LLM** (`extract_with_llm`): sarvam-105b, Claude or any OpenAI-compatible model through `kyun.llm.LLM`, asked for
  strict JSON that pydantic validates. Utterances are sent in windows with their `seq` numbers and the repository's
  keyterms so the model can anchor every decision on utterances that exist and on identifiers the graph knows.
  Signal `llm_kt`, confidence clamped to 0.5–0.8 (CONTRACTS §3).
* **Heuristic** (`extract_heuristic`): the transparent path used with `FakeLLM` or when the model fails. A sentence
  becomes a decision when it carries a decision cue in English or Hinglish (decide / final / we will / let's /
  use karo / karenge / rakhenge / switch / move to / because / kyunki / isliye / kar diya / set kiya / rakha hai ...)
  and names an identifier the repo knows (or anything identifier-shaped: `app.concurrency`, `queries.sql`,
  `internal/manager`). Values after a dotted/snake key become `config_value`; owner / deprecated / workaround /
  constraint / choice cues pick the predicate; the clause after "because/kyunki" (or before "isliye") is the
  rationale. Signal `heuristic_kt`, confidence 0.5.

Both return decisions that point at utterance `seq`s, so every KT decision is EVIDENCED_BY the words that were
actually said; the pipeline never records a decision it cannot anchor."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from kyun.kt.transcript import Utterance, clean_text, split_sentences
from kyun.llm import LLM, LLMUnavailable

log = logging.getLogger("kyun.kt.extract")

PREDICATES = ("chose", "constraint", "workaround_for", "deprecated", "owner", "config_value", "kt_said")
Predicate = Literal["chose", "constraint", "workaround_for", "deprecated", "owner", "config_value", "kt_said"]
HEURISTIC_CONFIDENCE = 0.5
LLM_WINDOW = 60


class KtDecision(BaseModel):
    """One decision as extracted (before it is resolved against the graph and recorded)."""

    model_config = ConfigDict(extra="ignore")

    subject: str
    predicate: Predicate
    object: str
    rationale: str | None = None
    speaker_label: str | None = None
    utterance_seqs: list[int] = Field(default_factory=list)
    about_terms: list[str] = Field(default_factory=list)
    confidence: float = 0.6

    @field_validator("subject", "object", mode="before")
    @classmethod
    def _text(cls, v: Any) -> str:
        return clean_text(v)

    @field_validator("rationale", "speaker_label", mode="before")
    @classmethod
    def _opt_text(cls, v: Any) -> str | None:
        return clean_text(v) or None

    @field_validator("about_terms", mode="before")
    @classmethod
    def _terms(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = [v]
        return [clean_text(t) for t in (v or []) if clean_text(t)]

    @field_validator("utterance_seqs", mode="before")
    @classmethod
    def _seqs(cls, v: Any) -> list[int]:
        out: list[int] = []
        for x in v if isinstance(v, list) else ([v] if v is not None else []):
            try:
                n = int(x)
            except (TypeError, ValueError):
                continue
            if n >= 0 and n not in out:
                out.append(n)
        return out

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v: Any) -> float:
        try:
            return min(1.0, max(0.0, float(v)))
        except (TypeError, ValueError):
            return 0.6


class KtDecisions(BaseModel):
    model_config = ConfigDict(extra="ignore")
    decisions: list[KtDecision] = Field(default_factory=list)


@dataclass
class Extraction:
    decisions: list[KtDecision]
    signal: str  # 'llm_kt' | 'heuristic_kt'
    llm_used: bool
    backend: str = "fake"
    model: str = "fake"
    errors: list[str] = field(default_factory=list)


# ---------- cues ----------

_LATIN_CUES = [
    r"decid(?:e|ed|es|ing)", r"decision", r"final(?:i[sz]ed?|ly)?", r"we will", r"we'll", r"let'?s", r"lets",
    r"use kar(?:o|te|na|enge|te hain)?", r"karenge", r"rakhenge", r"rakh(?:a|i|e) (?:hai|hain|tha|thi|the)", r"rakha",
    r"switch(?:ed)?", r"mov(?:e|ed|ing) to", r"because", r"kyunki", r"kyuki", r"kyonki", r"isliye", r"isiliye",
    r"kar diya", r"kar di", r"set kiya", r"set to", r"set kar", r"chose", r"choose", r"went with", r"stick with",
    r"instead of", r"ki jagah", r"prefer(?:red)?", r"owner", r"owns", r"ownership", r"maintain(?:er|s|ed)?",
    r"dekh(?:ta|ti|egi|ega|enge|te) (?:hai|hain|hoon|hu|hun)?", r"sambhal(?:ta|ti|ega|egi|enge)", r"handle(?:s|d)?",
    r"responsible", r"deprecated?", r"hata diya", r"hata di", r"remove kar", r"nikaal", r"no longer", r"ab use nahi",
    r"revert(?:ed)?", r"workaround", r"temporar(?:y|ily)", r"hack", r"jugaad", r"abhi ke liye", r"for now", r"must",
    r"never", r"always", r"cannot", r"can't", r"mat karna", r"kabhi nahi", r"hamesha", r"zaroori", r"zaruri",
    r"limit", r"throttl\w*", r"quota", r"agreed", r"we keep", r"we use", r"hum use", r"humne", r"maine",
]
_DEVANAGARI_CUES = [
    "क्योंकि", "इसलिए", "फाइनल", "रखा", "रखेंगे", "रखते", "रहने दो", "करेंगे", "हमेशा", "कभी नहीं", "ज़रूरी", "जरूरी", "तय किया",
    "फ़ैसला", "फैसला", "बदल दिया", "हटा दिया", "ओनर", "हमने", "मत करना", "मत चलाना", "मत बढ़ाना", "मत बदलना", "मत घटाना",
    "use करते", "use करो", "use होता", "use होती", "use नहीं", "देखेगी", "देखेगा", "देखेंगे", "देखता", "देखती", "संभालेगी",
    "संभालेगा", "संभालता", "संभालती", "अभी के लिए",
]
_CUE = re.compile(r"\b(?:" + "|".join(_LATIN_CUES) + r")\b", re.IGNORECASE)
# a bare reason connector ("... because the deploy was slow") is not a decision by itself
_REASON_ONLY = re.compile(r"\b(?:because|kyunki|kyuki|kyonki|isliye|isiliye|since|taaki|so that)\b|क्योंकि|इसलिए|ताकि", re.IGNORECASE)

_OWNER = re.compile(r"\b(?:owner|owns|ownership|maintain(?:er|s|ed)?|dekh(?:ta|ti|egi|ega|enge|te)|sambhal\w*|responsible|handles?|lead)\b|ओनर|संभाल|देख(?:ता|ती|ेगी|ेगा|ेंगे)", re.IGNORECASE)
_DEPRECATED = re.compile(r"\b(?:deprecated?|hata diya|hata di|remove kar\w*|removed|nikaal\w*|no longer|ab use nahi|retired|band kar diya|dead code)\b|हटा दिया|बंद कर दिया|use नहीं (?:होता|होती|करते|कर रहे)", re.IGNORECASE)
_WORKAROUND = re.compile(r"\b(?:workaround|temporar(?:y|ily)|hack|jugaad|abhi ke liye|for now|band-?aid|stopgap|patch)\b|अभी के लिए", re.IGNORECASE)
_CONSTRAINT = re.compile(r"\b(?:must|never|always|cannot|can'?t|don'?t|mat karna|kabhi nahi|hamesha|zaroori|zaruri|limit|throttl\w*|quota|max(?:imum)?|at most|se zyada nahi|constraint)\b|हमेशा|कभी नहीं|ज़रूरी|जरूरी|मत (?:करना|चलाना|बढ़ाना|बदलना|घटाना|हटाना|देना)", re.IGNORECASE)
_CHOSE = re.compile(r"\b(?:decid\w*|decision|final\w*|we will|we'll|let'?s|use kar\w*|karenge|rakhenge|rakh(?:a|i|e)|switch\w*|mov(?:e|ed|ing) to|kar diya|set kiya|set to|set kar\w*|chose|choose|went with|stick with|instead of|ki jagah|prefer\w*|agreed|we keep|we use|hum use|humne|maine)\b|फाइनल|रखा|रखेंगे|रखते|रहने दो|करेंगे|तय किया|फ़ैसला|फैसला|बदल दिया|use करते|use करो", re.IGNORECASE)

_REASON_AFTER = re.compile(r"\b(?:because|kyunki|kyuki|kyonki|since|taaki|so that)\b\s*(?P<r>.+?)(?=[.?!।]|$)|(?:क्योंकि|ताकि)\s*(?P<r2>.+?)(?=[.?!।]|$)", re.IGNORECASE)
_REASON_BEFORE = re.compile(r"^(?P<r>.+?)[,\s]+(?:isliye|isiliye|that'?s why|therefore|so we|इसलिए)(?=[\s,.?!।]|$)", re.IGNORECASE)
_PAST = re.compile(r"\b(?:pehle|earlier|before|previously|used to|originally|was)\b|पहले", re.IGNORECASE)
_NOW = re.compile(r"\b(?:ab|now|phir|then|currently|finally|aaj)\b|अब|फिर", re.IGNORECASE)
_VALUE = re.compile(r"""(?<![\w.])(?P<v>-?\d+(?:\.\d+)?(?:\s*(?:ms|s|sec|seconds?|min|minutes?|mb|kb|gb|%))?|"[^"]{1,80}"|'[^']{1,80}'|true|false|null|nil|none)(?![\w.])""", re.IGNORECASE)
_COMPARATIVE = re.compile(r"^\s*(?:से (?:ऊपर|ज़्यादा|ज्यादा|कम|नीचे)|se (?:upar|zyada|jyada|kam|neeche)|or more|or less|and above|and below|\+)", re.IGNORECASE)
_IDENT = re.compile(r"(?<![\w/.-])(?:[A-Za-z_][\w-]*(?:[./][\w-]+)+|[a-z][a-z0-9]*(?:_[a-z0-9]+)+)(?![\w/.-])")
_SELF = re.compile(r"\b(?:i|me|my|main|mein|mai|hum|humne|maine|mera|meri)\b|मैं|मेरा|मेरी|(?<![ऀ-ॿ])हम(?:ने)?(?![ऀ-ॿ])", re.IGNORECASE)
_FIRST = re.compile(r"\b(?:first|pehla|pehli|sabse pehle)\b", re.IGNORECASE)


def has_cue(sentence: str) -> bool:
    return bool(_CUE.search(sentence)) or any(c in sentence for c in _DEVANAGARI_CUES)


def _term_pattern(term: str) -> re.Pattern[str]:
    if " " in term:
        return re.compile(r"(?<!\w)" + r"\W+".join(re.escape(p) for p in term.split()) + r"(?!\w)", re.IGNORECASE)
    return re.compile(r"(?<![\w./-])" + re.escape(term) + r"(?![\w./-])", re.IGNORECASE)


class TermIndex:
    """Known identifiers (catalogue aliases + keyterms) compiled once; `find` returns (term, start, end) matches."""

    def __init__(self, terms: Iterable[str]):
        seen: dict[str, str] = {}
        for t in terms:
            t = clean_text(t)
            if len(t) >= 3 and t.lower() not in seen:
                seen[t.lower()] = t
        self.terms = list(seen.values())
        self._patterns = [(t, _term_pattern(t)) for t in self.terms]

    def find(self, text: str) -> list[tuple[str, int, int]]:
        low = text.lower()
        found: list[tuple[str, int, int]] = []
        for term, pat in self._patterns:
            if term.lower().split(" ")[0] not in low:
                continue
            m = pat.search(text)
            if m:
                found.append((term, m.start(), m.end()))
        found.sort(key=lambda x: (x[1], -(x[2] - x[1])))
        # drop matches nested inside a longer one (basename inside the full path)
        out: list[tuple[str, int, int]] = []
        for item in found:
            if out and item[1] < out[-1][2]:
                continue
            out.append(item)
        return out


def _subjects(sentence: str, index: TermIndex) -> list[tuple[str, int, int]]:
    """Known terms first (by position), then identifier-shaped tokens not already covered."""
    known = index.find(sentence)
    covered = [(s, e) for _, s, e in known]
    extra: list[tuple[str, int, int]] = []
    for m in _IDENT.finditer(sentence):
        if any(s <= m.start() < e for s, e in covered):
            continue
        if re.fullmatch(r"\d[\d.]*", m.group(0)):
            continue
        extra.append((m.group(0), m.start(), m.end()))
    return sorted(known + extra, key=lambda x: x[1]) if known or extra else []


def _value_after(sentence: str, end: int) -> str | None:
    tail = sentence[end : end + 90]
    values = [(m.start(), m.group("v")) for m in _VALUE.finditer(tail)]
    if not values:
        return None
    def _clean(pos: int, raw: str) -> str | None:
        if _COMPARATIVE.match(tail[pos + len(raw) :]):  # "10 से ऊपर मत बढ़ाना" is a bound, not the value
            return None
        return raw.strip().strip("'\"")

    now = _NOW.search(tail)
    if now:
        after_now = [(pos, v) for pos, v in values if pos > now.start()]
        if after_now:
            return _clean(*after_now[0])
    first_pos, first = values[0]
    if _PAST.search(tail[:first_pos]) or _PAST.search(sentence[max(0, end - 40) : end]):
        return None
    return _clean(first_pos, first)


def _rationale(sentence: str) -> str | None:
    m = _REASON_AFTER.search(sentence)
    if m:
        reason = m.group("r") or m.group("r2")
        if reason:
            return clean_text(reason)[:240] or None
    m = _REASON_BEFORE.search(sentence)
    if m:
        return clean_text(m.group("r"))[:240] or None
    return None


def _person_in(sentence: str, names: Sequence[str], self_name: str | None) -> str | None:
    low = sentence.lower()
    for name in sorted(names, key=len, reverse=True):
        if not name:
            continue
        first = name.split()[0].lower()
        if name.lower() in low or (len(first) >= 3 and re.search(r"(?<!\w)" + re.escape(first) + r"(?!\w)", low)):
            return name
    if self_name and _SELF.search(sentence):
        return self_name
    return None


def extract_heuristic(
    utterances: Sequence[Utterance],
    *,
    terms: Iterable[str] = (),
    speakers: Mapping[str, Mapping[str, Any]] | None = None,
    confidence: float = HEURISTIC_CONFIDENCE,
) -> list[KtDecision]:
    """Rule-based decisions (see module docstring). Deterministic and fully explainable."""
    index = TermIndex(terms)
    names = [str((v or {}).get("name") or "") for v in (speakers or {}).values()]
    out: list[KtDecision] = []
    seen: set[tuple[str, str, str]] = set()
    for u in utterances:
        self_name = str(((speakers or {}).get(u.speaker_label) or {}).get("name") or "") or None
        for sentence in split_sentences(u.text):
            if not has_cue(sentence):
                continue
            subjects = _subjects(sentence, index)
            if not subjects:
                continue
            subject, _, s_end = subjects[0]
            rationale = _rationale(sentence)
            value = _value_after(sentence, s_end) if (("." in subject or "_" in subject) and "/" not in subject) else None
            predicate: str
            obj: str
            if value is not None:
                predicate, obj = "config_value", value
            elif _OWNER.search(sentence):
                person = _person_in(sentence, names, self_name)
                if not person:
                    continue
                predicate, obj = "owner", person
            elif _DEPRECATED.search(sentence):
                predicate, obj = "deprecated", subject
            elif _WORKAROUND.search(sentence):
                predicate, obj = "workaround_for", rationale or sentence
            elif _CONSTRAINT.search(sentence):
                predicate, obj = "constraint", sentence
            elif _CHOSE.search(sentence):
                others = [t for t, s, _ in subjects[1:] if t.lower() != subject.lower()]
                predicate, obj = "chose", (others[0] if others else sentence)
            elif has_cue(_REASON_ONLY.sub(" ", sentence)):
                predicate, obj = "kt_said", sentence
            else:
                continue
            obj = clean_text(obj)[:240]
            key = (subject.lower(), predicate, obj.lower())
            if key in seen:
                continue
            seen.add(key)
            out.append(
                KtDecision(
                    subject=subject,
                    predicate=predicate,  # type: ignore[arg-type]
                    object=obj,
                    rationale=rationale,
                    speaker_label=u.speaker_label,
                    utterance_seqs=[u.seq],
                    about_terms=[subject],
                    confidence=confidence,
                )
            )
    return out


# ---------- LLM ----------

SYSTEM_PROMPT = """You extract engineering decisions from the transcript of a knowledge-transfer (handover) call.
The call is in Hindi, Hinglish (Hindi-English code-mixed, Devanagari or Latin script) or English about one code repository.
Return exactly ONE JSON object: {"decisions": [ {...}, ... ]} and nothing else.
Each decision: {"subject": str, "predicate": str, "object": str, "rationale": str|null, "speaker_label": str,
                "utterance_seqs": [int], "about_terms": [str], "confidence": number}
- subject: the code entity the statement is about, written exactly as an identifier (dotted config key such as
  app.concurrency, file path such as queries.sql, dependency such as github.com/lib/pq, module path, symbol name).
- predicate: one of chose | constraint | workaround_for | deprecated | owner | config_value | kt_said.
  config_value = the current value of a config key (object = the literal value as spoken, e.g. "10");
  owner = who owns/maintains it (object = the person's name); deprecated = no longer used; workaround_for = a
  temporary fix (object = what it works around); constraint = a rule that must hold; chose = a choice between
  alternatives (object = what was chosen); kt_said = any other statement worth remembering.
- rationale: the stated reason, verbatim or a short summary in the language spoken; null when no reason was given.
- utterance_seqs: the seq numbers of the utterances that say this (they must exist in the transcript).
- about_terms: identifiers from KEYTERMS (or the transcript) that the decision is about.
- confidence: 0.0-1.0, how clearly the decision was stated.
Record only what was actually said. Never invent values, people, reasons or utterance numbers.
Values that were explicitly described as old/previous/reverted are NOT the current value; record the current one."""


def _fmt_ms(ms: int) -> str:
    s = max(0, int(ms)) // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def _user_prompt(window: Sequence[Utterance], keyterms: Sequence[str], speakers: Mapping[str, Mapping[str, Any]] | None) -> str:
    lines = ["KEYTERMS: " + ", ".join(list(keyterms)[:50])]
    if speakers:
        lines.append("SPEAKERS: " + "; ".join(f"{label} = {(v or {}).get('name') or 'unknown'}" for label, v in speakers.items()))
    lines.append("UTTERANCES:")
    for u in window:
        lines.append(f"[{u.seq}] {u.speaker_label} ({_fmt_ms(u.start_ms)}): {u.text}")
    return "\n".join(lines)


def extract_with_llm(
    llm: LLM,
    utterances: Sequence[Utterance],
    *,
    keyterms: Sequence[str] = (),
    speakers: Mapping[str, Mapping[str, Any]] | None = None,
    window: int = LLM_WINDOW,
) -> tuple[list[KtDecision], list[str]]:
    """Ask the model window by window; returns (decisions, errors). Decisions whose seqs do not exist are dropped,
    missing speaker labels are filled from the first evidencing utterance, and confidence is clamped to 0.5-0.8."""
    by_seq = {u.seq: u for u in utterances}
    out: list[KtDecision] = []
    errors: list[str] = []
    for start in range(0, len(utterances), max(1, window)):
        chunk = utterances[start : start + window]
        try:
            parsed = llm.complete_json(SYSTEM_PROMPT, _user_prompt(chunk, keyterms, speakers), KtDecisions, max_tokens=4096)
        except (LLMUnavailable, ValidationError, ValueError) as exc:
            errors.append(f"window {start}: {type(exc).__name__}: {str(exc)[:200]}")
            continue
        except Exception as exc:  # noqa: BLE001 - a provider SDK error must not kill the ingestion
            errors.append(f"window {start}: {type(exc).__name__}: {str(exc)[:200]}")
            continue
        for d in parsed.decisions:
            seqs = [s for s in d.utterance_seqs if s in by_seq]
            if not seqs or not d.subject or not d.object:
                continue
            d.utterance_seqs = seqs
            d.speaker_label = d.speaker_label or by_seq[seqs[0]].speaker_label
            d.confidence = min(0.8, max(0.5, d.confidence))
            out.append(d)
    return out, errors


def extract_decisions(
    utterances: Sequence[Utterance],
    *,
    keyterms: Sequence[str] = (),
    terms: Iterable[str] = (),
    llm: LLM | None = None,
    speakers: Mapping[str, Mapping[str, Any]] | None = None,
) -> Extraction:
    """LLM when one is available, else (or on failure) the heuristic extractor."""
    if llm is not None and llm.available:
        decisions, errors = extract_with_llm(llm, utterances, keyterms=keyterms, speakers=speakers)
        if decisions or not errors:
            return Extraction(decisions, "llm_kt", True, llm.backend, llm.model, errors)
        log.warning("LLM extraction failed (%s); falling back to heuristics", "; ".join(errors)[:300])
        heur = extract_heuristic(utterances, terms=list(terms) + list(keyterms), speakers=speakers)
        return Extraction(heur, "heuristic_kt", False, llm.backend, llm.model, errors)
    heur = extract_heuristic(utterances, terms=list(terms) + list(keyterms), speakers=speakers)
    backend = llm.backend if llm is not None else "fake"
    model = llm.model if llm is not None else "fake"
    return Extraction(heur, "heuristic_kt", False, backend, model, [])


__all__ = [
    "HEURISTIC_CONFIDENCE",
    "PREDICATES",
    "Extraction",
    "KtDecision",
    "KtDecisions",
    "SYSTEM_PROMPT",
    "TermIndex",
    "extract_decisions",
    "extract_heuristic",
    "extract_with_llm",
    "has_cue",
]
