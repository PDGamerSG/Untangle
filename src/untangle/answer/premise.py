"""Premise check for comparative questions ("why do we use Jest instead of Mocha?").

A question can carry a claim about the repository. When it names two tools in an "X instead of Y" form, this module
checks both against the declared dependencies before the answer is read, so a reversed or outdated premise is said
plainly instead of being explained. It never decides that the answer is wrong; it reports what the manifests say."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from untangle.answer.text import fmt_date

Status = Literal["consistent", "contradicted", "outdated", "unsupported", "both"]

_WORD = r"(@?[\w][\w@./+-]{0,80})"
_PATTERNS = [
    re.compile(
        r"\b(?:use[sd]?|using|chose|chosen|choose|picked|pick|prefer(?:s|red)?|depend(?:s|ed)? on|rel(?:y|ies|ied) on|go(?:ne)? with|went with|stick(?:s)? with|have|has)\s+"
        + _WORD + r"\s+(?:instead of|over|rather than|and not|not|vs\.?|versus)\s+" + _WORD,
        re.IGNORECASE,
    ),
    re.compile(_WORD + r"\s+(?:is\s+|are\s+|was\s+|were\s+|being\s+|gets?\s+)?(?:used|chosen|preferred|picked|selected)\s+"
               r"(?:instead of|over|rather than)\s+" + _WORD, re.IGNORECASE),
    re.compile(r"\bwhy\s+" + _WORD + r"\s+(?:instead of|over|rather than|and not|vs\.?|versus)\s+" + _WORD, re.IGNORECASE),
]
_NUMBER = re.compile(r"^v?[\d.,_]+[a-z]{0,2}$", re.IGNORECASE)  # values ("10 instead of 5", "30s over 60s") are not tools
_NOT_TOOLS = frozenset("""a an the this that it we you they our their them here there some any one two more less it's
    code repo repository project version value config file files default is are was were why what how""".split())


class PremiseHit(BaseModel):
    name: str
    version: str | None = None
    path: str | None = None
    removed_iso: str | None = None


class Premise(BaseModel):
    status: Status
    text: str
    assumed: str
    alternative: str
    found: list[PremiseHit] = Field(default_factory=list)


def comparison(question: str) -> tuple[str, str] | None:
    """`(assumed, alternative)` from an "X instead of Y" question, or None."""
    for pattern in _PATTERNS:
        match = pattern.search(question)
        if not match:
            continue
        a, b = (m.strip(".,;:?!\"'`()") for m in match.groups())
        if a.lower() in _NOT_TOOLS or b.lower() in _NOT_TOOLS or a.lower() == b.lower() or _NUMBER.match(a) or _NUMBER.match(b):
            continue
        return a, b
    return None


def _hit(rows: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    n = name.lower()
    return [r for r in rows if (r.get("name") or "").lower() == n or (r.get("name") or "").lower().endswith("/" + n)]


def _where(row: dict[str, Any]) -> str:
    bits = [f"`{row['name']}`"]
    if row.get("version"):
        bits.append(f"at `{row['version']}`")
    if row.get("path"):
        bits.append(f"in `{row['path']}`")
    return " ".join(bits)


def check(recorder: Any, repo: str, question: str) -> Premise | None:
    pair = comparison(question)
    if pair is None:
        return None
    assumed, alternative = pair
    rows = recorder.run("premise_dependencies", {"repo": repo, "names": [assumed.lower(), alternative.lower()]})
    a_rows, b_rows = _hit(rows, assumed), _hit(rows, alternative)
    a_live = [r for r in a_rows if r.get("version") and not r.get("removed_at")]
    b_live = [r for r in b_rows if r.get("version") and not r.get("removed_at")]
    a_gone = [r for r in a_rows if r not in a_live]
    found = [PremiseHit(name=r["name"], version=r.get("version"), path=r.get("path"), removed_iso=None if not r.get("removed_at") else fmt_date(r["removed_at"]))
             for r in [*a_rows, *b_rows]]
    if a_live and b_live:
        status: Status = "both"
        text = f"Both are declared: {_where(a_live[0])} and {_where(b_live[0])}."
    elif a_live:
        status = "consistent"
        text = f"The repository declares {_where(a_live[0])}, and `{alternative}` is not a declared dependency."
    elif b_live and a_gone:
        status = "outdated"
        when = fmt_date(a_gone[0].get("removed_at"))
        text = (f"`{assumed}` was removed{' on ' + when if when else ''}, and the repository now "
                f"declares {_where(b_live[0])}.")
    elif b_live:
        status = "contradicted"
        text = f"The repository declares {_where(b_live[0])}, not `{assumed}`."
    elif a_gone:
        status = "outdated"
        when = fmt_date(a_gone[0].get("removed_at"))
        text = f"`{assumed}` was a dependency until{' ' + when if when else ' it was removed'}; neither it nor `{alternative}` is declared now."
    else:
        status = "unsupported"
        text = f"Neither `{assumed}` nor `{alternative}` is a declared dependency, so the history cannot confirm this choice."
    return Premise(status=status, text=text, assumed=assumed, alternative=alternative, found=found)


__all__ = ["Premise", "PremiseHit", "check", "comparison"]
