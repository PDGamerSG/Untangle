# Untangle verification record

## Production integration checks — 2026-10-30

- Frontend landing branch is merged into `main` at `c556460`.
- Full backend suite against a disposable Neo4j: **211 passed**, also confirmed in
  [GitHub CI](https://github.com/PDGamerSG/Untangle/actions/runs/41014902804).
- Repository-wide Ruff and `git diff --check`: **passed**.
- Web API contracts: **3 passed**. Browser integration suite: **10 passed**, including repository defaults and
  persistence, decision breadcrumbs, missing-page recovery, refusal, timeline, Pulse, uploads, and mobile layout.
  The mobile regression includes a long repository name, which previously widened the compact selector beyond
  the viewport on Meetings, Timeline, and Pulse. The shared selector now shrinks within its container.
- Next.js and landing production builds and web lint: **passed**.
- Real `PDGamerSG/Untangle` ingestion into Aura with FastEmbed at `0ad859c`: **37 commits, 537 decisions, 120
  embedded chunks, 3,076 nodes, 5,983 relationships**. These are a snapshot; subsequent ingestion updates them.
- The historical selector regression is covered by both offline and Neo4j-backed tests: a file-wide query such as
  `why do we use neo4j in pyproject.toml?` stays on the named dependency even when another dependency is in force.
- A real Claude `claude-haiku-5-5` completion passed the answer validator with `why.llm.used=true`.
- Unmocked production browser checks passed for the landing page, default repository, cited Claude answer,
  graph/vector comparison, evidence navigation, historical answer, unsupported-question refusal, timeline, and Pulse.
  Historical answers are checked for the correct subject and date; `llm.used=false` is allowed when the documented
  citation validator falls back to a deterministic answer. A separate current-answer check requires real Claude use.
- The configured Sarvam credential passed live model discovery, short real-time transcription, batch diarised
  transcription, language identification, and Hindi-to-English translation with a generated WAV. Short recordings
  use the batch endpoint first because Sarvam's real-time endpoint does not support diarisation; the app falls back
  to non-diarised real-time transcription when batch access is unavailable.
- Both text and generated-WAV uploads passed through the public `/api/kt/ingest` endpoint in the browser. Each
  returned one utterance, one Claude-extracted decision (`llm.used=true`, no extraction errors), and one embedded
  chunk. Audio reported `source=sarvam-batch`; the saved transcript page rendered its extracted decisions from Neo4j.
  These checks use synthetic data in a temporary repository, never a real handover.
- Public deployments respond at https://untangle-code.vercel.app and https://untangle-code-api.vercel.app.
  API health reports Neo4j Aura, Claude, FastEmbed, and Sarvam as available; the live calls above verify the services
  beyond their configuration flags.

See [Deployment](DEPLOYMENT.md) for the production environment, API surface, and verification commands. Browser
uploads are limited to 4 MB; use the CLI for longer recordings. Re-ingest after code changes to refresh the graph.

## Earlier migration verification

This record captures the checks run during the Untangle migration and setup refresh. It is a snapshot of the repository state, not a promise that later dependency or fixture changes will produce identical timings.

## Repository and identity

- Destination: `PDGamerSG/Untangle`
- Branch checked: `main`
- Destination is an independent repository with no fork parent.
- Tracked source-name scan passed. Remaining historical names are intentional public fixture references (`knadh/listmonk`), GitHub API URLs, and Hindi language terms in sample data.
- The original Team Vulcan copyright notice is retained; Untangle contributor attribution is included alongside it.

## Automated checks

| Area | Result |
|---|---|
| Backend test suite | 162 passed, 28 skipped locally |
| GitHub CI integration run | 190 passed with Neo4j, including constraints, indexes, and wheel Cypher-loading smoke tests |
| Web lint | Passed |
| Next.js sample-mode production build | Passed |
| Python sdist contents | All 55 Cypher files included |
| Python wheel contents | All 55 Cypher files included |
| `UNTANGLE_CYPHER_DIR` override | Passed |
| Bundled-query fallback | Passed |
| `docker compose config --quiet` | Passed |
| `uv lock --check` | Passed |
| `git diff --check` | Passed |

The CI run exercised the Neo4j-backed path. The local skipped tests are the checks that require the optional external service configuration.

## Runtime smoke checks

The bundled query fallback and the explicit `UNTANGLE_CYPHER_DIR` override both loaded the expected Cypher files outside the source checkout. Sample mode served the recorded Untangle fixtures without requiring Neo4j or an API key.

An independent read-only review found no actionable regressions in the migration. The checked-in demo and evaluation guides describe synthetic transcript labels and the historical evaluation snapshot so those fixtures are not presented as live ownership evidence or a freshly rerun benchmark.
