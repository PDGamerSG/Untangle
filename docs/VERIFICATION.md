# Untangle verification record

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
