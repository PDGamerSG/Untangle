# Untangle — ArgosX remediation log

**Application scanned:** https://untangle.pallabdas.me (same build also at https://untangle-code.vercel.app)
**Baseline scan:** 21 November 2026, about 16:10 IST, free deep scan (public surface, 3 pages crawled: `/`, `/login`,
`/signup`) — report https://getargosx.com/r/ipoczozg, **VibeScore 94/100** (Security 100, Performance 100, UX 88,
Accessibility 84), 6 findings · **Final scan:** 21 November 2026, 17:41 IST, same free deep scan — **VibeScore 99/100**
(Accessibility 100, Functional 100, Performance 100, UX 97, Security 97), 3 findings (1 medium, 2 low).

| Scan | Time (IST) | VibeScore | Findings | PDF |
| --- | --- | --- | --- | --- |
| Baseline | 16:10 | 94 | 6 (2 medium, 4 low) | [argosx/argosx-baseline-2026-11-21.pdf](argosx/argosx-baseline-2026-11-21.pdf) |
| Re-test 1 | 16:44 | 96.4 | 4 (2 medium, 2 low): 4 resolved, 2 new | [argosx/argosx-retest-1-2026-11-21.pdf](argosx/argosx-retest-1-2026-11-21.pdf) |
| Re-test 2 | 17:03 | 96.4 | 4 (2 medium, 2 low): 1 resolved, 1 new | [argosx/argosx-retest-2-2026-11-21.pdf](argosx/argosx-retest-2-2026-11-21.pdf) |
| **Final** | 17:41 | **99** | 3 (1 medium, 2 low): 2 resolved, 1 new | [argosx/argosx-final-2026-11-21.pdf](argosx/argosx-final-2026-11-21.pdf) |

**Context.** The security release (accounts, access control, rate limits, security headers, private API docs, safe
errors) went live at 15:33 IST, shortly before the baseline scan, so ArgosX found no security issue on the public
surface. Section 2 records what that release changed compared with the earlier build, from our own audit.

Section 1 lists only what ArgosX reported; our own audit findings are kept in section 2 so the two sources stay
separate. Each scan can look further than the last, so later scans also reported findings the baseline did not.

## 1. Findings reported by ArgosX

| # | ArgosX finding (as reported) | Severity | Baseline | Final | What we did | Commit | Status and reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c7b886 | A11y: elements must meet minimum colour contrast (27 nodes, axe impact serious) | Medium | Found | Resolved | Round 1: unspoken transcript lines were dimmed with opacity (1.2:1), now with colour (≥4.5:1); hero footnote raised; muted text token `#66758f` → `#5a6982`. The re-test still found 8 nodes: story copy caught mid fade-in, then the hero intro fading in on load. Round 2: faded-out copy is also hidden and fades in faster; round 3: the intro slides without fading. | `2976760`, `3f6a32c`, `403bff4` | Fixed. Browser tests run axe-core on `/`, `/login`, `/signup`, at load and at every scroll position of the landing story. |
| f95aed | A11y: scrollable region must have keyboard access (1 node) | Medium | Found | Resolved | The quick-start `pre` block is focusable (`tabindex="0"`) with a region label. | `2976760` | Fixed. |
| e1f851 | Missing Open Graph tag: image | Low | Found | Resolved | 1200×630 preview image, `og:image` with size and alt text, Twitter card. | `2976760` | Fixed. |
| 80ba7f | Missing canonical link tag | Low | Found | Resolved | Canonical links on `/`, `/login`, `/signup`. | `2976760` | Fixed. |
| 26a2a9 | No sitemap.xml at the site root | Low | Found | Resolved | `/sitemap.xml` with the public pages, referenced from `robots.txt`. | `2976760` | Fixed. |
| 2b56c7 | Words that look run together: "listmonk", "supersession" | Low | Found | Open | No change. | — | Accepted: "listmonk" is the open-source project used in the demo; "supersession" is the correct term for one decision replacing another. |
| 4997eb / a44143 | Navigation links lack an active location indicator (re-test 1 and 2) | Medium | — | Resolved | The landing progress rail marks the chapter in view with a larger white knot, its name and `aria-current="location"`; a clicked chapter is marked at once. Rail links got explicit accessible names. | `3f6a32c`, `403bff4`, `53448b4` | Fixed. |
| 7ac5f9 | Additional public root domain discovered: `pallabdas.me` (CVSS 3.7, re-test 1 onwards) | Low | — | Open | No change in this app. | — | Accepted: `pallabdas.me` is the team member's separate personal site on its own Vercel project; Untangle runs only on `untangle.pallabdas.me` and `untangle-code.vercel.app`. It holds no Untangle data or credentials. Reviewing that site is outside this submission. |
| (final) | Missing password reset link on the sign-in page | Medium | — | Open (new) | No change yet. | — | Accepted for now: password reset needs an email provider to prove ownership of the address, which the app does not have yet. Mitigations: account lockout after five wrong passwords, and GitHub sign-in is being added as a second way in. Planned in the roadmap. |
| — | (Found by us while checking the baseline, not by ArgosX) The live database lacked the unique email constraint, so one email could register twice | High | — | — | Sign-up merges on the email and returns 409; account constraints are applied automatically before the first sign-up. Verified on production with two throwaway sign-ups (both deleted). | `f02ca33` | Fixed. |

**Totals:** baseline 6 findings → final 3. Across all four scans ArgosX reported 9 distinct findings: **6 fixed**
(both medium accessibility issues, the navigation indicator, and three sharing/SEO tags), **3 open with reasons**
(two intentional product terms, a separate personal domain out of scope, and password reset pending an email
provider). VibeScore 94 → 99; accessibility 84 → 100. We also found and fixed one high-severity issue (duplicate
accounts) that a public-surface scan cannot see.

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
| Password reset link (ArgosX, medium) | Needs an email provider to verify the address; lockout limits guessing and GitHub sign-in adds a second way in | Email verification and reset in the next release |
| `pallabdas.me` root domain (ArgosX, low) | A separate personal site, not part of this app or its data | None for this app |
| Run-together words (ArgosX, low) | Intentional product and domain terms | None |
