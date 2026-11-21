# Security, accounts and agent-memory release — 21 November 2026

Deployment `dpl_787ug3EKVoRe25D489fgqA613YAG` (commit `b0f4a4c`), validated on its deployment URL, then promoted to
both public domains at about 16:27 IST.

## Live suite (`cd web && pnpm test:production`)

| Origin | Result | Time |
| --- | --- | --- |
| https://untangle-code.vercel.app | 11 passed, 0 failed | 2.2 minutes |
| https://untangle.pallabdas.me | 11 passed, 0 failed | 1.9 minutes |

Each origin covered sign-in with a throwaway account, dashboard and decision workbench with exports, cited answers
and the vector comparison, feature map and Obsidian download, landing page, icons and phone navigation, imported
repository restore and inventory, four independent repositories, legacy maps and import errors, and access control
(signed-out redirect, 401 on data endpoints, 403 on cross-site writes, health without hosts or model names,
security headers, private API docs).

The final cleanup request of this run hit a closed connection, so one `live-check-…@example.com` account remained;
the script now retries cleanup on a fresh connection (commit `9571e6e`).

An earlier run of the same suite found two problems, both fixed before this run: five sign-ups per hour per network
was too low for a shared network (now 30), and the signed-out checks reused the suite's own session (test setup).

## Checks on the release

- Duplicate sign-up with the same email in different case: first 201, second 409 (both test accounts deleted).
- `POST /api/mcp` with a session lists the eight agent tools; without a token or session it answers 401.
- Both domains serve `/sitemap.xml`, `/og.png` and a canonical link on the landing page.
- Anonymous `GET /api/repos`, `/api/pulse`, `/api/repository-imports` answer 401 on all three hostnames.

## Local checks

- `uv run ruff check src tests`: passed. `uv run pytest -q` with a disposable local Neo4j: 309 passed.
- `pnpm lint`, `pnpm build`: passed. API-client and browser suites: 55 passed, including axe-core WCAG A/AA checks
  on `/`, `/login` and `/signup`.
- Official MCP Python client against a local server with an imported public repository: protocol `2025-11-25`, all
  eight tools answered, `remember_decision` stored a superseding agent note shown on the Agents page.

## ArgosX

Free deep scans of https://untangle.pallabdas.me: baseline 94 (16:10 IST), re-tests 96.4 (16:44, 17:03), final **99**
(17:41) with accessibility 100. Four landing-page releases followed the findings (`2976760`, `3f6a32c`, `403bff4`,
`53448b4`); browser tests now run axe-core at load and at every scroll position. Details and the reasons for the
three open findings are in [the remediation log](../submission/ARGOSX_REMEDIATION_LOG.md); the four report PDFs are
in `docs/submission/argosx/`.
