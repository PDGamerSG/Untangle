# Repository loading and map completeness — 2 November 2026

Status: implemented and verified in the local checkout. These changes have not been deployed or pushed to the scheduled worker. The live-domain results below describe the existing production release, not the local fixes.

## Cause and changes

The dashboard's shared resource cache had a reproducible race: a response could populate the cache between a panel's render and its effect. The effect then skipped fetching without updating that panel's state, leaving its skeleton visible indefinitely. A React regression test reproduced the stuck state before the fix. Cached responses now reach every subscriber; completed imports also invalidate mounted repository data.

The map had independent limits of 2,000 scanned source files, 2,000 returned paths, 12,000 returned imports, 60 inferred directories and 65 drawn files. Eligible source files are now read in batches of 250; all inferred directories are retained. The API pages file paths, feature groups and imports independently, and the browser assembles and checks the complete snapshot before showing it. Downloads also assemble the full map. An All files view includes isolated and historical paths. Large maps use a deterministic layout that fits all nodes initially and supports zoom and pan.

A stress test also reproduced database memory exhaustion when the combined query retained page arrays through later expansions. Independent bounded reads resolved it. Snapshot identity and counts are checked again after reading to detect concurrent refreshes. A local complete-map read with 2,101 files and 12,600 connections took 0.691 seconds after the fix.

Inventory loading now shows an approximate wait range and elapsed time. Map loading reports fetched versus total records. Import estimates include the number of repositories ahead in the queue. Worker progress includes mapping and verification, and an import cannot report completion until persisted file, feature, entry-point and import counts match its source analysis. Each scheduled run processes one job to avoid starting another near the workflow time limit. Queue expiry allows five hours for a full queue; a running job's missing-heartbeat timeout remains three minutes.

## Local verification

- `uv run ruff check src tests`: passed.
- `uv run pytest -q`, with a disposable local Neo4j: 278 passed, no skips (17.72 seconds).
- Additional queue-order assertions: 2 focused tests passed.
- `pnpm lint`: passed.
- `pnpm build`: passed.
- `pnpm exec playwright test tests/api.test.ts tests/site.spec.ts --workers=2`: 47 passed (41.1 seconds).
- Regression coverage includes the cache race, refreshing mounted inventory after import, queued estimates, pagination and missing pages, changing snapshots, missing persisted connections preventing completion, 2,101 file paths, 12,600 edges, complete ZIP export, 85 directory groups, every node fitting the initial large-map viewport, and responsive navigation.

## Fresh public-repository imports

These ran through the updated worker into the disposable local database, with real Git/GitHub data and the free local embedding backend. They did not modify the production graph. Times exclude scheduled-worker queue delays and are observations, not guarantees.

| Repository | Result | Time | Current files | All indexed paths | Commits | Features | Static imports |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| jonschlinkert/is-number | Complete | 32.38 s | 15 | 33 | 62 | 2 | 1 |
| pallets/markupsafe | Complete | 128.71 s | 47 | 94 | 869 | 9 | 8 |
| spf13/cast | Complete | 89.96 s | 39 | 50 | 289 | 5 | 0 |

For each import, inventory totals matched the assembled map, current-file counts matched source coverage, and stored import counts matched analysis output.

## Existing production baseline

`cd web && pnpm test:production` ran against both required origins before local implementation was complete:

- https://untangle-code.vercel.app: 10 passed, 0 failed (1.2 minutes).
- https://untangle.pallabdas.me: 10 passed, 0 failed (1.0 minute).

Each origin covered landing, icons, mobile navigation, repository onboarding/selection and restored status, dashboard inventory, cited answers, vector comparison, history, Pulse, feature/commit maps and downloads. Independent repository checks covered is-number, markupsafe, cast and Hello-World. Additional flows covered Untangle and itsdangerous, legacy maps, and invalid/missing/oversize import errors.

Direct baseline reads for spf13/cast returned HTTP 200 on both origins: inventory 0.99 seconds on each, map 0.94 seconds on the Vercel origin and 0.92 seconds on the custom domain. Its production import was already complete. The original browser stall was not reproduced live during these checks; the cache race was reproduced deterministically in the regression test.

## Scope and remaining limits

This does not establish that every possible repository can be fully understood. Hosted admission still accepts public GitHub repositories up to 100,000 KB, with at most 1,000 recent commits, 50 pull requests and 100 issue entries. Source files may be excluded from language analysis by size/generated-file rules, while their file nodes remain mapped. Static import connections support Python and JS/TS; Go files are present but Go import relationships are not extracted. Runtime and cross-service connections remain outside this analysis. Source parse failures and unresolved imports are reported.

Previously indexed repositories that hit the old source-file cap need reindexing to discover skipped connections. Releasing these changes requires deploying the API/web application and updating the scheduled worker's code, then rerunning the production suite against both origins.
