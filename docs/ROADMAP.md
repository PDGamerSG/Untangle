# Untangle roadmap

Written 21 November 2026 for hackathon judges, teammates and future contributors.

**Status.** The accounts, access-control, security and reliability work in section 2 is finished in the working tree
and passes local tests, but is not deployed. Until it is, and the live suite passes on both
https://untangle.pallabdas.me and https://untangle-code.vercel.app, the public sites run the previous release,
which has no sign-in.

## 1. What Untangle is and who it is for

Untangle answers one question: why is the code like this? It builds a Neo4j graph from a public GitHub repository's
history (commits, pull requests, reviews, issues, ADRs and other documents, configuration and lockfile diffs, and
source symbols) and from uploaded handover calls, including Hinglish transcripts. Ask about a config value,
dependency, file or module and Untangle returns the decision behind it, its evidence, whether a later decision
replaced it, and who is most likely to know more. When the graph holds no supporting evidence, it says so instead
of guessing.

### The problem

The reason behind a line of code usually lives in an old PR thread, a closed issue or one person's memory.
Engineers and coding agents change code without knowing what it protected against, and when that person leaves,
the reason leaves too.

### Evidence of demand

| Finding | Source |
|---|---|
| About 58% of developer time goes to program comprehension (field study of 78 professionals) | [Xia et al., TSE 2018](https://xin-xia.github.io/publication/TSE17.pdf) |
| The pain is concentrated: 29.6% of developers hit knowledge silos 10+ times a week, while 52.1% never do | [Stack Overflow 2024](https://survey.stackoverflow.co/2024/professional-developers) |
| 65% of developers using AI for refactoring say it "misses relevant context" | [Qodo 2025](https://www.qodo.ai/reports/state-of-ai-Code-quality/) |
| 41% of surveyed software leaders run MCP in production; 49% name security as the top blocker | [Stacklok 2026](https://stacklok.com/resources/state-of-mcp-in-software-2026/) |
| 80% of dependencies go un-upgraded for over a year, although a fix exists 95% of the time | [Sonatype 2024](https://www.sonatype.com/state-of-the-software-supply-chain/2024/introduction) |

### Positioning

Cited answers about code are already a paid product: Unblocked sells them for $29 per user per month, with MCP,
Slack, PR review and meeting ingestion ([Unblocked pricing](https://getunblocked.com/pricing/index.md)).
Auto-generated wikis such as DeepWiki explain what code does from today's snapshot, and context engines from
Augment, Qodo and Sourcegraph feed coding agents. The [expansion research](research/2026-11-21-expansion-research.md)
found three capabilities that no competitor documents:

- **Refusal** with fixed wording when evidence is missing, plus the closest related entities and a person to ask.
- **Time-versioned decisions**: when each was in force (`valid_from`, `valid_to`), when the graph learned it
  (`created_at`, `expired_at`), and `SUPERSEDES` links that keep replaced reasons readable.
- **Time-aligned upstream evidence**: linking a past decision to the upstream issue, advisory or release behind it.
  Untangle does not do this yet; it is the roadmap's main wedge.

Our position is decision memory that proves why, shows when that reason stopped being true, and says when it does
not know. We will compete on two numbers no competitor publishes, refusal precision and as-of-date accuracy,
rather than on connector count.

### First buyers

1. **Platform and developer-experience leads** who want coding agents to get decision context before editing code.
2. **AppSec and platform teams, and maintainers,** asking "why is this pinned, and can we remove it now?"
3. **Transition heads in Indian IT services firms and global capability centres,** where handovers happen during
   notice periods, often in Hinglish. They need teams and private repositories first, so they come in phase 3.

## 2. What is built today

*Live* means running on both domains now. *Built* means finished and tested locally, waiting for deployment.

| Area | What exists | Status | Where it lives |
|---|---|---|---|
| Core workflow | Import a public repository through a durable queue; use Dashboard, Ask, Timeline, Pulse, Map and Meetings on it | Live | `src/untangle/repositories/`, `.github/workflows/repository-imports.yml` |
| Core workflow | Ask: cited answers, supersession, person to ask, refusal, comparison with vector-only search | Live | `src/untangle/answer/`, `cypher/31_*` to `34_*`, `web/src/components/ask/` |
| Core workflow | Timeline (what was in force on a date), Pulse risk queue, Markdown evidence briefs | Live | `cypher/33_belief_at.cypher`, `src/untangle/pulse.py`, `web/src/components/pulse/` |
| Core workflow | Feature and commit map with Obsidian export | Live | `src/untangle/repository_map/`, `web/src/components/map/` |
| Core workflow | Handover calls linked to code, marked `CONFIRMS` or `CONTRADICTS` against code decisions | Live | `src/untangle/kt/`, `cypher/24_reconcile_kt.cypher`, `web/src/components/meetings/` |
| Data and backend | FastAPI service; Neo4j with numbered Cypher queries, full-text and vector indexes; ingestion of every source listed in section 1 | Live | `src/untangle/api/`, `src/untangle/graph/`, `src/untangle/ingest/`, `cypher/` |
| Accounts and access | Email and password accounts (Argon2id, length and common-password checks), 7-day HttpOnly session, sign-out, account deletion, admin role | Built | `src/untangle/auth/`, `src/untangle/api/auth.py`, `web/src/components/auth/` |
| Accounts and access | Session required on every API route except health and sign-in; sign-in redirect; uploader-owned handover calls; consent checkbox | Built | `src/untangle/api/auth.py`, `web/src/proxy.ts`, `cypher/89_*`, `cypher/90_*` |
| Accounts and access | Question, upload, import, sign-in and sign-up limits stored in Neo4j, shared across serverless instances | Built | `src/untangle/auth/limits.py`, `cypher/86_*` to `88_*` |
| Agents (Neo4j agent memory) | MCP server over Streamable HTTP with eight graph tools, including `remember_decision`, which stores an agent's decision as a superseding `Decision {kind: 'agent'}`; personal access tokens stored as hashes; Agents page | Built | `src/untangle/mcp_server.py`, `src/untangle/agent_memory.py`, `src/untangle/auth/tokens.py`, `cypher/91_*` to `96_*`, `web/src/components/agents/` |
| Change safety | Pre-flight checks: replaced values coming back, guarding decisions, three-hop import reach, co-changed files, tests, OSV.dev advisories, reviewers and a points-based review level; also an MCP tool (`check_change`) for coding agents | Built | `src/untangle/preflight.py`, `src/untangle/advisories.py`, `cypher/97_*`, `web/src/components/preflight/` |
| Onboarding | Day-one briefing (areas and authors, decisions to read first, recent replacements, people, starter questions) as a page, Markdown and an MCP tool; decision replay; exact date-to-date comparison | Built | `src/untangle/briefing.py`, `cypher/98_*`, `cypher/99_decision_*`, `web/src/components/briefing/`, `web/src/components/decisions/` |
| Answers | Premise check for "X instead of Y" questions; listening in eleven Indian languages; Benchmarks page from the recorded evaluation | Built | `src/untangle/answer/premise.py`, `src/untangle/speech.py`, `web/src/components/benchmarks/` |
| Security | CSRF origin checks, security headers, private API docs, minimal health output, generic errors with request ids, bounded inputs | Built | `src/untangle/api/security.py`, `src/untangle/api/main.py`, `web/next.config.ts` |
| Security | Next.js 16.4.5, Actions pinned to commit SHAs with step-scoped secrets, tests refuse hosted databases | Built | `web/package.json`, `.github/workflows/`, `tests/conftest.py` |
| Reliability | Job leases, heartbeats and retries (live); page error boundaries and friendly errors (built) | Live and built | `src/untangle/repositories/jobs.py`, `web/src/app/(app)/error.tsx` |
| UX | Refusals with next steps, loading states, better 404, links that prefill a question, meeting delete | Built | `src/untangle/answer/compose.py`, `web/src/components/ui/`, `web/src/app/not-found.tsx` |
| Deployment | One Vercel project for Next.js and the Python API on two domains, functions in Mumbai beside the database | Live (previous release) | `vercel.json`, `app.py`, `docs/development/DEPLOYMENT.md` |
| Tests | 309 Python tests and 55 browser and API-client tests; live suite signs in with a throwaway account | Pass locally; live run pending | `tests/`, `web/tests/`, `web/scripts/test-production.mjs` |

## 3. How the six evaluation criteria are met

### 3.1 Primary workflow with no fake steps

Sign up, import a public repository, wait for indexing, ask why, and follow the citations.

- **Check:** Sign up at `/signup` with a throwaway email. On **Repositories**, paste a small public repository and
  watch the job move from queued to running to complete. Ask about one of its config values or dependencies and
  open a citation: it leads to a real commit, PR, issue or document. Ask "why do we use Kafka?" of a repository
  without Kafka and expect a refusal with a next step.
- **Limits:** Imports run on a GitHub Actions worker scheduled every five minutes; a job usually starts within
  minutes, but GitHub does not guarantee schedule times. Hosted imports use deterministic extraction only, so many
  decisions lack a written rationale, and they stop at 1,000 commits, 50 PRs and 100 issues. The sample handover
  call is synthetic: its fictional speakers and reasons are labelled in `data/kt/`, but answers citing it are not
  labelled yet. Sample mode is a local demo with a banner and never replaces a failed live request.

### 3.2 Backend and a real database

- **Check:** Every page reads from the FastAPI service, and every answer comes from Cypher queries against Neo4j
  Aura. After an import, the dashboard counts match the repository, and the **repository imports** workflow log
  shows the worker claiming the job. Ask shows the citations, graph route and subgraph behind each answer. CI runs
  the Python suite against a real Neo4j service.
- **Limits:** The capacity of the current Aura plan is unmeasured. Evidence from imported public repositories is
  visible to every signed-in user.

### 3.3 Authentication

- **Check:** Signed out, `/dashboard` redirects to `/login?next=/dashboard`; a `next` value pointing to another
  site is ignored. `curl -i https://untangle.pallabdas.me/api/repos` without a cookie returns 401. After sign-in,
  the `__Host-untangle_session` cookie is HttpOnly, Secure and SameSite=Lax, and only a SHA-256 hash of the
  token is stored. After five wrong passwords in a 15-minute window, that account refuses sign-in until the window
  resets. Sign-out revokes the session on the server.
- **Limits:** No email verification or password reset yet, because both need an email provider. No GitHub
  sign-in, teams or private repositories.

### 3.4 Reliability

- **Check:** Start an import, close the tab and return: the job survives because it lives in Neo4j with a lease
  and heartbeats, and a stalled job becomes retryable after three minutes. A missing page or malformed request
  gets a plain message with a request id, not a stack trace. Limits reply with a retry time; five wrong passwords
  is the cheapest way to see one.
- **Limits:** One worker runs one job per run, capped at 40 minutes. There is no alerting or tracing yet, so
  failures show only in the UI and in workflow logs.

### 3.5 User experience

- **Check:** At phone width the navigation collapses into a menu. Pages show loading, empty and error states
  instead of raw 422 or 500 text. Timeline and Pulse download a source-linked Markdown brief; Map downloads an
  Obsidian vault. A link from another site fills in the question box without sending it, so no quota is spent.
- **Limits:** Timeline loads up to 100 decisions. Pulse scores are heuristic signals, not probabilities. Commit
  impact is estimated from static imports, not from a tested revert.

### 3.6 Live deployment

- **Check:** Both domains serve the same Vercel project. `curl -I` on either shows CSP, HSTS,
  `X-Frame-Options: DENY` and `nosniff`. `/api/health` reports status without the database host, versions or
  model names. `cd web && pnpm test:production` runs the live browser suite against both origins.
- **Limits:** The live suite has not yet run against this release. A pass on one domain does not verify the
  other, so results are reported per origin. The suite makes real, billed answer calls.

## 4. Roadmap

Effort: **S** is up to 3 engineer-days, **M** 1–2 engineer-weeks, **L** 3–5 and **XL** 6 or more, for one or two
engineers. Items are in priority order; if early items run long, the last ones move to the next phase. Every
user-facing item ends with the live suite passing on both domains, keeps the configured lower-cost model, and
keeps model and provider names out of UI copy.

### Phase 1: next two weeks. Ship what is built and measure it

| # | Item | Purpose | Approach | Depends on | Effort | Verified by |
|---|---|---|---|---|---|---|
| 1.1 | Deploy the accounts and security release | Put finished work in front of users | Deploy with `--skip-domain`, test the deployment URL, then promote | None | S | Live suite passes on both domains; results per origin in `docs/verification/` |
| 1.2 | Synthetic-content label | Stop demo rationale being read as real | Mark sample-transcript evidence as synthetic in the graph; label it on citations and meeting pages | None | S | Tests assert the label on every answer citing the sample call |
| 1.3 | Email verification and password reset | Close the largest account gaps | Single-use, hashed, short-lived tokens; reset revokes all sessions | Email provider | M | Tests for expiry, reuse and responses that never reveal whether an account exists |
| 1.4 | Nonce-based CSP | Remove `'unsafe-inline'` from page scripts | Per-request nonce set in the Next.js proxy | 1.1 | S | Header test; no CSP violations in the live suite |
| 1.5 | Eval v2 | Publish numbers that guard every later change | Add a second repository with ADRs and revert trailers to `src/untangle/eval`; check quotes and entailment, not only citation IDs | Existing harness | M | Refusal precision and recall, as-of-date accuracy, citation accuracy; attributions stable when irrelevant evidence is added |
| 1.6 | Rationale extraction in hosted imports | Fill the largest data gap: hosted imports skip it today | Require a verbatim quote, exact span match and entailment check; version extractions instead of overwriting | 1.5; model key scoped to the worker step | M | Share of decisions with a rationale before and after; precision on a labelled sample; logged cost per import |

### Phase 2: one to two months. The external-evidence wedge and table stakes

| # | Item | Purpose | Approach | Depends on | Effort | Verified by |
|---|---|---|---|---|---|---|
| 2.1 | Always-on import worker | Start imports in seconds; remove the 40-minute cap | Run `untangle import-worker` continuously on the same queue (a Render background worker is an option we have); keep the Actions schedule as fallback | 1.1 | M | Enqueue-to-claim time over 20 imports; kill-and-resume through lease expiry |
| 2.2 | Observability | Find failures before users do | Request-id logs, error tracking, uptime checks on both domains, failed-job alerts, daily count of billed answers | 1.1 | M | Injected failures raise alerts; a test shows no secrets in logs |
| 2.3 | GitHub sign-in | Faster sign-up for developers | GitHub OAuth app; link existing accounts only by verified email | OAuth app; 1.3 | S | Tests for state checks, linking and denied consent |
| 2.4 | Structured upstream evidence | External evidence at no API cost | Worker fetches OSV.dev, deps.dev, endoflife.date, CISA KEV and EPSS for indexed dependencies; shown apart as "Upstream evidence" | 2.1 | M | Tests on recorded responses; known advisories show ID, fixed version and exploitation status |
| 2.5 | "Can we remove this pin or workaround?" | The most checkable claim Untangle can make | Link pins to upstream GitHub issues; read issue state; use GitHub compare to find the first release with the fix | 2.4, 1.6 | L | Gold set of about 30 decisions with known outcomes; every "removable now" flag reviewed by hand |
| 2.6 | MCP server and agent memory (**built at the finale**) | Decision context and memory for coding agents | Eight tools on the Neo4j graph, including `remember_decision`; hashed personal tokens under per-user limits | 1.1 | M | Done locally with the official MCP client; next: add the endpoint to the live suite |
| 2.7 | Quick Investigate | Bounded web search when structured sources miss | Queries from public identifiers only; research step never sees private evidence; tool-free synthesis; every citation anchored to an exact fetched quote; hard spend caps | 1.5, 2.5 | L | 20–40 cases on frozen pages, including injection attempts and refusals; citation accuracy; cost and latency per run |
| 2.8 | Pulse v2 | Measured signals instead of fixed boolean weights | Per-feature authorship ownership, evidence-based staleness (version lag, end-of-life, closed upstream issues), partial rationale gaps | 1.6, 2.4 | M–L | Replay Pulse from six months earlier against later reverts, contradictions and departures |

### Phase 3: three to six months. Teams, private code and new surfaces

| # | Item | Purpose | Approach | Depends on | Effort | Verified by |
|---|---|---|---|---|---|---|
| 3.1 | Organisations and teams | Prerequisite for private data and paid plans | Workspaces with roles; every query scoped to a workspace; per-workspace visibility of handover calls | 1.3 | XL | Cross-workspace isolation suite; external security review |
| 3.2 | GitHub App: private repositories and PR guard | Import private code under GitHub's permissions; flag PRs that touch an active, superseded or upstream-blocked decision | Installation tokens; retrieval that mirrors repository access; at most one comment per PR | 3.1, 2.5 | XL | Access-mirroring tests; replay on 100 past PRs rated by maintainers |
| 3.3 | Higher scale limits | Lift the 1,000-commit, 50-PR and 100-issue caps | Incremental imports on the always-on worker | 2.1; database plan decision | L | Import time and cost per 10,000 commits |
| 3.4 | Deep Investigate | Investigations longer than one request | Worker job with a stored budget and resumable steps | 2.7, 2.1 | L | Budget never exceeded; kill-and-resume test |
| 3.5 | Handover and transition kit | Paid product for IT services firms and capability centres | Handover plans, leaver question lists, completeness score, readiness report | 3.1, 2.8 | L | Pilot with 1–2 teams; measured transcription error on technical Hinglish calls |
| 3.6 | Slack, Jira and Confluence connectors | Tickets and chat hold much of the missing rationale | One connector per source under the same citation rules | 3.1 | XL | Rationale coverage before and after; Slack answers pass the same validator |
| 3.7 | Compliance evidence packs | Change-rationale evidence for SOC 2, ISO 27001, DORA and the EU Cyber Resilience Act | PR-to-ticket-to-decision-to-approval traceability, gap reports, immutable exports | 3.1, 3.6, 2.4 | XL | A practitioner reviews a mock sample of 25 changes |

Deferred until evidence raises their priority: co-change edges for the map and agent-provenance commit trailers.

## 5. How we will approach the work

### Principles

- **Evidence before claims.** Every answer, flag and score points at retrieved evidence. External evidence is a
  separate tier and never silently overrides repository evidence.
- **Refusal over guessing.** If nothing survives validation, Untangle refuses and offers a next step.
- **Measured quality.** Changes to retrieval, extraction or scoring run the eval first, and we publish the results,
  failures included.
- **Security by default.** Sessions on every route, least-privilege secrets, no credentials in browser code, logs or
  commits, and untrusted web pages kept apart from private evidence and tools.
- **Cost limits.** Per-user quotas, hard per-run research budgets, the configured lower-cost model, and no model
  upgrade without the owner's decision.

### Release process

1. Run `uv run ruff check src tests` and `uv run pytest -q`, then in `web/`: `pnpm lint`, `pnpm build`,
   `pnpm test` and `pnpm test:e2e`.
2. From the repository root, never inside `web/`, run
   `npx vercel deploy --prod --skip-domain --yes --project untangle-code`, test the deployment URL, then
   `vercel promote <deployment-url>`.
3. Run `cd web && pnpm test:production`. It signs in with a throwaway account, makes real billed answer calls, and
   checks the landing page, onboarding, dashboard, Ask with citations, history, Pulse, the map, downloads, icons
   and mobile navigation on both origins.
4. Record exact results per origin in `docs/verification/`. If a domain fails, report it and do not call the
   release verified.

### Risks

| Risk | Mitigation |
|---|---|
| A funded competitor such as Unblocked adds an explicit decision log | Publish refusal precision, as-of-date accuracy and citation accuracy on a public gold set first |
| Extracted rationale is often wrong: published methods reach 27–51% precision ([Zhou et al.](https://arxiv.org/abs/2504.20781), [Sun et al.](https://arxiv.org/abs/2604.10345)) | Quote, entailment and confidence gates ship with extraction (1.6), not after it |
| Prompt injection through fetched web pages | Plan queries before reading untrusted text, research without private data, synthesise with no tools, strip uncited URLs and sentences |
| A long, uncached research run costs far more than a normal one | Caps on searches and fetched tokens, prompt caching, stored per-run budgets, spend recorded per run |
| Shared upstream APIs limit requests per network | Fetch only from the worker with its own token, never from serverless functions |
| Database capacity on the current plan is unknown | Measure graph size per import before lifting scale limits (3.3) |
| Email delivery and GitHub sign-in depend on outside accounts | Set them up early in phase 1; password sign-in works without them |
| Handover recordings contain personal data | Consent checkbox, uploader ownership and deletion today; per-workspace visibility in 3.1 |
