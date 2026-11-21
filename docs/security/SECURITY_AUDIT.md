# Security audit — 21 November 2026

This audit covers the FastAPI service, the Next.js application, the static landing page, the Neo4j queries, the
GitHub Actions workflows and the Vercel deployment configuration. Three independent read-only reviews were run
(backend and infrastructure, web and live HTTP surface, functional reliability), followed by fixes and tests in the
same change set. Live checks used only GET and HEAD requests against both public domains; no billed call, upload or
import was made during the audit.

Status values: **Fixed** (changed and covered by a test), **Mitigated** (risk reduced, residual risk stated),
**Accepted** (deliberate, with the reason), **Open** (planned in [the roadmap](../ROADMAP.md)).

## Summary

Before this change the application had no accounts. Every endpoint, including the billed answer and transcription
endpoints, could be called anonymously; anyone could add or overwrite handover calls on any repository; pages sent
no security headers; the API schema and interactive docs were public; and the public health endpoint returned the
database host and the model identifier.

After this change every data endpoint requires a signed-in session, billed and write actions have per-user limits,
uploads have an owner, pages and API responses carry a full set of security headers, and error and health responses
no longer reveal internal details. All findings rated high or medium are fixed. The remaining open items are listed
at the end with their owners in the roadmap.

## Findings

| ID | Severity | Area | Finding | Status | Change and evidence |
| --- | --- | --- | --- | --- | --- |
| S1 | High | API | No authentication: `/ask`, `/kt/ingest` and imports could be called by anyone, spending model and transcription credits. | Fixed | `src/untangle/api/auth.py` applies `enforce_access` to every route; only `/health` and `/auth/*` are public. `tests/test_auth.py::test_protected_routes_need_a_session`. |
| S2 | High | API | No rate limits on billed or write actions; one client could exhaust the shared import queue. | Fixed | `src/untangle/auth/limits.py`: 40 questions/hour, 10 uploads/day, 5 imports/day per user, stored in Neo4j so all serverless instances share the count. `test_members_have_question_quotas`. |
| S3 | High | Handover calls | Re-uploading a call with the same title and date replaced someone else's call and its decisions. | Fixed | `before_write` hook in `kt/pipeline.py`; the API refuses (409) when another user owns the meeting. Owner stored as `Meeting.uploaded_by`. |
| S4 | High | Handover calls | Uploads to any `repo` string created fake repositories visible to everyone. | Fixed | `/kt/ingest` normalises the name and requires an imported repository (404 otherwise). |
| S5 | Medium | Web | No CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy or COOP; pages could be framed (clickjacking). | Fixed | `web/next.config.ts` `headers()`; a stricter `script-src 'self'` policy for the landing page. `site.spec.ts` "pages and the landing page send security headers". |
| S6 | Medium | API | API responses had no security headers or cache policy. | Fixed | `src/untangle/api/security.py`: `default-src 'none'`, `frame-ancestors 'none'`, HSTS, nosniff, `Cache-Control: no-store`, CORP and COOP. |
| S7 | Medium | API | `/api/docs`, `/api/redoc` and `/api/openapi.json` were public and loaded unpinned third-party scripts on the app's origin. | Fixed | Docs are off unless `UNTANGLE_API_DOCS=1`. `test_openapi_lists_every_contract_endpoint`, `test_deployment.py`. |
| S8 | Medium | API | Public `/health` returned the Aura host, database version and edition, model id and speech model. | Fixed | `src/untangle/api/health.py` returns readiness only. `test_public_health_hides_hosts_models_and_errors`. |
| S9 | Medium | API | Error responses included exception text, Neo4j messages and codes, and temporary paths. | Fixed | Generic messages with a request id; details stay in server logs. `test_unexpected_errors_do_not_reveal_internals`. |
| S10 | Medium | Dependencies | Next.js 16.4.3 had seven moderate advisories, one possibly reachable with Cache Components. | Fixed | Upgraded to 16.4.5; `pnpm audit --prod` reports no known vulnerabilities. |
| S11 | Medium | Ingestion | YAML aliases in a repository's config could expand to millions of keys and stall the worker. | Fixed | `_ConfigLoader` refuses aliases. `test_yaml_config_keeps_values_as_written_and_refuses_aliases`. |
| S12 | Medium | CI/CD | Production database secrets were set for the whole import job, readable by third-party actions and package installs; actions used moving tags. | Fixed | Secrets only on the queue check and worker steps; every action pinned to a commit SHA; CI token `contents: read`. |
| S13 | Medium | CI/CD | The worker polled the public imports endpoint, which now needs a session. | Fixed | The queue check reads the database over its HTTPS query endpoint and falls back to running the worker. |
| S14 | Medium | Development | A plain `pytest` with the production `.env` wrote to, and pruned people in, the production graph. | Fixed | `tests/conftest.py` skips database tests unless `NEO4J_URI` is local (override: `UNTANGLE_TEST_REMOTE_DB=1`). |
| S15 | Medium | Deployment | The CLI deploy could upload media, design files and research notes. | Fixed | `.vercelignore` excludes them. |
| S16 | Low | Web | `/ask?question=` asked automatically on page load, so a link from another site could spend a visitor's quota. | Fixed | A fresh load from another site only fills in the question; in-app links still ask at once. `site.spec.ts` "a question linked from another site…". |
| S17 | Low | Web | An uploaded transcript could set `audio_uri` to any host, making every viewer's browser contact it. | Fixed | The API drops recording links from uploaded transcripts; the page only plays same-site audio; CSP `media-src 'self'`. |
| S18 | Low | Web | Evidence links were not restricted by scheme; `//host` became an off-site link. | Fixed | `safeLink`/`externalHref` in `web/src/lib/api.ts` allow only http(s) URLs and single-slash paths. |
| S19 | Low | API | A caller-supplied `x-request-id` was echoed into headers and logs. | Fixed | Only `[A-Za-z0-9._-]{1,128}` is echoed. `test_untrusted_request_ids_are_replaced`. |
| S20 | Low | API | Inputs without length limits (`repo`, `at`, `title`, `language`); all-digit dates overflowed the driver. | Fixed | Bounded fields; dates limited to 1970–2200. `test_dates_are_bounded`. |
| S21 | Low | API | CORS allowed credentials with any method and header. | Fixed | Methods `GET, POST, DELETE`; headers `Accept, Content-Type, X-Request-Id`; origins from configuration. |
| S22 | Low | Dependencies | `opentelemetry-api` 1.45.1 (regex slowdown advisory). | Fixed | Locked at 1.45.2. |
| S23 | Info | Web | No `robots.txt` or `security.txt`. | Fixed | `web/public/robots.txt`, `web/public/.well-known/security.txt`, `SECURITY.md`. |
| S24 | Info | Web | `x-powered-by` header. | Fixed | `poweredByHeader: false`. |

## Account and session design

- **Passwords:** Argon2id via `argon2-cffi` (RFC 9106 low-memory profile), 10–128 characters, common passwords and
  passwords containing the email name refused. Hashes are upgraded on sign-in when parameters change. Unknown emails
  are verified against a dummy hash so sign-in timing does not reveal which addresses have accounts.
- **Sessions:** 32 random bytes in an HttpOnly, SameSite=Lax cookie, `Secure` with the `__Host-` prefix on HTTPS.
  Only the SHA-256 of the token is stored, so a database read cannot be replayed. Sessions last seven days; sign-out
  and account deletion revoke them. Each instance caches a resolved session for at most 20 seconds.
- **Cross-site request forgery:** SameSite=Lax plus an `Origin`/`Sec-Fetch-Site` check on every POST and DELETE.
- **Brute force:** 5 wrong passwords per account per 15 minutes locks that account's sign-in for the rest of the
  window. Network-wide limits (60 sign-in attempts per 15 minutes, 30 sign-ups per hour) are generous because a
  venue, office or campus shares one address.
- **Roles:** `member` and `admin` (`UNTANGLE_ADMIN_EMAILS`). Administrators have no quotas and may delete any
  handover call. Members can delete only the calls they uploaded.
- **Open redirects:** the `next` parameter after sign-in accepts only same-site paths.

## Verified clean

- Every Cypher query is parameterised; full-text search terms are sanitised to plain tokens.
- Repository import accepts only `github.com/owner/name`, never executes repository code, and clones without
  checking out files. No shell is used.
- No `dangerouslySetInnerHTML`, `innerHTML` or `eval` in the application; repository text renders as React text.
- No secrets in the repository or its history; no `NEXT_PUBLIC_*` secrets; no published source maps.
- The Obsidian export has no path traversal.

## Accepted and open items

| Item | Status | Reason or plan |
| --- | --- | --- |
| `script-src 'unsafe-inline'` on application pages | Accepted | Next.js inlines its hydration payload; nonces would force every page to render per request. No other origin is allowed and there is no HTML injection sink. Revisit with nonce-based CSP. |
| Static assets send `Access-Control-Allow-Origin: *` | Accepted | Vercel default for public static files; they contain no user data. |
| Handover statements can name real contributors as speakers | Mitigated | Calls now have an accountable uploader, uploads need consent confirmation, and owners or admins can delete them. Per-team visibility is planned. |
| Email verification and password reset | Open | Needs an email provider. |
| Sign in with GitHub, organisations and private repositories | Open | Needs a GitHub OAuth app and a GitHub App installation model. |
| Synthetic sample transcript is cited without a label in evidence chains | Open | Label synthetic sources wherever they are cited. |
| Prompt injection from repository text into answers | Mitigated | Answers may cite only retrieved evidence, numbers must appear in cited sources, and refusals are deterministic. Entailment checks are planned. |

## How to re-run the checks

```bash
uv run ruff check src tests
NEO4J_URI=bolt://localhost:7687 uv run pytest -q
cd web && pnpm lint && pnpm build && pnpm test && pnpm test:e2e
pnpm audit --prod
uvx pip-audit
```

After deploying, `cd web && pnpm test:production` signs in with a throwaway account on both public domains, checks
access control and headers, and deletes the account afterwards.
