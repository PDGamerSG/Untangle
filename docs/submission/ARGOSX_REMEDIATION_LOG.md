# Untangle — ArgosX remediation log

**Application scanned:** https://untangle.pallabdas.me (same build also at https://untangle-code.vercel.app)
**Baseline scan:** 21 November 2026, about 16:10 IST, free deep scan (public surface, 3 pages crawled: `/`, `/login`,
`/signup`) — report https://getargosx.com/r/ipoczozg, **VibeScore 94/100** (Security 100, Performance 100, UX 88,
Accessibility 84), 6 findings · **Final scan:** `<date and time>` — report `<link>`, VibeScore `<score>`

**Context.** The security release (accounts, access control, rate limits, security headers, private API docs, safe
errors) went live at 15:33 IST, shortly before the baseline scan, so ArgosX found no security issue on the public
surface. Section 2 records what that release changed compared with the earlier build, from our own audit.

Fill the "ArgosX finding" columns from the two reports. Do not list a finding that ArgosX did not report; our own
audit findings are kept in the second table so the two sources stay separate.

## 1. Findings reported by ArgosX

| # | ArgosX finding (as reported) | Severity | Baseline | Final | What we did | Commit | Status and reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c7b886 | A11y: elements must meet minimum colour contrast (27 nodes, axe impact serious) | Medium | Found | `<final>` | Unspoken transcript lines on the landing page were dimmed with opacity (1.2:1); now dimmed with colour at 4.5:1 or more. Hero footnote raised to 74% white. Muted text token darkened from `#66758f` to `#5a6982` (5.2:1). | `2976760` | Fixed. A browser test runs axe-core on `/`, `/login`, `/signup` and fails on any serious violation. |
| f95aed | A11y: scrollable region must have keyboard access (1 node) | Medium | Found | `<final>` | The quick-start `pre` block is now focusable (`tabindex="0"`) with a region label. | `2976760` | Fixed. |
| e1f851 | Missing Open Graph tag: image | Low | Found | `<final>` | 1200×630 preview image, `og:image` with size and alt text, Twitter card, on the landing page and the app. | `2976760` | Fixed. |
| 80ba7f | Missing canonical link tag | Low | Found | `<final>` | Canonical links on `/`, `/login`, `/signup`. | `2976760` | Fixed. |
| 26a2a9 | No sitemap.xml at the site root | Low | Found | `<final>` | `/sitemap.xml` with the public pages, referenced from `robots.txt`. | `2976760` | Fixed. |
| 2b56c7 | Words that look run together: "listmonk", "supersession" | Low | Found | `<final>` | No change. | — | Accepted: "listmonk" is the name of the open-source project used in the demo, and "supersession" is the correct term for one decision replacing another. |
| — | (Found by us while checking the baseline, not by ArgosX) The live database lacked the unique email constraint, so one email could register twice | High | — | — | Sign-up merges on the email and returns 409; account constraints are applied automatically before the first sign-up. Verified on production with two throwaway sign-ups (both deleted). | `f02ca33` | Fixed. |

**Totals:** ArgosX found 6 at baseline (2 medium, 4 low) · fixed 5 · accepted 1 (intentional product and domain terms) · open 0. We also found and fixed one high-severity issue that the public-surface scan could not see.

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
