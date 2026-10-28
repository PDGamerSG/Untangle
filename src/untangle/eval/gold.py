"""Gold file format (`eval/gold/<name>.yaml`):

    repo: owner/name
    name: listmonk                      # optional; defaults to the file stem
    questions:
      - id: cfg-concurrency
        question: "Why is app.concurrency 10?"
        intent: config_value            # free text: config_value | entity_why | dependency | who_to_ask | refuse | kt | supersession
        at: 2024-01-01                  # optional "as of" date passed to ask()
        unverified: true                # the expectation was written without checking the repo; reported separately
        note: "..."                     # optional
        expect:
          entities_any: [app.concurrency]        # one of these must be among the resolved entities (id/name/path/key)
          answer_contains_any: ["10"]            # one of these substrings must be in the answer (case-insensitive)
          cites_any: ["dec:knadh/listmonk:"]     # one of these must be a substring of a cited id
          refuse: false                          # the question should be refused
          person_any: [knadh]                    # one of these names/logins must be the person to ask
          superseded: true                       # the answer must show a supersession and name the active value

Every list is optional; an empty list means "not checked" and the metric that needs it reports N/A."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str | int | float):
        return [str(v)]
    return [str(x) for x in v if x is not None and str(x).strip()]


class Expect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities_any: list[str] = Field(default_factory=list)
    answer_contains_any: list[str] = Field(default_factory=list)
    cites_any: list[str] = Field(default_factory=list)
    refuse: bool = False
    person_any: list[str] = Field(default_factory=list)
    superseded: bool = False

    @field_validator("entities_any", "answer_contains_any", "cites_any", "person_any", mode="before")
    @classmethod
    def _lists(cls, v: Any) -> list[str]:
        return _as_list(v)

    @property
    def checks_evidence(self) -> bool:
        return not self.refuse and bool(self.answer_contains_any or self.cites_any)


class GoldQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    intent: str = "entity_why"
    expect: Expect = Field(default_factory=Expect)
    at: str | None = None
    unverified: bool = False
    note: str | None = None

    @field_validator("at", mode="before")
    @classmethod
    def _at(cls, v: Any) -> str | None:
        return None if v is None else str(v)


class GoldSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo: str
    name: str | None = None
    questions: list[GoldQuestion]

    @model_validator(mode="after")
    def _unique_ids(self) -> GoldSet:
        seen: set[str] = set()
        for q in self.questions:
            if q.id in seen:
                raise ValueError(f"duplicate question id {q.id!r}")
            seen.add(q.id)
        return self

    @property
    def verified(self) -> list[GoldQuestion]:
        return [q for q in self.questions if not q.unverified]

    @property
    def unverified(self) -> list[GoldQuestion]:
        return [q for q in self.questions if q.unverified]


def load_gold(path: str | Path) -> GoldSet:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping with repo and questions")
    gold = GoldSet.model_validate(data)
    if not gold.name:
        gold.name = path.stem
    return gold


__all__ = ["Expect", "GoldQuestion", "GoldSet", "load_gold"]
