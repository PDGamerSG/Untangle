"""`run_eval`: every gold question through `untangle.answer.service.ask` in each mode (`graph`, `baseline`), scored
against the expectations, summarised per mode and written as Markdown (+ JSON next to it).

The answer service is imported lazily and duck-typed: any object or dict with the `AskResponse` attributes of
CONTRACTS §6 (`answer`, `refused`, `citations`, `evidence_chain`, `entities`, `supersession`, `confidence`,
`baseline`) works, so the harness runs against a fake `ask` in tests and against the real one in `untangle eval`.

Metrics (per mode, verified and unverified questions reported separately):

* evidence-chain accuracy: questions with `cites_any` / `answer_contains_any` where the answer contains an expected
  string AND cites an expected id (whichever of the two is specified);
* supersession correctness: `superseded: true` questions where `supersession` is non-empty and the answer names
  the active value (`answer_contains_any`);
* refusal precision / recall: `refused` vs `expect.refuse`;
* person-to-ask hit rate: `person_any` questions where an expected person appears among the evidence-chain people
  or in the answer;
* entity hit rate: `entities_any` questions where an expected entity is among the resolved entities;
* latency p50 / p95 in milliseconds over all questions of the mode."""

from __future__ import annotations

import inspect
import logging
import math
import re
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from untangle.eval.gold import GoldQuestion, GoldSet, load_gold

log = logging.getLogger("untangle.eval")

DEFAULT_MODES: tuple[str, ...] = ("graph", "baseline")
_BRACKET_ID = re.compile(r"\[([a-z]+:[^\]\s]+)\]")
AskFn = Callable[..., Any]


@dataclass
class QuestionRun:
    id: str
    intent: str
    mode: str
    question: str
    unverified: bool
    refused: bool | None
    answer: str
    latency_ms: float
    error: str | None
    checks: dict[str, bool | None] = field(default_factory=dict)
    citations: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    confidence: float | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------- calling the service ----------


def default_ask() -> AskFn:
    from untangle.answer.service import ask  # lazy: written by another module; only needed for the real run

    return ask


def call_ask(ask: AskFn, question: str, repo: str, mode: str, at: str | None) -> Any:
    """Pass `mode` / `at` only when the function accepts them (or takes **kwargs)."""
    kwargs: dict[str, Any] = {}
    try:
        params = inspect.signature(ask).parameters
        var_kw = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
    except (TypeError, ValueError):
        params, var_kw = {}, True
    if var_kw or "mode" in params:
        kwargs["mode"] = mode
    if at is not None and (var_kw or "at" in params):
        kwargs["at"] = at
    return ask(question, repo, **kwargs)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    value = getattr(obj, name, default)
    return default if value is None else value


def _items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, dict):
        return list(value.values()) if not all(isinstance(k, str) and ":" in k for k in value) else [{"id": k, **(v if isinstance(v, dict) else {})} for k, v in value.items()]
    if isinstance(value, list | tuple):
        return list(value)
    return [value]


def normalise_response(resp: Any, mode: str) -> dict[str, Any]:
    """Flatten an `AskResponse`-like object into what the checks need."""
    answer = _get(resp, "answer")
    refused = _get(resp, "refused")
    baseline = _get(resp, "baseline")
    if mode == "baseline" and baseline is not None and (_get(baseline, "answer") or not answer):
        answer = _get(baseline, "answer") or answer
    answer = str(answer or "")
    citation_ids: list[str] = []
    citations = _get(resp, "citations")
    if isinstance(citations, dict):
        citation_ids.extend(str(k) for k in citations)
    else:
        citation_ids.extend(str(_get(c, "id") or "") for c in _items(citations))
    people: list[str] = []
    entities: list[str] = []
    for step in _items(_get(resp, "evidence_chain")):
        sid = str(_get(step, "id") or "")
        if sid:
            citation_ids.append(sid)
        if str(_get(step, "role") or "") == "person":
            people.extend(str(x) for x in (_get(step, "name"), sid) if x)
    citation_ids.extend(_BRACKET_ID.findall(answer))
    for e in _items(_get(resp, "entities")):
        entities.extend(str(_get(e, k)) for k in ("id", "name", "path", "key") if _get(e, k))
    for p in _items(_get(resp, "people")) + _items(_get(resp, "person_to_ask")):
        people.extend(str(_get(p, k)) for k in ("id", "name", "login") if _get(p, k))
        if isinstance(p, str):
            people.append(p)
    supersession = _items(_get(resp, "supersession"))
    conf = _get(resp, "confidence")
    score = _get(conf, "score") if conf is not None and not isinstance(conf, int | float) else conf
    try:
        score = None if score is None else float(score)
    except (TypeError, ValueError):
        score = None
    return {
        "answer": answer,
        "refused": None if refused is None else bool(refused),
        "citations": list(dict.fromkeys(c for c in citation_ids if c)),
        "people": list(dict.fromkeys(p for p in people if p)),
        "entities": list(dict.fromkeys(e for e in entities if e)),
        "supersession": supersession,
        "confidence": score,
    }


# ---------- scoring ----------


def _any_in(needles: Iterable[str], haystacks: Iterable[str]) -> bool:
    hs = [h.lower() for h in haystacks if h]
    return any(n.lower() in h for n in needles for h in hs)


def evaluate(q: GoldQuestion, norm: dict[str, Any]) -> dict[str, bool | None]:
    """None = not applicable to this question."""
    ex = q.expect
    answer, cites = norm["answer"], norm["citations"]
    contains = _any_in(ex.answer_contains_any, [answer]) if ex.answer_contains_any else None
    cited = _any_in(ex.cites_any, cites) if ex.cites_any else None
    evidence = None
    if ex.checks_evidence:
        evidence = (contains is not False) and (cited is not False)
    supersession = None
    if ex.superseded:
        supersession = bool(norm["supersession"]) and (contains is not False)
    person = _any_in(ex.person_any, norm["people"] + [answer]) if ex.person_any else None
    entity = _any_in(ex.entities_any, norm["entities"] + [answer]) if ex.entities_any else None
    refused = norm["refused"]
    return {
        "contains": contains,
        "cites": cited,
        "evidence": evidence,
        "supersession": supersession,
        "person": person,
        "entity": entity,
        "refuse_expected": ex.refuse,
        "refuse_predicted": None if refused is None else bool(refused),
        "refusal_correct": None if refused is None else (bool(refused) == ex.refuse),
    }


def percentile(values: Sequence[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = max(1, math.ceil(p / 100.0 * len(ordered)))
    return float(ordered[k - 1])


def _rate(hits: int, total: int) -> float | None:
    return None if total == 0 else hits / total


def summarise(runs: Sequence[QuestionRun]) -> dict[str, Any]:
    """Metrics over one list of runs (one mode, one verification bucket)."""
    def tally(name: str) -> tuple[int, int]:
        applicable = [r for r in runs if r.checks.get(name) is not None]
        return sum(1 for r in applicable if r.checks[name]), len(applicable)

    ev_hit, ev_n = tally("evidence")
    sup_hit, sup_n = tally("supersession")
    per_hit, per_n = tally("person")
    ent_hit, ent_n = tally("entity")
    tp = sum(1 for r in runs if r.checks.get("refuse_expected") and r.checks.get("refuse_predicted"))
    fp = sum(1 for r in runs if not r.checks.get("refuse_expected") and r.checks.get("refuse_predicted"))
    fn = sum(1 for r in runs if r.checks.get("refuse_expected") and r.checks.get("refuse_predicted") is False)
    tn = sum(1 for r in runs if not r.checks.get("refuse_expected") and r.checks.get("refuse_predicted") is False)
    lat = [r.latency_ms for r in runs if r.error is None]
    precision, recall = _rate(tp, tp + fp), _rate(tp, tp + fn)
    f1 = None if precision is None or recall is None or (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
    return {
        "n": len(runs),
        "errors": sum(1 for r in runs if r.error),
        "evidence_accuracy": {"hits": ev_hit, "n": ev_n, "rate": _rate(ev_hit, ev_n)},
        "supersession_correctness": {"hits": sup_hit, "n": sup_n, "rate": _rate(sup_hit, sup_n)},
        "refusal": {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1},
        "person_hit_rate": {"hits": per_hit, "n": per_n, "rate": _rate(per_hit, per_n)},
        "entity_hit_rate": {"hits": ent_hit, "n": ent_n, "rate": _rate(ent_hit, ent_n)},
        "latency_ms": {"p50": percentile(lat, 50), "p95": percentile(lat, 95), "mean": (sum(lat) / len(lat)) if lat else None},
    }


# ---------- the run ----------


def run_question(ask: AskFn, q: GoldQuestion, repo: str, mode: str) -> QuestionRun:
    t0 = time.perf_counter()
    try:
        resp = call_ask(ask, q.question, repo, mode, q.at)
        error = None
    except Exception as exc:  # noqa: BLE001 - one failing question must not stop the run
        resp, error = None, f"{type(exc).__name__}: {str(exc)[:200]}"
        log.warning("ask failed for %s (%s): %s", q.id, mode, error)
    latency = (time.perf_counter() - t0) * 1000.0
    norm = normalise_response(resp, mode) if error is None else {"answer": "", "refused": None, "citations": [], "people": [], "entities": [], "supersession": [], "confidence": None}
    checks = evaluate(q, norm)
    if error is not None:
        checks = {k: (None if k not in ("refuse_expected",) else v) for k, v in checks.items()}
    return QuestionRun(
        id=q.id, intent=q.intent, mode=mode, question=q.question, unverified=q.unverified, refused=norm["refused"],
        answer=norm["answer"], latency_ms=round(latency, 1), error=error, checks=checks, citations=norm["citations"][:12],
        people=norm["people"][:8], entities=norm["entities"][:8], confidence=norm["confidence"], note=q.note,
    )


def run_eval(
    gold_path: str | Path,
    *,
    ask: AskFn | None = None,
    modes: Sequence[str] = DEFAULT_MODES,
    out: str | Path | None = None,
    repo: str | None = None,
    gold: GoldSet | None = None,
) -> dict[str, Any]:
    """Run the gold set; returns the report dict (also written to `out` as Markdown and `<out>.json`)."""
    from untangle.eval.report import write_report

    gold = gold or load_gold(gold_path)
    repo = repo or gold.repo
    ask = ask or default_ask()
    runs: list[QuestionRun] = []
    for mode in modes:
        for q in gold.questions:
            runs.append(run_question(ask, q, repo, mode))
    summary = {
        mode: {
            "verified": summarise([r for r in runs if r.mode == mode and not r.unverified]),
            "unverified": summarise([r for r in runs if r.mode == mode and r.unverified]),
            "all": summarise([r for r in runs if r.mode == mode]),
        }
        for mode in modes
    }
    report = {
        "name": gold.name or Path(gold_path).stem,
        "repo": repo,
        "gold_path": str(gold_path),
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "modes": list(modes),
        "questions": len(gold.questions),
        "verified": len(gold.verified),
        "unverified": len(gold.unverified),
        "summary": summary,
        "runs": [r.as_dict() for r in runs],
    }
    if out is None:
        out = Path("eval") / "out" / f"{report['name']}.md"
    report["out"] = str(write_report(report, out))
    return report


__all__ = ["DEFAULT_MODES", "QuestionRun", "call_ask", "evaluate", "normalise_response", "percentile", "run_eval", "run_question", "summarise"]
