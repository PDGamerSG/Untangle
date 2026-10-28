# Untangle verification

This repository was checked after the package, configuration, web, and documentation migration.

| Check | Result |
|---|---|
| `uv run ruff check src tests` | passed |
| `uv run pytest -q` | 162 passed, 28 skipped without Neo4j |
| `cd web && pnpm lint` | passed |
| `cd web && pnpm build` | passed |
| `uv run untangle --version` | `untangle 0.1.0` |
| `git diff --check` | passed |
| `git remote -v` | only `https://github.com/PDGamerSG/Untangle.git` |

The skipped tests are the optional Neo4j integration cases. Unit, contract, fixture, API, ingestion, handover, evaluation, and Pulse tests run without a graph service.

The tracked tree contains no legacy package directory, source lineage file, dependency checkout, `node_modules`, build output, or Python cache artifacts.
