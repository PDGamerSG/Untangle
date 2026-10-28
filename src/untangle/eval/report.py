"""Markdown (+ JSON) report for an eval run: the graph-vs-baseline summary table, the unverified block, and one
row per question and mode with the checks that applied."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _pct(block: dict[str, Any] | None) -> str:
    if not block or block.get("n") in (None, 0):
        return "n/a"
    return f"{block['hits']}/{block['n']} ({block['rate'] * 100:.0f}%)"


def _ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def _ms(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f} ms"


def _mark(value: bool | None) -> str:
    return "-" if value is None else ("yes" if value else "NO")


def _summary_table(summary: dict[str, Any], modes: list[str], bucket: str) -> list[str]:
    head = "| Metric | " + " | ".join(modes) + " |"
    sep = "|---|" + "---|" * len(modes)
    rows = [head, sep]

    def row(label: str, cell) -> None:
        rows.append(f"| {label} | " + " | ".join(cell(summary[m][bucket]) for m in modes) + " |")

    row("Questions", lambda s: str(s["n"]))
    row("Evidence-chain accuracy (cites + contains)", lambda s: _pct(s["evidence_accuracy"]))
    row("Supersession correctness", lambda s: _pct(s["supersession_correctness"]))
    row("Refusal precision", lambda s: _ratio(s["refusal"]["precision"]))
    row("Refusal recall", lambda s: _ratio(s["refusal"]["recall"]))
    row("Refusal F1", lambda s: _ratio(s["refusal"]["f1"]))
    row("Person-to-ask hit rate", lambda s: _pct(s["person_hit_rate"]))
    row("Entity resolution hit rate", lambda s: _pct(s["entity_hit_rate"]))
    row("Latency p50", lambda s: _ms(s["latency_ms"]["p50"]))
    row("Latency p95", lambda s: _ms(s["latency_ms"]["p95"]))
    row("Errors", lambda s: str(s["errors"]))
    return rows


def render_markdown(report: dict[str, Any]) -> str:
    modes = list(report["modes"])
    lines = [
        f"# Untangle eval: {report['name']} ({report['repo']})",
        "",
        f"Generated {report['generated_at']} from `{report['gold_path']}`: {report['questions']} questions "
        f"({report['verified']} verified, {report['unverified']} unverified), modes {', '.join(modes)}.",
        "",
        "`graph` is Untangle's answer from the decision graph; `baseline` is vector-only retrieval over the same text "
        "(no decisions, no supersession, no refusal logic). An expectation marked *unverified* was written without "
        "checking the repository's history, so those rows are scored but reported apart.",
        "",
        "## Summary (verified questions)",
        "",
        *_summary_table(report["summary"], modes, "verified"),
        "",
    ]
    if report["unverified"]:
        lines += ["## Unverified expectations", "", *_summary_table(report["summary"], modes, "unverified"), ""]
    lines += [
        "## Per question",
        "",
        "| id | intent | mode | refused | evidence | supersession | person | entity | confidence | latency | answer |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report["runs"]:
        c = r["checks"]
        refused = "-" if r["refused"] is None else ("refused" if r["refused"] else "answered")
        if c.get("refusal_correct") is False:
            refused += " (wrong)"
        answer = (r["answer"] or "").replace("|", "\\|").replace("\n", " ")
        if len(answer) > 140:
            answer = answer[:137] + "..."
        if r["error"]:
            answer = f"ERROR {r['error']}"
        flag = " *(unverified)*" if r["unverified"] else ""
        conf = "-" if r["confidence"] is None else f"{r['confidence']:.2f}"
        lines.append(
            f"| {r['id']}{flag} | {r['intent']} | {r['mode']} | {refused} | {_mark(c.get('evidence'))} | {_mark(c.get('supersession'))} | "
            f"{_mark(c.get('person'))} | {_mark(c.get('entity'))} | {conf} | {r['latency_ms']:.0f} ms | {answer} |"
        )
    errors = [r for r in report["runs"] if r["error"]]
    if errors:
        lines += ["", "## Errors", ""]
        lines += [f"- `{r['id']}` ({r['mode']}): {r['error']}" for r in errors]
    lines.append("")
    return "\n".join(lines)


def write_report(report: dict[str, Any], out: str | Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(report), encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return out


__all__ = ["render_markdown", "write_report"]
