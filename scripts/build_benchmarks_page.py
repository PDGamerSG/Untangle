"""Regenerate web/src/lib/benchmarks.ts (the Benchmarks page) from the recorded report in docs/development/EVAL.md.

Run after `untangle eval` writes a new report: `python3 scripts/build_benchmarks_page.py`."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "docs/development/EVAL.md").read_text()

recorded = re.search(r"Recorded (\S+) from `([^`]+)`: (\d+) questions \((\d+) verified, (\d+) unverified\)", text)


def table(after: str) -> list[list[str]]:
    start = text.index(after)
    rows = []
    for line in text[start:].splitlines()[1:]:
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if set(cells[0]) <= {"-"}:
            continue
        rows.append(cells)
    return rows


summary = table("## Summary (verified questions)")[1:]
metrics = [{"name": r[0], "graph": r[1], "baseline": r[2]} for r in summary]

rows = table("## Per question")[1:]
questions: dict[str, dict] = {}
for r in rows:
    qid, intent, mode, refused, evidence, supersession, person, entity = r[:8]
    unverified = "unverified" in qid
    qid = qid.replace("*(unverified)*", "").strip()
    q = questions.setdefault(qid, {"id": qid, "intent": intent, "verified": not unverified})
    q[mode] = {"outcome": refused, "evidence": evidence, "supersession": supersession, "person": person, "entity": entity}

data = {
    "recorded": recorded.group(1)[:10],
    "gold": recorded.group(2),
    "questions": int(recorded.group(3)),
    "verified": int(recorded.group(4)),
    "unverified": int(recorded.group(5)),
    "metrics": metrics,
    "rows": list(questions.values()),
}

out = f'''// Generated from docs/development/EVAL.md (the recorded evaluation snapshot). Regenerate after a new run rather
// than editing by hand, so the page never shows a number the report does not.

export interface BenchmarkCell {{ outcome: string; evidence: string; supersession: string; person: string; entity: string }}
export interface BenchmarkRow {{ id: string; intent: string; verified: boolean; graph?: BenchmarkCell; baseline?: BenchmarkCell }}

export const BENCHMARK = {json.dumps(data, indent=2, ensure_ascii=False)} as const satisfies {{
  recorded: string; gold: string; questions: number; verified: number; unverified: number;
  metrics: readonly {{ name: string; graph: string; baseline: string }}[];
  rows: readonly BenchmarkRow[];
}};
'''
(ROOT / "web/src/lib/benchmarks.ts").write_text(out)
print(len(metrics), len(questions))
