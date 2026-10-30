# Untangle verification record

## Production integration checks — 2026-10-30

- Frontend landing branch is merged into `main` at `c556460`.
- Full backend suite against a disposable local Neo4j: **205 passed**.
- Repository-wide Ruff and `git diff --check`: **passed**.
- Web API contracts: **3 passed**. Browser integration suite: **9 passed**, including decision breadcrumbs,
  missing-page recovery after moving Ask to `/ask`, refusal, timeline, Pulse, uploads, and mobile overflow checks.
- Real `PDGamerSG/Untangle` ingestion into local Neo4j with FastEmbed: **35 commits, 537 decisions, 117 embedded
  chunks, 3,053 nodes, 5,945 relationships**. This verifies the ingestion path; Aura was also initialized with the
  same graph counts.
- The historical selector regression is covered by both offline and Neo4j-backed tests: a file-wide query such as
  `why do we use neo4j in pyproject.toml?` stays on the named dependency even when another dependency is in force.
- A real Claude `claude-haiku-5-5` completion passed the answer validator with `why.llm.used=true`.
- The configured Sarvam credential was tested against `POST /speech-to-text` with a short generated WAV and the
  service returned `403 invalid_api_key_error`; a replacement Sarvam key is required for live audio ingestion.
- Public deployments respond at the URLs below. The production API remains degraded until the corrected Sarvam key
  is installed and the API is redeployed.

See [Deployment](DEPLOYMENT.md) for the production environment and remaining live checks.

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
