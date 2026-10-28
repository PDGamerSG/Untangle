# Untangle Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the HackFront application snapshot into a self-contained, fully branded Untangle project and publish a README that follows the Make-the-readme reference structure.

**Architecture:** Preserve the existing Python/FastAPI/Neo4j and Next.js boundaries. Rename the Python package and public configuration first, then update web consumers, fixtures, docs, and repository metadata. Each numbered task is a small, reviewable commit; the sequence targets 32 meaningful commits.

**Tech Stack:** Python 3.12, uv, FastAPI, Neo4j, Cypher, pytest, Ruff, Next.js, React, TypeScript, pnpm.

**Spec:** `docs/superpowers/specs/2026-10-29-untangle-migration-design.md`

## Global Constraints

- Preserve existing behavior, API route paths, graph schema, sample fixtures, and test intent.
- Product identifiers use `Untangle`, `untangle`, and `UNTANGLE` consistently.
- Hindi language tokens such as `kyunki` remain language content.
- The sample repository `knadh/listmonk` remains fixture data.
- The finished checkout has only the Untangle Git remote.
- Do not add runtime dependencies.
- Every task ends with a focused check and a commit.

## Commit Map

1. `chore: establish Untangle repository baseline`
2. `docs: add Untangle migration design`
3. `docs: add Untangle implementation plan`
4. `refactor: rename Python package to untangle`
5. `refactor: rename CLI commands to untangle`
6. `refactor: rename configuration and cache variables`
7. `refactor: rename API and logging identifiers`
8. `refactor: rename answer and evaluation imports`
9. `refactor: rename ingestion and graph imports`
10. `refactor: rename KT package imports and transcript helpers`
11. `refactor: rename test imports and fixtures`
12. `refactor: rename Cypher and service documentation identifiers`
13. `chore: rename container and CI configuration`
14. `refactor: rename web API environment variables`
15. `refactor: rename web branding and navigation`
16. `refactor: rename web sample-mode storage and copy`
17. `refactor: rename web documentation and package metadata`
18. `docs: rewrite Untangle product README hero`
19. `docs: document Untangle quick start`
20. `docs: document Untangle architecture and workflow`
21. `docs: document Untangle limitations and development`
22. `docs: update web README for Untangle`
23. `docs: rewrite data and demo documentation`
24. `docs: remove source lineage metadata`
25. `docs: rename existing planning artifacts`
26. `test: update API and CLI expectations for Untangle`
27. `test: update integration fixture expectations`
28. `chore: remove source repository references`
29. `chore: normalize Untangle naming and URLs`
30. `test: run backend verification and fix regressions`
31. `test: run frontend verification and fix regressions`
32. `chore: perform final independence audit`

## Task Details

### Task 1: Establish the repository baseline

Copy tracked source files without `.git`, initialize Git on `main`, and set only the Untangle destination remote. Do not copy source history or source remotes. Check with `git remote -v` and `git status --short`.

### Task 2: Add migration design

Commit `docs/superpowers/specs/2026-10-29-untangle-migration-design.md` after checking for placeholders and contradictions.

### Task 3: Add implementation plan

Commit this plan after checking that every commit has a scoped deliverable and validation command.

### Task 4–12: Rename backend boundaries

Use `src/untangle` as the Python package, replace product identifiers in imports, module docstrings, loggers, CLI help, package metadata, public script entry points, configuration keys, cache directories, API metadata, tests, and data instructions. Keep language tokens and `knadh/listmonk` fixture identifiers unchanged. Run targeted import/collection checks after each boundary.

### Task 13: Rename container and CI configuration

Update Neo4j container names, volume names, CI environment values, commands, and sample-mode variable names. Keep service versions and ports unchanged.

### Task 14–17: Rename web configuration and branding

Update API/sample environment variables, client API errors, local storage keys, application metadata, navigation, logo, accessible labels, sample banner, README, and package scripts. Keep route paths and fixture payload shapes stable.

### Task 18–24: Rewrite documentation

Rewrite the root README in the reference structure with truthful Untangle-specific content. Document setup, data flow, architecture, limitations, development commands, and license. Update web/data/demo docs and remove source-specific lineage metadata.

### Task 25: Normalize existing planning artifacts

Remove stale planning/spec artifacts that describe the source project. Keep the new Untangle design and plan as the authoritative docs.

### Task 26–27: Update tests

Update import paths, CLI names, environment variable assertions, API title/header assertions, sample-mode expectations, and fixture comments. Preserve test coverage and semantics.

### Task 28–29: Independence and naming audits

Use `rg` over tracked files to find source project names, source repository URLs, old environment keys, old package paths, and stale GitHub links. Fix only genuine product/repository references; leave runtime GitHub API URLs and sample repository URLs intact.

### Task 30–31: Full verification

Run:

```bash
uv run ruff check src tests
uv run pytest
cd web && pnpm lint && pnpm build
```

Fix regressions in focused commits if needed, then rerun the failed check.

### Task 32: Final independence audit

Run `git diff --check`, `git status --short`, `git remote -v`, `git log --oneline -32`, and targeted `rg` searches. Confirm the checkout is self-contained, all required docs are present, and the final commit is clean.

## Review checkpoints

After backend renames, the import graph and Python test collection are checked. After the web rename, the TypeScript build and sample-mode fixtures are checked. The final two commits are reserved for full verification and a clean-tree independence audit.

## Acceptance checks

- `git remote -v` lists only the Untangle destination.
- No tracked product-facing file uses the old product name or old package path.
- `uv run pytest`, `uv run ruff check src tests`, `pnpm lint`, and `pnpm build` complete successfully.
- README setup commands and environment variables match the renamed package and web client.
