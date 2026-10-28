<div align="center">

# Kyun (क्यों)

### Why is the code like this? Ask, and get the decision, the discussion, the person and the date.

**hackFront India 2026 · Open Source & Innovation · Neo4j track · Sarvam track**

</div>

Kyun reads a repository's history (commits, pull requests, reviews, issues, design records, config and dependency
changes) and the handover calls where engineers explain their code in Hinglish, and turns them into a Neo4j graph of
**decisions moving through time**. Ask it why something is the way it is and it answers with a chain of evidence,
tells you when a later decision quietly replaced an earlier one, shows how sure it is and why, and says plainly when
the graph does not know.

This README follows the order the Open Innovation brief says judges read in.

---

## 1. The problem in one sentence

When an engineer leaves an Indian software team, the reasons behind the code leave with them, scattered across
commits, PR threads, incident tickets and handover calls nobody can search, so the next engineer either asks around
for days or follows a rule that was reversed two years ago.

## 2. The user

> **TEAM: replace this with a real person you interviewed (name, role, company type, city).** Draft persona until then:
> Ananya, 23, SDE-1 at a Bengaluru product company, three weeks into owning a service whose author left on a 60-day
> notice. She has two recorded KT calls in Hinglish and a five-year repository. Her first PR stalled for four days
> because nobody could tell her why a limit was set the way it is.

## 3. The evidence

> **TEAM: fill from `../research/interviews.md` (target 12 conversations; quote the numbers people give you).**

The problem statement the organisers published for this theme (T1.1, *Why The Code Is Like This*) names the same
failures we hear: vector search returns text that mentions a topic rather than the decision that governs it;
documentation drifts while commits keep telling the truth; reversed decisions still look authoritative; nobody links
an incident to the line that changed because of it.

## 4. What exists today, and why it is not enough

| Tool | What it does | What it cannot do |
|---|---|---|
| `git blame`, GitLens | last author of a line | the decision behind it, or that it was reversed |
| DeepWiki, Copilot Spaces | explain *what* the code does | history, supersession, the person to ask |
| Unblocked and similar | retrieval over code + chat | a model of time: which decision is in force, which is dead |
| ADRs | record big decisions | they are rare and drift; most decisions live in PRs |
| Recorded KT calls | exist in every Indian IT team | unsearchable, in Hinglish, disconnected from the code |

## 5. What we built

A working system on a real, public, long-lived repository: **knadh/listmonk** (Indian open-source newsletter
manager, Go, ~2,300 commits and ~900 pull requests since 2018).

```
GitHub + git history ─┐                                     ┌─ kyun ask (CLI)
ADRs, docs, configs  ─┼─► ingestion ─► Neo4j decision graph ─┼─ FastAPI ─► web app (Next.js)
Hinglish KT calls ────┘   (Sarvam)     (AuraDB-compatible)   └─ eval harness (graph vs vector-only)
```

**What it does, every item running:**

- **Decisions from deterministic signals first.** Every config key and dependency version is followed through
  history; a new value supersedes the old one (`SUPERSEDES {signal: 'config_diff' | 'lockfile_diff'}`), and the old
  one stays readable with its dates. Merged PRs become change decisions linked to their reviews, commits and the
  issues they close (incidents flagged). Reverts and "supersedes #N" text link decisions explicitly, and ADRs are
  parsed with their status (both covered by tests on a fixture repository; listmonk itself has no ADRs and no revert
  commits on its default branch). On listmonk: 2,531 decisions, 891 of them superseded by a later value.
- **Answers with a chain of evidence.** decision → discussion (PR, commit, issue) → incident → person → date, every
  claim cited by node id. The *Why this answer* panel shows the route, every Cypher query that ran with its row count,
  and the subgraph it read.
- **Supersession, said out loud.** "`github.com/lib/pq` is pinned at v1.12.3 … that decision is still active",
  with the five earlier versions in order. Ask "as of 1 Jan 2020" and you get what was true then.
- **A confidence score from the graph, never from the model**: evidence count, source authority (ADR > PR review >
  PR > commit message > issue > call), whether the leading decision is active, entity match strength, agreement,
  age, incident link. Each reason is shown.
- **Honest refusal.** "Why does listmonk use MongoDB?" → *Kyun found nothing in the graph that answers that*, with
  the closest related entities and the person to ask. Generic words and the repository's own name never anchor an
  answer.
- **Kyun Pulse, the proactive layer.** Before anyone asks a question, the repository gets a ranked knowledge-risk queue: code-vs-handover contradictions, decision drift, ownership gaps and missing rationale. Every warning carries the graph facts that caused it, plus an Ask action that hands the risk into the normal evidence flow.
- **Person to ask**, ranked by recency-weighted authorship, reviews, review comments and stated decisions, with the
  counts ("authored 57 of 69 commits on manager, reviewed 1 of 15 PRs touching it").
- **Handover calls (KT) through Sarvam AI.** Saaras speech-to-text (code-mixed mode, diarization, keyterms built from
  the repository's own identifiers so `app.concurrency` is spelled right), utterances linked to the files and keys
  they mention, decisions extracted with their quotes. A spoken statement **never overwrites the code history**: it
  is linked to the repository's record as `CONFIRMS` or `CONTRADICTS`, and an answer names the conflict.
- **A vector-only baseline in the same UI**, so the difference the graph makes is visible on every question.

**Run it** (Windows, macOS or Linux; Docker, Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20+ with pnpm):

```bash
cp .env.example .env                    # set NEO4J_PASSWORD; GITHUB_TOKEN or `gh auth login` for the API limit
docker compose up -d neo4j              # or point NEO4J_URI at an AuraDB instance (neo4j+s://…)
uv sync --all-extras
uv run kyun schema
uv run kyun ingest knadh/listmonk       # first run ~10 min (3.8k GitHub API calls, cached on disk) plus ~16 min of
                                        # CPU embeddings with EMBED_BACKEND=fastembed (cached too); re-runs take ~1 min
uv run kyun kt ingest --repo knadh/listmonk --transcript data/kt/listmonk-kt-sample.json
uv run kyun ask "why is app.concurrency set the way it is?" --repo knadh/listmonk
uv run kyun serve                       # API on http://127.0.0.1:8090
cd web && pnpm install && pnpm dev      # web app on http://localhost:3000
```

The API emits an `x-request-id` header on every response. Custom error responses repeat that value as `request_id` so a failed question can be traced in server logs. `GET /health` keeps the original `ok`, `neo4j`, `llm`, and `embed` fields and adds a `status`, a safe `graph` readiness summary, and `optional_backends` for operational checks; the new fields never expose credentials or secret configuration values.

No model key is needed: answers are rendered from the graph by a deterministic template unless `LLM_BACKEND` is set
(`anthropic`, `sarvam` for sarvam-105b, or any OpenAI-compatible server), and a model answer is only accepted when
every citation exists in the evidence and every number in it appears in a cited source. Sample mode
(`NEXT_PUBLIC_KYUN_SAMPLE=1`) replays real recorded answers from the live graph (see `web/README.md`).

**Link to it running:** _TEAM: add the hosted URL once deployed (AuraDB instance + API host + web)._

### Evaluation

`uv run kyun eval --repo knadh/listmonk --gold eval/gold/listmonk.yaml` asks 25 gold questions twice: through the
graph, and through **vector-only retrieval over exactly the same text** (bge-small embeddings, no decisions, no time,
no refusal logic). Full per-question report: [docs/EVAL.md](docs/EVAL.md). Verified questions (19):

| Metric | Kyun (graph) | Vector-only |
|---|---|---|
| Evidence-chain accuracy (right citation and right content) | **9/11 (82%)** | 4/11 (36%) |
| Supersession correctness (names the live value, not the dead one) | **1/1** | 0/1 |
| Refusal precision / recall on 5 questions the repo never decided | **100% / 100%** | refuses nothing |
| Person to ask | 4/4 | 4/4 |
| Latency p50 / p95 | 31 ms / 96 ms | 14 ms / 1,369 ms |

What still fails, honestly: "Which Postgres driver does listmonk use?" names no identifier, so the graph anchors on
`postgres.user` instead of inferring `github.com/lib/pq`; and "was the retry logic ever reverted?" needs a model to
extract that sentence from the handover call (the heuristic extractor, used when no model key is set, misses it). The
gold set was written before the history was checked; expectations that could not be verified against the repository are
marked `unverified` and reported separately in docs/EVAL.md.

A worked answer, verbatim from the CLI:

> **why is app.concurrency set the way it is?**
> `app.concurrency` in `schema.sql` is 10 [dec:…1746b14b6895]. It was set in commit 942eb7c 'Add settings UI and "hot
> reload" support to the app.' by Kailash Nadh on 8 Jul 2020 [commit:…942eb7c3d86e]. A recorded handover call confirms
> it and gives the reason: SES का rate limit hit हो रहा था [dec:…kt:507117e52193]. Before it moved to `schema.sql`,
> `config.toml.sample` had it at 5 (2 Apr 2020) and earlier 100 (25 Oct 2018), until it was removed there on 8 Jul 2020.
> Person to ask: Kailash Nadh, who authored 114 of 133 commits on app.concurrency …
>
> *confidence 0.69 (medium): 2 independent sources; backed by a commit message; decision is active; a recorded
> handover call confirms it; entity matched exactly; the decision is 6 years old; stated by a named person*

The vector-only baseline, asked the same question, returns the closest passages by similarity, with no current value,
no dates and no sign that 5 and 100 are dead.

## 6. What was hard (our layer beneath)

- **Entity resolution.** The same file has many paths over five years and the same person has many emails. Kyun keeps
  a `File` per historical path joined by `RENAMED_FROM {at, sha}` from git's rename detection, and resolves people
  through `Identity` nodes (emails, logins, meeting speakers) learned from PR commit lists.
- **Temporal reasoning.** Decisions are bi-temporal (when a value was in force, when Kyun learned it), the model from
  our Helium project. Supersession is one atomic Cypher statement (`cypher/21_record_decision.cypher`), so two
  writers cannot leave two "current" values; same-key rows are recorded in chronological rounds because rows inside
  one `UNWIND` see each other's half-written state.
- **Knowing what the question is about.** "Why does listmonk use MongoDB?" first answered with `db.host`, because the
  `db` of *MongoDB* matched it. Anchors must now share a specific token with the question, and a fragment of a named
  identifier counts in proportion to how much of it matches.
- **Speech vs code.** A synthetic handover call first *superseded* the repository's own record. Spoken statements now
  live on their own keys and are reconciled (`CONFIRMS` / `CONTRADICTS`); the answer leads with the code. The call
  then appeared to contradict five settings, which was our bug, not the call's: listmonk moved those settings into
  the database in July 2020 and seeds them from `schema.sql` as `('app.concurrency', '10')`. Ingestion now reads SQL
  settings seeds, reconciliation matches a key in whichever file defines it, and four of the five became `CONFIRMS`.
- **Idempotent history.** Invariant checks after a warm re-ingest (every superseded version has a successor, every
  `valid_to` equals its successor's `valid_from`, no key has two different active values) caught our late-import rule
  re-linking old versions straight to the newest one. Fixed with regression tests; a re-ingest now leaves the graph
  unchanged.
- **Grounding a model.** Citations are validated against the evidence ids and every two-digit number is checked
  against the cited sources; anything else falls back to the template. The model writes sentences; the graph decides.

Why a graph at all, in detail: [docs/GRAPH_MODEL.md](docs/GRAPH_MODEL.md).

## 7. Who pays

Engineering leaders: in product companies for faster onboarding and lower attrition risk, and in IT-services firms
where knowledge transfer is a costed part of every transition. The metric they already track is **time to first
meaningful commit** for a new engineer (the organisers' own commercial wedge). Hypothesis to test: per active
repository per month, free for open source.

## 8. With three more months

- **PR guard**: a GitHub Action that comments when a PR touches code governed by a decision, or re-introduces a
  superseded one.
- **IDE and agents**: an Aura Agent with Cypher-template tools (`why_path`, `belief_at`, `person_to_ask`) over MCP for
  VS Code and Claude Code.
- **KT Box**: an Arduino UNO Q recorder for meeting rooms (ReSpeaker mic array, on-device voice detection and speaker
  turns, a *Decision* button that bookmarks the moment, an off-record switch and a consent light), feeding the same
  Sarvam pipeline.
- **Knowledge-loss map**: "if this person leaves, these decisions lose their only owner".
- Rationale extraction from PR threads with a model, kept only when its quote exists verbatim in a source.

---

## Models and services

| What | Used for | Required? |
|---|---|---|
| Neo4j (local Docker or AuraDB Free) | the graph; vector + full-text indexes; no APOC/GDS needed | yes |
| GitHub REST API | PRs, reviews, review comments, issues (cached on disk) | for PR/issue history |
| Sarvam AI Saaras v4 | speech-to-text for handover calls (code-mixed, diarization, keyterms) | for audio |
| Sarvam AI Mayura / text-lid | English rendering of Hinglish utterances, language id | optional |
| Sarvam AI Bulbul v3 | `scripts/make_kt_audio.py` voices the sample call for pipeline tests | optional |
| sarvam-105b, Claude Haiku, or any OpenAI-compatible model | writing the answer sentence; KT decision extraction | optional |
| BAAI/bge-small-en-v1.5 via fastembed (CPU) | the vector-only baseline and chunk recall | optional (a hash embedder is the default) |

## Repository

```
cypher/          every query the product runs, numbered (00 schema · 1x ingest · 2x decisions · 3x answers · 4x KT · 5x baseline)
src/kyun/        graph, ingest (git, GitHub, docs, symbols, config history), answer, kt (Sarvam), eval, api, cli
web/             Next.js app: Ask, decision pages, timeline, meetings
eval/gold/       gold questions; `kyun eval` writes eval/out/
data/kt/         the synthetic Hinglish handover call and how to record a real one
docs/            CONTRACTS (graph model and API), GRAPH_MODEL (why a graph), DEMO (run of show)
scripts/         make_kt_audio (Sarvam voices), export_sample (web sample mode from real answers)
```

Tests: `uv run pytest` (the Neo4j tests skip when no server answers) · `uv run ruff check src tests` ·
`cd web && pnpm lint && pnpm build`. CI runs all of them with a Neo4j service container.

## Attribution and AI disclosure

Kyun builds on Team Vulcan's earlier open-source work (Helium on Neo4j, and patterns from Minutes, Vision and
On Record); exactly what was reused and what is new for hackFront is in [UPSTREAM.md](UPSTREAM.md), with the AI
disclosure the hackFront rules require. The demo handover call is synthetic and labelled as such. MIT licence.
