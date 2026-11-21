# Untangle — ArgosX remediation log

**Application scanned:** https://untangle.pallabdas.me (same build also at https://untangle-code.vercel.app)
**Baseline scan:** `<date and time>` — report file: `<filename>` · **Final scan:** `<date and time>` — report file: `<filename>`

Fill the "ArgosX finding" columns from the two reports. Do not list a finding that ArgosX did not report; our own
audit findings are kept in the second table so the two sources stay separate.

## 1. Findings reported by ArgosX

| # | ArgosX finding (as reported) | Severity | Baseline | Final | What we did | Commit | Status and reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | Found | | | | Fixed / Accepted / Open: why |
| 2 | | | | | | | |
| 3 | | | | | | | |

**Totals:** found `__` at baseline · fixed `__` · accepted `__` (with reasons) · open `__` (with plan).

## 2. Changes made between the scans (from our own audit)

These were found by our internal review on 21 November and are deployed in the release that the final scan
covers. Map each ArgosX finding above to one of these where it applies. Full detail:
[docs/security/SECURITY_AUDIT.md](../security/SECURITY_AUDIT.md).

| Area | Before (baseline build) | After (final build) | Commit |
| --- | --- | --- | --- |
| Authentication | No accounts; every endpoint public, including billed answer and transcription endpoints | Accounts with Argon2id passwords, HttpOnly `__Host-` SameSite session cookies, sign-out, account deletion; all data endpoints need a session | `5c8316d`, `0a5c16a` |
| Abuse and cost | No rate limits | Per-user limits (40 questions/hour, 10 uploads/day, 5 imports/day), sign-in throttling and lockout, sign-up limit per network | `5c8316d` |
| Security headers | No CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy or COOP | All set on pages and API; `frame-ancestors 'none'`; API `default-src 'none'`; `Cache-Control: no-store` on API | `8b657bd`, `5c8316d` |
| Information disclosure | Public `/api/docs`, `/api/openapi.json`; health endpoint showed database host, version and model id; errors showed exception text | Docs and schema not published; health shows readiness only; generic errors with a request id | `5c8316d` |
| Data integrity | Anyone could create repositories or overwrite another person's handover call | Uploads need an imported repository, record their owner; only the owner or an admin can replace or delete | `5c8316d` |
| Cross-site request forgery | Not applicable without accounts | SameSite cookies plus an origin check on every POST and DELETE | `5c8316d` |
| Client-side safety | Third-party audio URLs played; links not restricted by scheme; links from other sites ran billed questions | Same-site audio only; http(s) links only; cross-site links only fill in the question | `8b657bd` |
| Dependencies | Next.js 16.4.3 (7 moderate advisories), opentelemetry-api 1.45.1 | Next.js 16.4.5, opentelemetry-api 1.45.2; `pnpm audit --prod` clean | `f9ac952` |
| Ingestion | YAML aliases could stall the worker | Aliases refused; values kept as written | `ff68885` |
| Pipeline | Database secrets visible to every job step; actions on moving tags | Secrets on two steps only; actions pinned to commit SHAs; CI token read-only | `dfdc901` |
| Disclosure policy | No `security.txt` | `/.well-known/security.txt` and `SECURITY.md` | `8b657bd`, `e12bccd` |

## 3. What remains and why

| Item | Why it is acceptable now | Plan |
| --- | --- | --- |
| `script-src 'unsafe-inline'` on application pages | Next.js inlines its hydration data; nonces would force every page to render per request. No other script origin is allowed and the app has no HTML injection sink. The landing page already uses `script-src 'self'`. | Nonce-based CSP |
| `Access-Control-Allow-Origin: *` on static files | Vercel default for public static assets, which hold no user data | None needed |
| No email verification or password reset | Requires an email provider; accounts hold no payment data | Next release |
| `<anything else ArgosX reports that we choose not to fix>` | `<reason>` | `<plan>` |
