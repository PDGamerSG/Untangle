# Untangle contracts: graph model, module boundaries, CLI and API

This is the source of truth every module is written against. Change it here first.

## 1. Conventions

- Python 3.12, `src/untangle` package, `uv` for everything (`uv sync --all-extras`, `uv run pytest`, `uv run ruff check`).
- **Every Cypher query lives in `cypher/NN_name.cypher`** and is loaded with `untangle.graph.queries.load_cypher("name")`
  (or `Graph.run_named`). Numbering: `00` schema · `10–19` ingestion upserts · `20–29` decisions and supersession ·
  `30–39` answering and retrieval · `40–49` handover calls (KT) · `50–59` baseline and evaluation · `60–69` stats and admin.
  Cypher is bundled under `untangle/graph/cypher/` in wheels. Set `UNTANGLE_CYPHER_DIR` to select a custom
  query directory before the checkout or bundled copies. Parameters are `$name`. Batch writes take `$rows` (a list of maps) and `UNWIND $rows AS r`.
- **Timestamps are epoch milliseconds (int)** on every node and relationship (`authored_at`, `created_at`, `valid_from`, …).
  The API renders ISO-8601 strings next to them (`*_iso`). Never store Neo4j temporal types.
- **Repository-scoped nodes carry `repo`** (the GitHub `owner/name`). People and identities can be shared across
  repositories; query traversal scopes their activity to the requested repository.
- Node ids come from `untangle.ids` and are deterministic; ingestion is idempotent (`MERGE` on `id`, `SET` properties).
- Full-text indexes: `entity_search` (File, Module, Symbol, ConfigKey, Dependency on `name|path|key|tokens`),
  `person_search`, `text_search` (Decision, PullRequest, Issue, Comment, Commit, Document, Chunk, Utterance on
  `title|text|body|message`). Query them with `CALL db.index.fulltext.queryNodes('entity_search', $q)`.
  Lucene syntax: sanitise user text to `term1 OR term2` of plain tokens (see `untangle.ids.tokens`).
- Vector index: `chunk_embedding` on `Chunk.embedding`, cosine, dimension = `EMBED_DIM` (384 default).
- Only AuraDB-Free features: no APOC, no GDS, one database. Graph algorithms are plain Cypher.
- Logging via `logging.getLogger("untangle.<module>")`. No prints outside the CLI.
- Tests: `tests/` with pytest. Tests that need Neo4j use the `graph` fixture from `tests/conftest.py`, which
  skips when the server does not answer; everything else runs against fakes (`FakeLLM`, `FakeEmbedder`, recorded
  GitHub JSON, a small git fixture repo created in `tmp_path`).

## 2. Graph model

### Nodes (label → properties; `id` is unique on every label)

| Label | Properties |
|---|---|
| `Repo` | `id`, `full_name`, `url`, `default_branch`, `head_sha`, `ingested_at`, `commit_count`, `languages` (list) |
| `Person` | `id`, `name`, `login` (GitHub, nullable), `email` (nullable), `tokens`, `kind` (`contributor`/`speaker`) |
| `Identity` | `id`, `kind` (`email`/`login`/`speaker`), `value` — `(Identity)-[:IDENTITY_OF]->(Person)` |
| `Commit` | `id`, `sha`, `repo`, `title`, `message`, `authored_at`, `committed_at`, `is_merge`, `is_revert`, `reverts_sha` (nullable), `url`, `additions`, `deletions`, `files_changed` |
| `File` | `id`, `repo`, `path`, `name`, `ext`, `tokens`, `is_config`, `is_doc`, `alive` (exists at HEAD), `first_seen_at`, `last_touched_at`, `touch_count` |
| `Module` | `id`, `repo`, `path` (directory, `.` for root), `name`, `tokens` |
| `Symbol` | `id`, `repo`, `name`, `kind` (`function`/`class`/`method`/`const`/`type`), `path`, `line`, `tokens` |
| `ConfigKey` | `id`, `repo`, `key` (dotted), `path`, `tokens`, `current_value`, `current_since` |
| `Dependency` | `id`, `repo`, `name`, `ecosystem` (`go`/`npm`/`pypi`/`cargo`/`maven`/`other`), `tokens`, `current_version` |
| `PullRequest` | `id`, `repo`, `number`, `title`, `body`, `state`, `merged` (bool), `created_at`, `merged_at`, `closed_at`, `url`, `author_login`, `labels` (list), `additions`, `deletions`, `changed_files` |
| `Issue` | `id`, `repo`, `number`, `title`, `body`, `state`, `labels` (list), `created_at`, `closed_at`, `url`, `author_login`, `is_incident` (bool). Incidents also carry the label `:Incident`. |
| `Comment` | `id`, `repo`, `kind` (`pr_review`/`pr_review_comment`/`pr_comment`/`issue_comment`), `body`, `created_at`, `url`, `author_login`, `path` (nullable), `line` (nullable), `review_state` (nullable) |
| `Document` | `id`, `repo`, `path`, `title`, `kind` (`adr`/`design`/`changelog`/`readme`/`doc`), `status` (ADR status text, nullable), `adr_number` (nullable), `date` (ms, nullable), `text`, `superseded_by_path` (nullable) |
| `Chunk` | `id`, `repo`, `text`, `source_id`, `source_kind` (`pr`/`issue`/`comment`/`commit`/`document`/`utterance`), `seq`, `created_at`, `embedding` (float list) |
| `Decision` | see §3 |
| `Meeting` | `id`, `repo`, `title`, `started_at`, `duration_ms`, `language` (e.g. `hi-IN`), `source` (`sarvam-batch`/`sarvam-rest`/`transcript-json`), `audio_uri` (nullable), `summary` |
| `Utterance` | `id`, `repo`, `meeting_id`, `seq`, `text` (as spoken, e.g. Hinglish), `text_en` (English rendering, nullable), `start_ms`, `end_ms`, `speaker_label`, `language` |

### Relationships

```text
(Person)-[:AUTHORED]->(Commit)              (Person)-[:COMMITTED]->(Commit)
(Commit)-[:TOUCHED {change:'A'|'M'|'D'|'R', additions, deletions}]->(File)
(File)-[:RENAMED_FROM {at, sha}]->(File)    (File)-[:IN]->(Module)     (Module)-[:IN]->(Module)
(Symbol)-[:DEFINED_IN]->(File)              (ConfigKey)-[:SET_IN]->(File)   (Dependency)-[:DECLARED_IN]->(File)
(Commit)-[:PART_OF]->(PullRequest)          (Commit)-[:REVERTS]->(Commit)
(Person)-[:OPENED]->(PullRequest|Issue)     (Person)-[:REVIEWED {state, at}]->(PullRequest)
(Comment)-[:ON]->(PullRequest|Issue)        (Person)-[:WROTE]->(Comment)   (Comment)-[:ABOUT_LINE]->(File)
(PullRequest)-[:CLOSES]->(Issue)            (PullRequest|Issue|Commit)-[:REFERENCES]->(Issue|PullRequest)
(PullRequest)-[:TOUCHED]->(File)            (derived from its commits; speeds up "PRs about this file")
(Document)-[:STORED_AS]->(File)             (Document)-[:SUPERSEDED_BY]->(Document)
(Chunk)-[:FROM]->(PullRequest|Issue|Comment|Commit|Document|Utterance)
(Decision)-[:ABOUT]->(File|Symbol|ConfigKey|Dependency|Module)
(Decision)-[:DECIDED_IN]->(PullRequest|Issue|Document|Commit|Meeting)
(Decision)-[:EVIDENCED_BY]->(Commit|Comment|Document|Utterance|PullRequest|Issue)
(Decision)-[:STATED_BY]->(Person)           (Decision)-[:IMPLEMENTED_BY]->(Commit)
(Decision)-[:MOTIVATED_BY]->(Issue)         (Decision)-[:SUPERSEDES {at, signal}]->(Decision)
(Decision:kt)-[:CONFIRMS {at}]->(Decision)  (Decision:kt)-[:CONTRADICTS {at}]->(Decision)
(Meeting)-[:HAS]->(Utterance)               (Utterance)-[:NEXT]->(Utterance)
(Utterance)-[:SPOKEN_BY]->(Person)          (Utterance)-[:MENTIONS]->(File|Symbol|ConfigKey|Dependency)
(Meeting)-[:ABOUT_REPO]->(Repo)
```

## 3. Decisions and supersession (the core)

```text
Decision {
  id, repo,
  kind:      'config_value' | 'dependency' | 'adr' | 'revert' | 'change' | 'rationale' | 'kt',
  key:       lower-cased "subject|predicate" (code history); "kt|subject|predicate" (spoken decisions),
  subject:   the entity the decision is about (file path, dotted config key, dependency name, ADR title, …),
  predicate: 'config_value' | 'uses_dependency' | 'dependency_version' | 'adr_status' | 'reverted' | 'changed'
             | 'chose' | 'constraint' | 'workaround_for' | 'owner' | 'deprecated' | 'kt_said',
  object:    the value / choice as text,
  text:      one readable sentence: "retry_limit in config/app.yaml is 3 (set in PR #812 after incident #790)",
  rationale: the stated reason, verbatim or summarised, nullable,
  status:    'active' | 'superseded' | 'retracted',
  valid_from, valid_to (nullable), created_at, expired_at (nullable),   -- all epoch ms; valid time and graph recording time
  confidence: 0..1 (deterministic signals 0.9+, LLM-extracted 0.5–0.8, KT 0.6),
  signal:    what produced it: 'config_diff' | 'lockfile_diff' | 'adr_status' | 'revert_commit' | 'pr_merge'
             | 'supersedes_text' | 'llm_pr_thread' | 'llm_kt' | 'heuristic_kt'
}
```

Rules:

1. A decision is `active` from `valid_from` until a later decision with the **same `key`** and a different `object`
   is recorded; then the old one gets `valid_to = new.valid_from`, `expired_at = now`, `status = 'superseded'`, and
   `(new)-[:SUPERSEDES {at, signal}]->(old)`. Implemented in **one statement** (`cypher/21_record_decision.cypher`:
   MERGE the new decision, expire the active ones with the same key whose `valid_from <= new.valid_from`, link).
2. Explicit supersession signals also link decisions with **different** keys: revert commits (`REVERTS`), ADR
   "Superseded by ADR-0007", PR/commit text "supersedes #N", "replaces #N", "reverts #N".
2a. **Spoken statements never supersede code history.** Decisions from handover calls (`kind: 'kt'`) use the key
   `kt|<subject>|<predicate>`, so a later call can update an earlier call but not the repository's record.
   `cypher/24_reconcile_kt.cypher` then links each spoken config value to the repository's active decision on the
   same `<subject>|<predicate>`: `(kt)-[:CONFIRMS]->(code)` when the values agree, `(kt)-[:CONTRADICTS]->(code)` when
   they differ. Answers lead with the repository decision and cite the call (agreement adds a source; a conflict is
   named in the answer and lowers confidence).
2b. Same-key rows must not share one `$rows` batch of `21_record_decision` (rows in one `UNWIND` see each other's
   half-written state); `untangle.ingest.loader` records them in chronological rounds.
3. `belief_at(t)`: decisions with `valid_from <= t < coalesce(valid_to, +inf)` and `status <> 'retracted'`.
4. `why_path(decision_id)`: the decision, its evidence, who stated it, where it was decided (PR/issue/ADR/meeting),
   the entities it is about, the incident that motivated it, and the whole `SUPERSEDES` chain both ways.

## 4. Module boundaries

| Package | Boundary | Responsibility |
|---|---|---|
| `untangle.graph.*`, `untangle.ids`, `untangle.config`, `untangle.llm`, `untangle.embed` | shared adapters | connection, schema, loader, ids, model adapters |
| `untangle.ingest.*` | repository ingestion | `git_history.py` (clone/fetch, `git log` parsing with renames and numstat), `github_api.py` (PRs, reviews, review comments, issue comments, issues; token or anonymous; on-disk JSON cache under `.cache/github/<repo>/`), `docs.py` (ADRs, design docs, CHANGELOG, README), `symbols.py` (regex symbol + config-key + dependency extraction for Go/Python/TS/JS/Rust/Java and YAML/TOML/JSON/.env/INI), `config_history.py` (config values and dependency versions over time via `git show sha:path`), `decisions.py` (deterministic Decision rows from all signals), `chunks.py` (chunking + embeddings), `loader.py` (batched MERGE writes), `pipeline.py` (`ingest_repo(full_name, …)` orchestration with progress logging) |
| `untangle.answer.*` | evidence and answering | `router.py` (intent + entity resolution), `retrieve.py` (evidence gathering), `confidence.py`, `compose.py` (LLM with citation validation + template fallback + grounding check), `baseline.py` (vector-only RAG), `service.py` (`ask(question, repo, …) -> Answer`) and `untangle.api.main` (FastAPI) |
| `untangle.kt.*` | handover ingestion | `sarvam.py` (batch STT with diarization, REST ≤30 s, language id, translate), `transcript.py` (Sarvam JSON → utterances), `pipeline.py` (`ingest_kt(...)`: Meeting/Utterance/Person, keyterms from the repo's entities, MENTIONS links, decision extraction via LLM with strict JSON or the fake path, `21_record_decision` for each) |
| `untangle.eval.*` | evaluation | gold YAML format, `run_eval` (graph vs baseline), report writer |
| `untangle.cli` | subcommands register through `register(subparsers)` | `untangle schema`, `untangle ingest`, `untangle ask`, `untangle serve`, `untangle kt`, `untangle eval`, `untangle stats` |
| `web/` | web client | Next.js app |

## 5. CLI

```bash
untangle schema                                   # ensure constraints and indexes
untangle ingest owner/name [--max-commits N] [--since YYYY-MM-DD] [--no-github] [--no-embed] [--reset]
untangle ask "why is the retry limit 3?" --repo owner/name [--at 2024-01-01] [--baseline] [--json]
untangle stats [--repo owner/name]
untangle kt ingest --repo owner/name (--audio file.mp3 | --transcript file.json) [--title "..."] [--speakers 3] [--language hi-IN]
untangle eval --repo owner/name --gold eval/gold/<name>.yaml [--out eval/out/<name>.md]
untangle serve [--port 8090]
```

## 6. API (FastAPI, JSON; CORS from settings)

- `GET /health` → legacy `ok`, `neo4j`, `llm`, `embed`, and `sarvam` fields plus `status` (`ok` or
  `degraded`), `graph: {ok, version, aura, edition}`, and safe `optional_backends` availability summaries.
- `GET /repos` → `[{ full_name, head_sha, commit_count, ingested_at_iso, counts: {commits, prs, issues, decisions, meetings} }]`
- `POST /ask` body `{ "question": str, "repo": str, "at": iso|null, "mode": "graph"|"baseline"|"both" }` → `AskResponse`
- `GET /decisions/{id}` → `WhyPath`
- `GET /entities/{id}` → `{ entity, decisions: [DecisionCard], people: [PersonCard], recent_commits: [...] }`
- `GET /search?repo=&q=` → `{ entities: [EntityHit], people: [PersonHit] }`
- `GET /timeline?repo=&at=iso` → `{ at_iso, active: [DecisionCard], superseded_since: [DecisionCard] }`
- `GET /pulse?repo=&limit=24` → `{ repo, generated_at_iso, summary, risks: [PulseRisk] }`; risks are deterministic graph signals, ordered by score. `PulseRisk.category` is `contradiction`, `drift`, `ownership_gap`, `rationale_gap`, or `stale`; `reasons` lists the exact signals that contributed to the score.
- `GET /meetings?repo=` → `[MeetingSummary]` and `GET /meetings/{id}` → `MeetingDetail` (shaped by `untangle.api.meetings`):
  `MeetingSummary {id, repo, title, started_at_iso, duration_ms, language, source, audio_uri, summary, utterance_count,
  speaker_count, decision_count}`; `MeetingDetail` adds `utterances: [{id, meeting_id, seq, text, text_en, start_ms,
  end_ms, speaker_label, speaker: PersonCard|null, language, mentions: [EntityRef]}]`, `speakers: [{label, person}]`
  and `decisions: [DecisionCard]` (the same projection as `/decisions/{id}`)
- `POST /kt/ingest` multipart `{ repo, title, audio | transcript }` → `{ meeting_id, utterances, decisions }`
- `GET /stats?repo=` → label and relationship counts

Responses carry `x-request-id` and `x-untangle-ms` headers. Handled application errors include `request_id`
with the same value, so the client can correlate a failure with server logs. FastAPI request validation retains
its standard `detail` shape; consumers should use the response header for correlation.

```jsonc
// AskResponse
{
  "question": "...", "repo": "owner/name", "mode": "graph",
  "answer": "The retry limit is 3 because ... [dec:...] ...",       // plain text, citations in [brackets]
  "refused": false,                                                 // true => answer is the refusal sentence
  "confidence": { "score": 0.82, "label": "high", "reasons": ["3 independent sources", "decision is active", "stated by the file's main author"] },
  "evidence_chain": [                                               // ordered: decision -> discussion -> person -> date
    { "role": "decision", "id": "dec:...", "title": "...", "status": "active", "valid_from_iso": "...", "valid_to_iso": null },
    { "role": "discussion", "id": "pr:owner/name#812", "title": "...", "url": "...", "excerpt": "..." },
    { "role": "incident", "id": "issue:owner/name#790", "title": "...", "url": "..." },
    { "role": "person", "id": "person:gh:rahul", "name": "Rahul", "why": "authored the change and reviewed 14 PRs on this file" },
    { "role": "date", "iso": "2023-03-14T10:22:00Z" }
  ],
  "supersession": [ { "newer": "dec:...", "older": "dec:...", "at_iso": "...", "signal": "config_diff", "older_text": "...", "newer_text": "..." } ],
  "citations": { "dec:...": { "kind": "decision", "title": "...", "url": "...", "excerpt": "..." }, "commit:...": {...} },
  "entities": [ { "id": "cfg:...", "label": "ConfigKey", "name": "retry_limit", "path": "config/app.yaml" } ],
  "why": {                                                          // "Why this answer" panel
    "route": "entity_why",
    "cypher": [ { "name": "31_decisions_about", "params": {...}, "rows": 4 } ],
    "subgraph": { "nodes": [ { "id": "...", "label": "Decision", "props": {...} } ], "edges": [ { "from": "...", "to": "...", "type": "SUPERSEDES" } ] },
    "llm": { "backend": "fake", "model": "fake", "used": false }
  },
  "baseline": null                                                  // when mode = both: { "answer": "...", "chunks": [ {id, text, source_kind, score} ], "note": "vector-only, no graph" }
}
```

`DecisionCard`: `{ id, kind, key, subject, predicate, object, text, rationale, status, valid_from_iso, valid_to_iso, confidence, signal, about: [EntityRef], decided_in: Ref|null, stated_by: PersonCard|null }`.
`PulseRisk`: `{ id, category, score, reasons, entity: EntityRef, decision: DecisionCard, owner: PersonCard|null, evidence: [Ref], contradictions: [Ref], last_touched_iso, owner_last_active_iso }`.
`PulseSummary`: `{ active_decisions, risks, critical, coverage, contradictions, drift, ownership_gaps }`.
`WhyPath`: `{ decision: DecisionCard, evidence: [Ref], older: [DecisionCard], newer: [DecisionCard], motivated_by: [Ref], implemented_by: [Ref], cypher: [...] }`.

## 7. Grounded answering rules

- Use only the evidence given. Cite the id of every decision, commit, PR, issue, comment, document or utterance
  used, in square brackets right after the claim. Only ids present in the evidence may be cited; an answer with
  an unknown or missing citation is replaced by the deterministic template answer.
- At most five sentences. Tell changes oldest first ("first … then … now"); the current value is the ACTIVE one.
- For "why" questions give the stated reason and who gave it, where and when; if no reason is recorded, say so.
- Refuse when no decision or evidence is anchored on a resolved entity: "Untangle found nothing in the graph that
  answers that. Closest related: … Person to ask: …" (`refused: true`). Never invent dates, people or reasons.
- Confidence is computed from graph signals only (never from the model): number of independent evidence nodes,
  source authority (ADR 1.0 > PR review 0.8 > PR body 0.7 > commit message 0.6 > issue comment 0.5 > KT 0.5),
  whether the top decision is active, agreement among decisions, entity match strength, and recency; thresholds
  `high >= 0.75`, `medium >= 0.5`, `low` otherwise, refuse below 0.2 or with no anchored evidence.
