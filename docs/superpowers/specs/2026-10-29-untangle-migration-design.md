# Untangle Migration Design

**Date:** 2026-10-29

## Goal

Turn the application snapshot into an independent project named Untangle, with no source-repository remote or source-specific product branding, while preserving the working graph, API, CLI, web application, fixtures, and tests.

## Context

The destination repository is `PDGamerSG/Untangle`. The migration begins from an application snapshot without its Git history. The README reference repository supplies the documentation shape: a strong hero, a short value explanation, a quick start, a workflow/architecture explanation, honest limitations, development notes, and license information.

## Decisions

- The destination starts from a tracked-file snapshot; the source `.git` directory is never copied.
- The only Git remote in the finished checkout is `https://github.com/PDGamerSG/Untangle.git`.
- Product identifiers use `untangle`/`Untangle`/`UNTANGLE` across Python modules, CLI commands, package metadata, environment variables, API metadata, UI copy, fixtures, and documentation.
- `kyunki` and other Hindi words remain unchanged because they are language content, not product identifiers.
- `knadh/listmonk` remains in sample fixtures because it is the repository analyzed by the demo; it is data, not a source dependency.
- Stale source-specific planning and lineage documents are removed. Product links and remotes point to Untangle,
  while original copyright and license notices are retained.
- No new runtime dependency or feature is introduced; the migration preserves behavior.

## Architecture and Boundaries

The existing boundaries remain intact:

- `src/untangle/` remains the Python package containing CLI, configuration, graph, ingestion, answering, KT, evaluation, and API modules.
- `cypher/` remains the numbered query source of truth.
- `web/` remains the Next.js client and sample-mode fixture surface.
- `tests/` remains the backend contract and regression suite.
- Root docs describe product behavior and setup; `web/README.md` documents the client independently.

## Validation

- Search the tracked tree for product/source identifiers and source Git URLs.
- Run `uv run ruff check src tests` and `uv run pytest`.
- Run `cd web && pnpm lint && pnpm build`.
- Run `git diff --check` and confirm the remote list contains only the Untangle destination.

## Commit cadence

The migration is intentionally split into small commits so each boundary can be reviewed independently. The accepted range is 30–40 meaningful commits. Commit timestamps record the actual creation time. New sections
use real gaps of about 20–25 minutes, with longer gaps when the work or an interruption takes longer. Push each
commit to `main` immediately after creation; never delay its push or fabricate its timestamp.
