# Add your repository

Open **Repositories**, paste a GitHub URL or `owner/name`, and start the import. The job is saved in Neo4j,
so closing or reloading the page does not cancel it. When it finishes, open that repository's workspace.
The selected repository applies to the dashboard, Ask, Timeline, Pulse, Map, meetings, and exports.
Clone URLs ending in `.git` and links with a trailing slash are accepted too.

The tracker shows elapsed time and an estimated remaining range. Small imports are budgeted at 2–10 minutes
once running; larger imports at 5–20 minutes. Queued estimates add 1–10 minutes for scheduling and 2–20 minutes
per repository ahead in the queue. These are planning
ranges, not measured completion guarantees: GitHub traffic, queue depth and first-time model setup can extend them.
When the range is exceeded the tracker says so instead of counting down to a false completion.

The public deployment accepts publicly readable GitHub repositories. Imported evidence is shared with other
visitors. It does not request users' GitHub passwords or tokens and cannot import private repositories.

## Trying without an account

The sign-in page offers **Try it on your repository, no account**. It starts a guest session: a temporary account
that can add a public repository, ask about it and use every page. Guests get a quarter of a member's hourly and
daily allowances, and cannot create agent tokens. A banner offers **Create account** and **Sign in** on every page.
Creating an account turns the guest into that account and keeps its repositories. Signing in to an existing account,
by email or with GitHub, moves the guest's saved repositories there and deletes the guest. One network can start
20 guest sessions an hour.

## Built-in agent

The Agents page answers questions with the deployment's configured Claude model and the same read-only tools that
coding agents reach over MCP (`ask_why`, `list_decisions`, `decision_timeline`, `who_to_ask`, `search_repository`,
`recall_agent_notes`, `list_repositories`). It needs no token. It cannot write to the graph. Each message counts
against the Ask allowance and each lookup against the agent-call allowance. **Use your own agent** below it keeps
the token and MCP setup for Claude Code, Cursor and other clients.

## Your repositories and GitHub sign-in

**Continue with GitHub** on the sign-in and sign-up pages creates or opens an account from a GitHub identity.
It requests only `read:user user:email` and never stores the GitHub access token. A GitHub identity links to the
signed-in account, or to an existing account whose email matches the verified primary GitHub email; otherwise
GitHub creates a new account without a password. An account without a password cannot disconnect GitHub.

On **Repositories**:

- **Your repositories** lists repositories the signed-in person added or saved. Only that person sees the list;
  imported evidence stays shared. For each indexed repository, **What changed** compares the indexed commit with
  the current default branch on GitHub. It shows new commits, changed files and a compare link, and
  **Update import** queues a fresh import. Opening the changes marks them as seen.
- **From GitHub** lists the public repositories of the connected GitHub account, or of any user or organization
  name typed there. **Import** queues a repository and saves it to the list.

Configure one GitHub OAuth App per public origin in `GITHUB_OAUTH_APPS` (see `.env.example`); the callback URL is
`<origin>/api/auth/github/callback`. Without it, the button is hidden and the rest still works. Set `GITHUB_TOKEN`
(public read-only) on the API too, so repository lists and comparisons are not limited to 60 GitHub calls per hour.

## Analysis and coverage

The worker reuses the full ingestion pipeline: commits and parents, changed files, contributors, source symbols,
configuration, dependencies, documentation and ADRs, pull requests/reviews/issues, recorded decisions, search
chunks, free CPU embeddings, and the static feature/import map. Hosted imports use deterministic extraction,
without paid model calls. Ask continues to use the existing low-cost Claude API. No new model or embedding key is needed.
The application never executes an imported repository's scripts, tests, hooks, or dependencies.

The overview reports actual indexed counts and lists dependencies, documents and feature definitions. Suggested
questions come from active decisions in the repository. Repositories with little recorded history may have few
decisions or no evidence for a particular question. Without `.untangle/features.json`, feature boundaries are
explicitly labelled inferred directory groups. Import reachability is not proof of what a revert would break.
Older repositories without a source map immediately expose their stored files, directory groups and commit
changes. The page labels missing import connections and offers **Build import connections**, which queues the
normal hosted refresh. An invalid optional feature manifest falls back to directory groups with a visible warning.

Hosted limits: GitHub-reported repository size at most 100,000 KB, 1,000 recent commits, 50 PRs, 100 entries from
GitHub's combined issues endpoint, six pending imports, and twenty new jobs per rolling day across the deployment.
The map scans all eligible source files and pages through all indexed paths and import connections. Inventory previews contain up to 50 dependencies, 50 documents,
and 60 feature groups; counts describe all indexed records. The CLI supports larger history imports.

The dashboard inventory displays an estimated wait and elapsed time. Import completion invalidates cached
inventory, map and tool data, so reimporting the selected repository refreshes mounted views too. The worker
checks persisted file, feature, entry-point and import counts before marking a job complete. Each scheduled run
processes one job, avoiding interruption of a later job near the workflow's 40-minute limit. Failed or expired
imports remain explicitly retryable; no time estimate is treated as proof of completion.

## Durable execution

Vercel handles short admission/status requests. The scheduled `repository imports` GitHub Actions workflow runs
the trusted `untangle import-worker` command against the same Aura database. It checks the queue before installing
dependencies. Starts are usually within minutes, but GitHub scheduling is not a timing guarantee. A maintainer
can dispatch the workflow manually.

An admission transaction locks one control record, coalesces duplicate submissions, and enforces global quotas.
An atomic claim permits only one active ingestion. A random lease token owns progress/completion updates.
Heartbeats run every 25 seconds; a running job without updates for three minutes becomes retryable. A queued job
without a worker for five hours also becomes a visible failure; this allows a full queue to survive earlier
jobs and scheduling delays. Re-adding a failed repository creates a new job;
active or recently completed imports return the existing job. Completed imports can be refreshed after an hour.
Failed refreshes preserve previously stored evidence and report partial-update risk.

### Persistent worker on Render

GitHub runs the five-minute schedule only every few hours on this repository, so queued imports could wait that long.
A Render background worker (`render.yaml`, `deploy/render/worker.Dockerfile`) runs
`untangle import-worker --poll 15`: it checks the queue every 15 seconds and starts a job at once. It uses the
same Aura queue and leases, so it can run beside the scheduled workflow, which stays as a fallback. A failed poll
reconnects on the next one. On shutdown it finishes the current job when Render's 300-second grace period allows;
otherwise the lease expires and the job becomes retryable.

A local import of a small repository peaked near 1.1 GB of memory, so the worker uses Render's 2 GB Standard plan.
Set `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` and `GITHUB_TOKEN` in Render. Use a fine-grained
token with public read-only access. Anonymous GitHub calls share a 60-per-hour limit per outbound address. The
public-visibility check still tries without the token first. If GitHub answers 403/429, it repeats with the token
and reports any private repository exactly like a missing one.

## Deployment

Set `REPO_IMPORTS_ENABLED=true` on the API after deploying the workflow and schema. Configure these GitHub Actions
secrets using the existing API credentials: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE`.
The worker uses the read-only Actions `GITHUB_TOKEN` and `EMBED_BACKEND=fastembed`. Optional LLM rationale extraction
is disabled (`llm_prs=0`), so the worker needs no model credentials. The app retains its existing model configuration.

The checkout does not persist credentials. Public accessibility is checked without authentication both before
enqueue and before ingestion. Arbitrary hosts, credentials, query parameters and filesystem paths are rejected.
Each workflow run is limited to forty minutes. Import progress describes stages, not estimated time remaining.

```bash
uv run untangle schema
uv run untangle import-worker --max-jobs 6
gh workflow run repository-imports.yml
```

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /repository-imports` | Configuration, limits, last worker activity, and 30 recent jobs. |
| `POST /repository-imports` | JSON `{"repository":"owner/name"}`; returns a durable job with HTTP 202. |
| `GET /repository-imports/{id}` | Progress, timestamps, completion counts, warnings or a retryable error. |
| `GET /repository-overview?repo=owner/name` | Indexed inventory, coverage and suggested questions. |

States: `queued`, `running`, `complete`, `failed`. Invalid/missing/private repositories produce actionable
400/404 errors; size limits return 413, shared capacity limits 429, and GitHub/service unavailability 503.
Responses never contain worker leases or upstream exception text that could disclose credentials.

## Validation

`tests/test_repository_imports.py` covers input validation, real Neo4j concurrency, leases, retry, HTTP contracts,
failure redaction and the complete fixture ingestion/overview/Ask/map path. Existing backend and browser suites
remain required. Production verification includes a real different repository and its exported graph; fixtures
alone do not establish that the hosted worker is configured.
