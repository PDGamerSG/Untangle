"""Composition: citation/grounding validation, the model-vs-template decision, and the template for every intent."""

from __future__ import annotations

import pytest

from _answer_fixture import T_NOW, Fixture
from untangle.answer.compose import (
    SYSTEM_PROMPT,
    build_user_prompt,
    compose,
    count_sentences,
    render_refusal,
    render_template,
    validate,
)
from untangle.answer.confidence import score, signals_from
from untangle.answer.retrieve import Dossier, build_dossiers, version_from_row
from untangle.answer.service import evidence_chain
from untangle.llm import FakeLLM

FX = Fixture("test/fixture")


def _confidence(ev):
    return score(signals_from(ev, at_ms=ev.decision.at_ms if ev.decision.intent == "belief_at" else None, now_ms=T_NOW))


# -- dossiers -------------------------------------------------------------------------------------------------------


def test_dossiers_group_the_chain_oldest_first():
    dossiers = FX.dossiers()
    assert len(dossiers) == 1
    d = dossiers[0]
    assert [v.object for v in d.versions] == ["5", "10"]
    assert d.top.id == FX.dec_new and d.top.active
    assert d.at(1651363200000).id == FX.dec_old  # 2022-05-01
    assert d.at(1700000000000).id == FX.dec_new


def test_dossiers_split_unrelated_decisions():
    other = FX.row_new() | {"id": "dec:test/fixture:adr:zzz", "key": "adr|x", "supersedes": [], "superseded_by": []}
    versions = {r["id"]: version_from_row(r) for r in (FX.row_old(), FX.row_new(), other)}
    assert len(build_dossiers(versions)) == 2


# -- validation -----------------------------------------------------------------------------------------------------


def test_validate_rejects_unknown_citation():
    ev = FX.evidence()
    assert validate(f"It is 10 [{FX.dec_new}] because of [pr:test/fixture#999].", ev) == "unknown citation pr:test/fixture#999"


def test_validate_requires_a_citation():
    assert validate("It is 10.", FX.evidence()) == "no citation"
    assert validate("", FX.evidence()) == "empty answer"


def test_validate_rejects_more_than_five_sentences():
    text = " ".join(f"Sentence {i} is here [{FX.dec_new}]." for i in range(6))
    assert validate(text, FX.evidence()) == "more than five sentences"
    assert count_sentences("One. Two e.g. three. Four 3.5 five [dec:x.y]. Six!") == 4


def test_validate_rejects_ungrounded_numbers():
    ev = FX.evidence()
    assert validate(f"app.concurrency is 10 [{FX.dec_new}], set after 42 incidents.", ev) == "number 42 not grounded in the cited sources"
    # a number present only in an uncited source is not grounded either
    assert validate(f"It was 5 since 2021 [{FX.dec_new}].", ev) == "number 2021 not grounded in the cited sources"


def test_validate_accepts_grounded_dates_and_numbers():
    ev = FX.evidence()
    good = f"app.concurrency is 10 [{FX.dec_new}], set in PR #812 on 14 Mar 2023 [{FX.pr}] after incident #790 [{FX.issue}]; before that it was 5 from 2 Jun 2021 [{FX.dec_old}]."
    assert validate(good, ev) is None


# -- compose: model vs template -------------------------------------------------------------------------------------


def test_compose_without_model_uses_template():
    ev = FX.evidence()
    out = compose(ev, _confidence(ev), FakeLLM())
    assert not out.used_llm and "model unavailable" in (out.note or "")
    assert f"[{FX.dec_new}]" in out.answer


def test_compose_falls_back_on_unknown_citation():
    ev = FX.evidence()
    llm = FakeLLM({"Question:": "It is 10 because of [pr:test/fixture#999]."})
    out = compose(ev, _confidence(ev), llm)
    assert not out.used_llm and "unknown citation" in (out.note or "")
    assert out.answer == render_template(ev)
    assert llm.calls and llm.calls[0][0] == SYSTEM_PROMPT


def test_compose_falls_back_on_ungrounded_number():
    ev = FX.evidence()
    llm = FakeLLM({"Question:": f"app.concurrency is 10 [{FX.dec_new}] since 1999."})
    out = compose(ev, _confidence(ev), llm)
    assert not out.used_llm and "not grounded" in (out.note or "")


def test_compose_accepts_a_good_model_answer():
    ev = FX.evidence()
    good = f"app.concurrency in config.toml is 10 [{FX.dec_new}]. Kailash Nadh set it in PR #812 'Limit concurrency after SMTP errors' on 14 Mar 2023 [{FX.pr}] after incident #790 [{FX.issue}]. Before that it was 5 [{FX.dec_old}]."
    out = compose(ev, _confidence(ev), FakeLLM({"Question:": good}))
    assert out.used_llm and out.answer == good


def test_compose_never_calls_the_model_for_refusals():
    ev = FX.evidence("why does the billing webhook retry twice?", with_dossiers=False)
    ev.entities = []
    llm = FakeLLM({"Question:": "made up [dec:x]"})
    out = compose(ev, _confidence(ev), llm)
    assert out.note == "refused" and not llm.calls
    assert out.answer.startswith("Untangle found nothing in the graph that answers that.")


def test_user_prompt_lists_versions_oldest_first_with_ids():
    prompt = build_user_prompt(FX.evidence())
    assert prompt.index(f"v1 [{FX.dec_old}]") < prompt.index(f"v2 [{FX.dec_new}]")
    assert "ACTIVE" in prompt and "rationale: \"The SMTP provider" in prompt
    assert "motivated by incident #790" in prompt
    assert "PEOPLE" in prompt and "Kailash Nadh" in prompt


# -- templates ------------------------------------------------------------------------------------------------------


def test_template_why_reads_like_the_demo():
    text = render_template(FX.evidence())
    assert text.startswith(f"`app.concurrency` in `config.toml` is 10 [{FX.dec_new}].")
    assert f"It was set in PR #812 'Limit concurrency after SMTP errors' by Kailash Nadh on 14 Mar 2023 [{FX.pr}], after incident #790 'SMTP errors under load' [{FX.issue}]." in text
    assert "The stated reason: The SMTP provider rate-limits above 10 concurrent connections" in text
    assert f"Before that it was 5, set in commit 3fa2c1d 'Set concurrency to 5' (2 Jun 2021) [{FX.dec_old}]." in text
    assert "Person to ask: Kailash Nadh, who authored 2 of 2 commits on app.concurrency, stated 2 recorded decisions about it." in text
    assert count_sentences(text) <= 5
    assert validate(text, FX.evidence()) is None


def test_template_why_without_rationale_says_so():
    ev = FX.evidence()
    ev.dossiers[0].versions[-1].rationale = None
    assert "No reason is recorded beyond the PR title." in render_template(ev)


def test_template_belief_at():
    ev = FX.evidence("what was app.concurrency on 2022-05-01?", at="2022-05-01")
    text = render_template(ev, at_ms=ev.decision.at_ms)
    assert text.startswith(f"On 1 May 2022 `app.concurrency` in `config.toml` was 5 [{FX.dec_old}].")
    assert f"It was later superseded on 14 Mar 2023 by 10, set in PR #812 'Limit concurrency after SMTP errors' by Kailash Nadh [{FX.dec_new}]." in text
    assert validate(text, ev) is None


def test_template_belief_at_before_any_decision():
    ev = FX.evidence("what was app.concurrency on 2019-01-01?", at="2019-01-01")
    text = render_template(ev, at_ms=ev.decision.at_ms)
    assert text.startswith("On 1 Jan 2019 nothing was recorded yet about `app.concurrency` in `config.toml`; the first recorded value, 5, came in commit 3fa2c1d")


def test_template_belief_at_before_any_decision_keeps_the_named_subject():
    ev = FX.evidence("what was app.concurrency on 2019-01-01?", at="2019-01-01")
    unrelated = version_from_row(FX.row_new() | {
        "id": "dec:test/fixture:dependency:unrelated",
        "key": "dependency|pyproject.toml::untangle",
        "subject": "pyproject.toml::untangle",
        "object": "*",
        "text": "untangle was added in pyproject.toml",
        "about": [{"id": "file:test/fixture:pyproject.toml", "labels": ["File"], "name": "pyproject.toml", "path": "pyproject.toml"}],
        "supersedes": [],
        "superseded_by": [],
    })
    ev.dossiers = [Dossier([unrelated]), *ev.dossiers]
    text = render_template(ev, at_ms=ev.decision.at_ms)
    assert text.startswith("On 1 Jan 2019 nothing was recorded yet about `app.concurrency` in `config.toml`")


def test_historical_subject_selection_is_shared_by_answer_confidence_and_chain():
    ev = FX.evidence("what was app.concurrency on 2019-01-01?", at="2019-01-01")
    unrelated = version_from_row(FX.row_new() | {
        "id": "dec:test/fixture:dependency:in-force-unrelated",
        "key": "dependency|pyproject.toml::untangle",
        "subject": "untangle",
        "object": "*",
        "text": "untangle is used by the project",
        "valid_from": 1,
        "valid_to": None,
        "status": "active",
        "about": [{"id": "file:test/fixture:pyproject.toml", "labels": ["File"], "name": "pyproject.toml", "path": "pyproject.toml"}],
        "supersedes": [],
        "superseded_by": [],
    })
    ev.dossiers = [Dossier([unrelated]), *ev.dossiers]

    led = ev.lead(ev.decision.at_ms)
    assert led is not None and led[1].id == FX.dec_old
    assert render_template(ev, at_ms=ev.decision.at_ms).startswith(
        "On 1 Jan 2019 nothing was recorded yet about `app.concurrency` in `config.toml`"
    )
    confidence = score(signals_from(ev, at_ms=ev.decision.at_ms, now_ms=T_NOW))
    assert "no decision was in force on 1 Jan 2019" in confidence.reasons
    assert evidence_chain(ev, ev.decision.at_ms)[0].id == FX.dec_old


def test_historical_gap_uses_last_value_before_the_date():
    ev = FX.evidence("what was app.concurrency?", at="2022-05-01")
    ev.dossiers[0].oldest.valid_to = 1640995200000  # 2022-01-01; next version starts in 2023
    led = ev.lead(ev.decision.at_ms)
    assert led is not None and led[1].id == FX.dec_old
    text = render_template(ev, at_ms=ev.decision.at_ms)
    assert f"the last one before it, 5, ended on 1 Jan 2022 [{FX.dec_old}]" in text
    assert evidence_chain(ev, ev.decision.at_ms)[0].id == FX.dec_old


def test_template_is_current_yes_and_no():
    yes = render_template(FX.evidence("is app.concurrency still 10?"))
    assert yes.startswith(f"Yes — `app.concurrency` in `config.toml` is still 10, active since 14 Mar 2023 [{FX.dec_new}].")
    no = render_template(FX.evidence("do we still cap app.concurrency at 5?"))
    assert no.startswith(f"No — `app.concurrency` in `config.toml` was 5 until 14 Mar 2023 [{FX.dec_old}].")
    assert f"It was superseded on 14 Mar 2023 by 10, set in PR #812 'Limit concurrency after SMTP errors' by Kailash Nadh [{FX.dec_new}]." in no
    neutral = render_template(FX.evidence("is app.concurrency still current?"))
    assert neutral.startswith("Yes — `app.concurrency` in `config.toml` is 10")


def test_template_who_to_ask():
    text = render_template(FX.evidence("who should I ask about app.concurrency?"))
    assert text.startswith(f"Person to ask about `app.concurrency` in `config.toml`: Kailash Nadh, who authored 2 of 2 commits on app.concurrency, stated 2 recorded decisions about it [{FX.person}].")
    assert f"The latest recorded decision about it was stated by Kailash Nadh in PR #812 'Limit concurrency after SMTP errors' on 14 Mar 2023 [{FX.dec_new}]." in text


def test_template_what_changed_tells_the_story_oldest_first():
    text = render_template(FX.evidence("what changed in app.concurrency?"))
    assert text.startswith("`app.concurrency` in `config.toml` changed 1 time: first 5 (commit 3fa2c1d 'Set concurrency to 5', 2 Jun 2021) [")
    assert f"now 10 (PR #812 'Limit concurrency after SMTP errors', 14 Mar 2023) [{FX.dec_new}]." in text
    assert "The latest stated reason: The SMTP provider rate-limits above 10 concurrent connections" in text


def test_template_list_decisions():
    text = render_template(FX.evidence("list the decisions about app.concurrency"))
    assert text.startswith("2 decisions are recorded about `app.concurrency` in `config.toml`: 1) app.concurrency in config.toml is 10")
    assert f"(superseded, 2 Jun 2021) [{FX.dec_old}]" in text


def test_template_fallback_without_decisions_uses_prs_and_commits():
    ev = FX.evidence(with_dossiers=False)
    ev.prs = [{"id": FX.pr, "number": 812, "title": "Limit concurrency after SMTP errors", "merged_at": 1678789320000, "author": {"name": "Kailash Nadh"},
               "closes": [{"id": FX.issue, "number": 790, "title": "SMTP errors under load", "is_incident": True}]}]
    ev.commits = [{"id": FX.commit_new, "sha": "9b8c7d6e5f4a", "title": "Limit concurrency after SMTP errors (#812)", "authored_at": 1678789320000, "author": {"name": "Kailash Nadh"}}]
    text = render_template(ev)
    assert text.startswith(f"No recorded decision explains `app.concurrency` in `config.toml`, but it last changed in PR #812 'Limit concurrency after SMTP errors' by Kailash Nadh on 14 Mar 2023 [{FX.pr}], which closed incident #790 'SMTP errors under load' [{FX.issue}].")
    assert f"The latest commit on it is commit 9b8c7d6 'Limit concurrency after SMTP errors (#812)' by Kailash Nadh on 14 Mar 2023 [{FX.commit_new}]." in text
    assert validate(text, ev) is None


@pytest.mark.parametrize("question", ["why is app.concurrency 10?", "what changed in app.concurrency?", "who should I ask about app.concurrency?", "is app.concurrency still 10?", "list decisions about app.concurrency"])
def test_every_template_validates_against_its_own_evidence(question: str):
    ev = FX.evidence(question)
    text = render_template(ev)
    assert validate(text, ev) is None, text


def test_refusal_wording():
    ev = FX.evidence("why does the billing webhook retry twice?", with_dossiers=False)
    text = render_refusal(ev)
    assert text == (
        "Untangle found nothing in the graph that answers that. Closest related: app.concurrency in config.toml (ConfigKey), config.toml (File). "
        "Person to ask: Kailash Nadh, who authored 2 of 2 commits on app.concurrency, stated 2 recorded decisions about it."
    )
    ev.entities, ev.people = [], []
    assert render_refusal(ev) == "Untangle found nothing in the graph that answers that. Closest related: none. Person to ask: no one is recorded for this."
