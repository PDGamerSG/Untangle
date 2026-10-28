# Upstream, attribution and disclosure

Kyun was started on 28 October 2026 for hackFront India 2026 (Where U Elevate), after Team Vulcan's
Bengaluru round. The organisers asked finalists to build on top of their round entry. This file records
exactly what Kyun inherits and what is new, so judges can tell the two apart.

## Lineage

| Project | Licence | Where | What Kyun takes from it |
|---|---|---|---|
| **Helium** (Team Vulcan, Neo4j) | MIT | https://github.com/PDGamerSG/helium, commit `af80c8b` | The temporal memory model (facts with `valid_from`/`valid_to` and `created_at`/`expired_at`, `SUPERSEDES` chains, `belief_at` and `why_path` queries), the numbered-Cypher-file convention and loader (`src/kyun/graph/queries.py`), the Neo4j handle pattern (`src/kyun/graph/db.py`), the answer rules (cite every claim, tell changes oldest-first, refuse when evidence is missing) and the citation validator. |
| **Minutes** (Team Vulcan, FalkorDB) | MIT | https://github.com/PDGamerSG/minutes-falkordb | The atomic "remember or supersede in one statement" idea (`cypher/2x_*`). Minutes was pre-event work for FalkorDB Graph Hacks; no FalkorDB code is used here. |
| **Vision** (Team Vulcan, FalkorDB) | MIT | https://gitlab.com/vision-hq/vision | The Sarvam speech-to-text client shape (28 s windows, retries, danda-aware sentence split) and the review-before-filing flow. Vision was a GitLab Transcend (Devpost) entry; nothing is copied verbatim. |
| **On Record** (Team Vulcan, FalkorDB) | Apache-2.0 | https://github.com/PDGamerSG/On-Record | The per-sentence grounding check (every number and claim in an answer must appear in a cited source). On Record was a Hacktoberfest Hack Day Bengaluru entry. |

Everything else in this repository is new work for hackFront: the code-history graph model, Git/GitHub
ingestion, deterministic decision and supersession signals (reverts, ADR status, config-value and
dependency changes), entity resolution across renames, the evidence-based confidence score, the
vector-only baseline and evaluation harness, the KT (handover call) pipeline, the API and the web app.

## AI disclosure (required by the hackFront rules)

Claude Code (Anthropic) was used as a pair programmer throughout: scaffolding, drafting modules and
tests from our specifications, and reviewing diffs. Every design decision, the graph model, the
evaluation questions and all judgement calls are the team's. Language-model APIs used at runtime are
listed in the README under "Models and services", together with what each one does; the system
answers from the graph alone when no model key is configured.

## Third-party services and data

- Neo4j AuraDB / Neo4j Community edition (Neo4j licence terms).
- Sarvam AI APIs for Hindi, Hinglish and English speech-to-text, translation and text generation.
- GitHub REST API for pull requests, reviews and issues of public repositories.
- Demo repositories are public open-source projects; their history is read, never executed.
- Handover-call audio in `data/kt/` is recorded by team members with everyone's consent, or synthetic.
