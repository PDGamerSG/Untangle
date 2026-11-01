# Untangle verification record

## Answer waits and repository map recovery — 2026-11-02

- Released application commit `795938c` to both public origins. Graph answers now render before the optional
  vector comparison. Waits show an estimated range and elapsed time, allow cancellation, and end with a retry
  message on timeout. Interactive model calls have a 20-second response budget without automatic retries;
  batch extraction retains its existing budget. The configured model was not changed.
- `cd web && pnpm test:production` completed successfully after deployment:
  **https://untangle-code.vercel.app: 10 passed, 0 failed, 0 skipped**;
  **https://untangle.pallabdas.me: 10 passed, 0 failed, 0 skipped**.
  Checks cover landing/icons/mobile navigation, repository selection and restored imports, inventories, real
  cited answers, vector comparison, history and risk exports, feature/commit maps, pagination, Obsidian downloads,
  meetings navigation, and invalid/missing/oversize repository errors. Detailed results and answer timings are
  retained in `web/test-results/production-vercel/results.json` and `production-custom-domain/results.json`.
- Fresh public imports completed through the hosted worker for `jonschlinkert/is-number` (JavaScript, 62 commits),
  `pallets/markupsafe` (Python/C, 869), `spf13/cast` (Go, 289), and `octocat/Hello-World` (minimal repository, 3).
  Each repository's workflows passed on each origin. The minimal repository correctly refused an unsupported
  question rather than inventing evidence. [Worker run](https://github.com/PDGamerSG/Untangle/actions/runs/41347605501).
- Rebuilt source maps at the exact stored repository versions for `usememos/memos` (2,561 import connections),
  `imputnet/helium` (5), `dcondrey/onrecord` (73), and `knadh/listmonk` (55). Both domains returned ready maps.
  Older repositories without a map can now display stored file/commit evidence immediately, label missing
  import connections, and request a refresh from the UI. Invalid optional feature manifests fall back to directory groups.
- Local verification passed **273 backend tests**, **40 browser/API tests**, Ruff, web lint, TypeScript, production
  build, and diff whitespace checks. Regression coverage includes slow comparison, cancellation, response-body
  timeout, import estimates, clone URLs, legacy maps, optional malformed manifests, and retained batch retries.
- An initial live check matched both a cached dashboard and the current inventory. Its selector now targets the
  active repository's region; the complete two-origin rerun passed. Verification avoids submitting old completed
  imports outside their reuse window, so repeated tests do not consume the import quota.
- Scope: public repositories within the hosted size/history limits; static source import analysis supports
  Python/JS/TS. Other languages still have file/commit/directory evidence. These checks do not prove every GitHub
  repository is supported, or that a static impact map predicts runtime failures. Live audio ingestion was not
  repeated in this release; upload/extraction regressions passed locally. Separate landing edits were preserved
  and excluded from this deployment.

## Combined production deployment — 2026-11-02

- The Next.js frontend and FastAPI backend now deploy as two services in **one Vercel project**, `untangle-code`.
  Both https://untangle-code.vercel.app and https://untangle.pallabdas.me point to it. The unused frontend project
  was deleted after both domains passed verification. The old API hostname remains a compatibility alias.
- `pnpm test:production` passed **5 live browser tests on each domain**. It covers real cited answers and vector
  comparison, timeline/risk exports, graph inspection and commit impact, Obsidian downloads, landing/icons/mobile
  navigation, restored import tracking, repository switching and the external repository's inventory/tools.
  Root `AGENTS.md` requires both origins for every production verification.
- **268 backend tests**, **34 contract/browser tests**, lint, TypeScript and production builds passed. The final
  transcript-source label and integer-progress assertions were also exercised in targeted browser regressions.
  Earlier mobile test failures came from matching a hidden cached dashboard as well as the active inventory;
  the selector now targets the active repository inventory explicitly.
- Actual browser form submissions verified a server-side validation error, reuse of a recent completed import,
  a new queued import and recovery after reload. The hosted worker refreshed `PDGamerSG/Untangle` at `d8a7523`
  with 61 commits and 605 decisions. [Worker run](https://github.com/PDGamerSG/Untangle/actions/runs/41343834067).
- A synthetic text upload through the Vercel domain and generated WAV through the custom domain each produced
  one utterance, one extracted decision and one embedded chunk. Audio used batch transcription. Both transcript
  pages rendered; the temporary test repository was then removed from the database.
- Both origins returned the expected CORS origin header. Their downloaded Untangle vaults contained **431 notes
  and 1,559 valid internal links**, with no broken links. Counts are a snapshot, not a permanent corpus guarantee.
- Desktop and phone screenshots were inspected with real data. The README architecture diagram parsed and
  rendered successfully; the top live link uses only the custom domain. App status and transcript-source labels
  describe capabilities without displaying model/provider identifiers; actual repository evidence is preserved.

## Repository onboarding — 2026-11-02

- Durable imports validate GitHub URLs and public accessibility, coalesce duplicate jobs, enforce shared queue
  and daily limits, recover interrupted jobs, and protect worker updates with a lease token.
- The final backend suite passed **268 tests**, including two shared-domain routing checks. The inventory
  refinement also passed all **31 import tests**. Tests use disposable Neo4j, including concurrent admission and
  claims, fixture ingestion, inventory, cited answers, repository isolation, and failure-message redaction.
- Imports reuse the full Git/GitHub analysis pipeline and free embeddings. Optional paid rationale extraction
  is disabled for hosted imports; the existing answer service retains its configured low-cost model.
- A real hosted-worker import of `pallets/itsdangerous` completed: 677 commits, 108 historical/current file paths,
  50 current files, 119 symbols and 692 embedded chunks. Inventory, timeline, Pulse and the feature map loaded;
  a real generated answer had six citations and a vector comparison. The Obsidian export contained 318 notes
  and 675 valid internal links, with no broken links. [Worker run](https://github.com/PDGamerSG/Untangle/actions/runs/41341557536).
- Inventory distinguishes all indexed file paths from current files and counts PR/issue contributors as well
  as commit authors, deduplicated within the repository.

## Feature and commit map — 2026-11-02

- Backend: **234 passed** against disposable Neo4j 2025.09. New checks cover Python/JS/TS import resolution,
  feature definitions, unresolved imports, Git parents, pagination, repository isolation, stale-edge replacement,
  export filenames/link integrity, and HTTP validation/downloads.
- Frontend: **30 checks passed** across the contract/browser suite and targeted regression runs.
  Includes reverse dependency traversal, cycles, unrelated-feature exclusion, absent historical paths, keyboard
  graph selection, zoom/reset, impact paths, commit pagination, and unindexed repositories. A dense eight-feature
  regression verifies labels do not overlap on desktop or phone; dense-file keyboard selection is also covered.
- Ruff, web lint, TypeScript, Next.js/landing production builds, and diff whitespace checks passed. The targeted
  21st component review returned no findings. Desktop and phone screenshots with actual repository data were
  inspected; disconnected components stay bounded, feature labels reserve space, and file/commit names appear
  on hover, focus or selection in dense graphs. The token stylesheet review reports existing palette definitions.
- Live production checks passed for the decision/risk exports, a cited Claude answer with vector comparison,
  and the feature map/commit impact/Obsidian download. The exported vault was checked for valid internal links.
- Existing entity-resolution tests now assert that both exact matches precede partial matches, without assuming
  an ordering between their corpus-dependent full-text scores. Answer behavior was not changed.
- The map is a static estimate at indexed HEAD, not an executed revert. Computed runtime dependencies, HTTP calls,
  unsupported languages and configuration effects are outside its coverage. Merge commits without a parent-specific
  diff are explicitly identified. See [research and usage](FEATURE_MAP.md).

## Decision workbench and Pulse triage — 2026-11-01

- Fetched and pulled `origin/main`; all existing feature branches were already merged. The only pre-existing
  local file was the development launch configuration, now tracked and using the landing-aware `pnpm dev` command.
- Added a searchable Timeline workbench with decision-kind and temporal filters, source/code/person inspection,
  date-aware Ask links, and Markdown evidence exports. A decision appearing in both timeline groups is shown once,
  with historical membership kept separate from its current status.
- Added Pulse category/search/critical filters and filtered risk exports. The dashboard links to both workflows.
  Counts explicitly describe loaded results, and risk scores are shown out of 100 rather than as probabilities.
- Full backend suite against disposable Neo4j 2025.09: **228 passed**, with fake model/embedding adapters.
- Web contract/helper tests: **6 passed**. Browser integration tests: **18 passed**. Checks include downloaded
  source links and filtered content, keyboard selection, temporal-group deduplication, invalid URL dates,
  empty states, API error recovery, existing navigation/Ask/upload flows, and phone overflow after content loads.
- Web lint, Next.js/landing production builds, repository-wide Ruff and `git diff --check`: **passed**.
- Reviewed generated desktop and phone screenshots of Timeline and Pulse, plus the phone dashboard. Existing
  blue-and-white tokens and evidence components are reused. No new UI dependency or API credential is required.
- Search and export operate on the loaded timeline snapshot (up to 100 decisions) or the returned Pulse queue;
  neither is a full repository audit. The new opt-in production tests check live graph/export flows and a real
  cited Claude answer with vector comparison. Their invocation is documented in [Deployment](DEPLOYMENT.md).

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
