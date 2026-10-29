<div align="center">

# 🧭 Untangle

### Ask why the code is like this, and follow the evidence back through time.

**Repository decisions · supersession · handovers · cited answers**

[![License](https://img.shields.io/badge/license-MIT-1a7f37?style=for-the-badge)](LICENSE)
![Python](https://img.shields.io/badge/python-3.12%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/web-Next.js-111?style=for-the-badge&logo=next.js&logoColor=white)
![Graph](https://img.shields.io/badge/graph-Neo4j-008cc1?style=for-the-badge)
![Status](https://img.shields.io/badge/status-open%20source-2f6fde?style=for-the-badge)

</div>

Untangle turns a repository's history and handover conversations into a searchable decision graph. Ask why a value, dependency, file, or module exists and it traces the answer through commits, pull requests, reviews, issues, documents, and recorded knowledge-transfer calls. Each answer names its evidence, shows which decision is current, and says when the graph does not know.

## 💡 Why Untangle

| | |
|---|---|
| 🧵 **Follow the thread** | Connect a decision to the discussion, commit, issue, person, and date that support it. |
| ⏳ **Respect history** | See the value that was true at a chosen date and which later decision replaced it. |
| 🗣️ **Keep handovers searchable** | Ingest English or Hinglish calls and link spoken decisions to the code record. |
| 🔎 **Answer with evidence** | Every answer includes citation ids, a confidence score, and the path the graph followed. |
| 🚫 **Refuse honestly** | When no decision is recorded, Untangle says so and shows the closest related entities. |
| 📡 **Spot knowledge risk** | Untangle Pulse ranks contradictions, drift, missing rationale, and ownership gaps before they slow someone down. |
| 🔒 **Run it yourself** | The default answer path is deterministic and works without a model key. |

## 🚀 Three steps

1. **Ingest a repository.** Untangle reads git history, GitHub discussions, docs, symbols, config changes, and dependencies.
2. **Ask a question.** The router resolves the named entity, retrieves its decision chain, and gathers the supporting evidence.
3. **Review the path.** The CLI and web app show the answer, citations, supersession timeline, confidence reasons, and the person to ask.

## 📥 Quick start

Prerequisites: Docker, Python 3.12, [uv](https://docs.astral.sh/uv/), Node 20+, and pnpm 10.

```bash
git clone https://github.com/PDGamerSG/Untangle.git
cd Untangle
cp .env.example .env                    # set NEO4J_PASSWORD for local development
docker compose up -d neo4j
uv sync --all-extras
uv run untangle schema
uv run untangle ingest knadh/listmonk
uv run untangle ask "why is app.concurrency set the way it is?" --repo knadh/listmonk
uv run untangle serve                       # API: http://127.0.0.1:8090

cd web
pnpm install
pnpm dev                                   # web: http://localhost:3000
```

For a zero-service UI walkthrough, run the web app with sample fixtures:

```bash
cd web
NEXT_PUBLIC_UNTANGLE_SAMPLE=1 pnpm dev
```

The sample mode is self-contained and reads the files in `web/sample/`; it does not call Neo4j or the API.

The project landing page is a separate static site that needs no services at all:

```bash
cd landing
pnpm install
pnpm dev                                   # landing: http://localhost:5180
```

## 🔍 What it does

| Stage | What happens |
|---|---|
| **Ingest** | Clones a repository into a cache, reads commits and renames, fetches GitHub PRs/issues/reviews, parses docs and symbols, and records config/dependency changes. |
| **Model** | Stores repositories, files, people, discussions, decisions, and handover utterances in Neo4j. A new value supersedes the old one without deleting its history. |
| **Resolve** | Matches question terms to exact files, modules, config keys, dependencies, and symbols. Generic words and unrelated repository names do not anchor an answer. |
| **Answer** | Renders a deterministic evidence-backed answer, or optionally asks a configured model to write one that must pass citation and number-grounding checks. |
| **Compare** | Shows the graph answer beside a vector-only baseline over the same text so the value of temporal structure is visible. |
| **Pulse** | Ranks knowledge risks and links every warning to the same evidence flow used by Ask. |

The core flow is:

```text
Git + GitHub + docs + handover calls
                    │
                    ▼
              Untangle ingest
                    │
                    ▼
             Neo4j decision graph
              │       │       │
              ▼       ▼       ▼
           CLI Ask  FastAPI  Next.js web
```

## 🧩 Main components

| Folder | Purpose |
|---|---|
| `src/untangle/` | Python package for graph access, ingestion, answering, handovers, evaluation, API, and CLI. |
| `cypher/` | Numbered Cypher statements used by the application. |
| `web/` | Next.js interface for Ask, Pulse, decisions, timeline, and meetings. |
| `landing/` | Static, scroll-driven landing page (Three.js) built from the sample fixtures; no backend needed. |
| `tests/` | Unit, contract, fixture, and optional Neo4j integration tests. |
| `data/kt/` | Transcript format notes and the synthetic handover sample. |
| `eval/gold/` | Gold questions for graph-versus-vector evaluation. |
| `docs/` | API contracts, graph model, demo runbook, and evaluation notes. |

## 🧠 How answers stay grounded

Untangle keeps decisions temporal. Each version has a `valid_from` and optional `valid_to`; a later config, dependency, revert, or explicit supersession links to the prior version. The answer service then builds a path such as:

```text
question → entity → decision → discussion → commit / issue / person → date
```

A confidence score comes from graph signals: evidence count, source authority, whether the decision is active, agreement, entity match, recency, and incident links. When a handover contradicts the repository record, the code history stays authoritative and the conflict is shown.

## ⚠️ Known limits

- Ingestion needs a reachable Neo4j instance; GitHub history also needs API access and benefits from a token.
- The default deterministic answer can only repeat rationale that exists in the graph. A model can improve wording, but it cannot add uncited claims.
- Handover audio transcription and translation require Sarvam credentials; the included transcript is synthetic demo data.
- The graph describes repository history. It does not execute untrusted repository code or prove that a historical decision was objectively correct.
- Sample mode uses the checked-in `knadh/listmonk` fixtures and is not a substitute for ingesting your own repository.
- The web client is designed for current desktop browsers; mobile layouts are usable but less tested.

## 🛠️ Development

```bash
uv sync --all-extras
uv run ruff check src tests
uv run pytest
cd web && pnpm install && pnpm lint && pnpm build
```

Configuration is documented in `.env.example`. The important variables are `NEO4J_*`, `GITHUB_TOKEN`, `UNTANGLE_REPO_CACHE`, `LLM_BACKEND`, `EMBED_BACKEND`, `SARVAM_API_KEY`, `NEXT_PUBLIC_UNTANGLE_API`, and `NEXT_PUBLIC_UNTANGLE_SAMPLE`.

Every query belongs in `cypher/` and is loaded by name. Keep answer citations and API response fields stable when changing internals; the contract is documented in [docs/CONTRACTS.md](docs/CONTRACTS.md).

## 📄 License

[MIT](LICENSE).
