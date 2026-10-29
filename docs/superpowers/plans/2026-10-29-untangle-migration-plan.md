# Untangle migration implementation plan

**Goal:** Publish a self-contained Untangle application with consistent package, CLI, environment, web, fixture,
and documentation naming, preserving the existing behavior and required license notices.

**Architecture:** Python/FastAPI and Next.js share the existing Neo4j decision model. Keep API routes, query
semantics, sample payload shapes, and dependency versions stable except for the verified distribution and setup fixes.

**Design:** [Migration design](../specs/2026-10-29-untangle-migration-design.md).

## Constraints

- Use `Untangle`, `untangle`, and `UNTANGLE` for product identifiers.
- Keep Hindi language content and the `knadh/listmonk` demo repository intact.
- Retain original MIT copyright and license notices.
- Use only the Untangle destination remote; do not import the source Git history.
- Publish meaningful commits with actual timestamps, real elapsed gaps, and an immediate push to `main`.
- Finish with 30–40 commits; do not create empty commits to fill the count.
- Preserve the independent landing-page work in the user's separate branch.

## Published sections

1. `c11fd58 chore: initialize Untangle repository`
2. `64d77e6 docs: add Untangle migration design and plan`
3. `1d1fa6a refactor: rename Python package to untangle`
4. `dab307b refactor: rename answer imports to untangle`
5. `8c72e42 refactor: rename graph imports to untangle`
6. `aeefffd refactor: rename ingestion imports to untangle`
7. `f6c5266 refactor: rename handover modules to untangle`
8. `3c12497 refactor: rename evaluation imports to untangle`
9. `491dd43 refactor: rename core services to untangle`
10. `795a2b8 refactor: rename API package to untangle`
11. `129d147 test: update Python imports for untangle`
12. `9104ab9 docs: update Cypher comments for Untangle`
13. `771bd47 refactor: update utility scripts for untangle`
14. `8a495e4 refactor: rename package metadata and cache settings`
15. `10bbb39 chore: rename Untangle deployment configuration`
16. `f3598d4 refactor: rename web API settings to Untangle`
17. `b8941fe refactor: update Untangle web metadata`
18. `e00ce4d refactor: update Untangle web controls`
19. `78c8d9d fix: restore CI import ordering after package rename`
20. `52cba6d docs: update Untangle web and KT guides`
21. `edf91b4 docs: rewrite Untangle README`
22. `e7235a0 build: bundle Cypher queries in Python wheels`
23. `90c1e25 refactor: finish Untangle web identity`
24. `bdb4c08 docs: align Untangle graph and API contracts`
25. `8e36607 refactor: finish Untangle runtime naming`

## Remaining sections

26. `chore: remove stale source planning artifacts`: remove obsolete lineage/planning documents, retain license
    notices, and make the Untangle design and this plan the current migration record.
27. `refactor: normalize Untangle sample labels`: update recorded fixture copy, transcript test naming, sample
    documentation comments, and the remaining public 404 label. Validate fixture schemas and web lint/build.
28. `docs: refresh Untangle demo and evaluation guides`: document sample/live operation, synthetic context, historical
    evaluation limits, reproduction commands, and the evaluation package path. Check CLI commands and local links.
29. `chore: align local setup with CI`: pin local Neo4j to the tested Community image, enforce the Python lockfile in
    CI, and wait for local Neo4j readiness in setup instructions. Check Compose and locked dependency resolution.
30. `docs: record Untangle migration verification`: record the completed acceptance checks and verification evidence,
    then confirm the final push, clean checkout, sole destination remote, and GitHub CI result.

## Verification

Run backend lint and tests, frontend lint and production build, distribution builds and the isolated wheel-loading
check. Tests that need Neo4j may skip locally; confirm the GitHub run with its Neo4j service completes all 190 tests.

```bash
uv lock --check
uv run ruff check src tests
uv run pytest -q
uv run untangle --version
uv build
cd web
pnpm install --frozen-lockfile
pnpm lint
NEXT_PUBLIC_UNTANGLE_SAMPLE=1 pnpm build
```

Check fixture payloads against the backend response models, relative Markdown links, product/source naming in tracked
files, `git diff --check`, and `git remote -v`. Review the built wheel outside the checkout so missing Cypher data cannot
be hidden by source-tree paths. Keep the original copyright and synthetic labels intact.

## Review checkpoint

An independent read-only review of the migration through web identity plus the pending final edits found no actionable
regressions. It checked naming, packaging, CI, fixture structure, documentation accuracy, and original license notices.
The reviewer did not modify the tree or repeat the full test suite.
