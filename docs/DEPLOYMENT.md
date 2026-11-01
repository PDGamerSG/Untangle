# Production deployment

The same public application is available at https://untangle.pallabdas.me and https://untangle-code.vercel.app.
The landing page's **Open dashboard** buttons open `/dashboard`. New sessions default to `PDGamerSG/Untangle`;
visitors can add and select their own public repositories.

## One Vercel project

| Service in `untangle-code` | Root directory | Framework | Configuration |
| --- | --- | --- | --- |
| `api` | Repository root | FastAPI | `vercel.json`, `app.py` |
| `web` | `web` | Next.js | `vercel.json`, `web/next.config.ts` |

Vercel Services builds both runtimes into one deployment. `/api/*` routes directly to Python and all other
requests go to Next.js. Both public domains point to this project. The former API hostname is retained as a
compatibility alias routed to the API service; it is not a separate project. The hosted import worker calls
`https://untangle-code.vercel.app/api`.

Deploy from the repository root with `npx vercel deploy --prod --yes --project untangle-code`. The Vercel project
root directory must be empty (repository root). To validate a release before switching domains, use
`--prod --skip-domain`, test the deployment URL, then run `vercel promote <deployment-url>`.

The root `vercel.json` pins functions to `bom1` (Mumbai) because the Aura instance runs in GCP `asia-south1`.
Keep the API near the database: every answer runs several Cypher round trips, and a function in Vercel's default `iad1`
paid about 230 ms per trip, which made simple pages take seconds and a handover transcript about ten.

The frontend build needs files outside its root directory: `web/scripts/build-landing.mjs` builds the sibling
`landing` project and copies its assets into `web/public/welcome`. Enable Vercel's option to include source files
outside the root directory. Generated assets and private `.env` files are excluded from Git and deployment uploads.

## Credentials and environment variables

Set these on the **single project's Production environment**. Never put private credentials in `NEXT_PUBLIC_*` variables.

| Variable | Value / purpose |
| --- | --- |
| `NEO4J_URI` | Reachable Neo4j endpoint, usually the Aura `neo4j+s://…databases.neo4j.io` URI. |
| `NEO4J_USER` | Database username, normally `neo4j`. |
| `NEO4J_PASSWORD` | Database password. |
| `NEO4J_DATABASE` | Database name, normally `neo4j`. |
| `ANTHROPIC_API_KEY` | Claude API key with billing available. |
| `LLM_BACKEND` | `anthropic` — Claude handles answers and decision extraction. |
| `LLM_MODEL` | Keep the configured lower-cost Claude model; do not switch to Sonnet or Opus. |
| `SARVAM_API_KEY` | Sarvam key for speech transcription and translation. |
| `SARVAM_STT_MODEL` | `saaras:v4`. |
| `SARVAM_STT_MODE` | `codemix`. |
| `EMBED_BACKEND` | `fastembed`. |
| `EMBED_MODEL` | `BAAI/bge-small-en-v1.5`. |
| `EMBED_DIM` | `384`. |
| `CORS_ORIGINS` | `https://untangle-code.vercel.app,https://untangle.pallabdas.me`. |
| `UNTANGLE_DISPLAY_LANGUAGE` | `en` (default). Responses render stored Hindi and Hinglish in English; `original` turns this off. |
| `REPO_IMPORTS_ENABLED` | `true` once the scheduled repository worker and its Actions secrets are configured. |

The embedding model runs on CPU through ONNX and needs no paid API or key. Vercel instances download it into
`/tmp/untangle`; a cold instance can take longer to answer. It does not silently substitute fake embeddings if
initialization fails. Sarvam is used for speech; no OpenAI key is needed for this deployment.

Leave `NEXT_PUBLIC_UNTANGLE_API` at its `/api` default and leave `NEXT_PUBLIC_UNTANGLE_SAMPLE` unset.
No external API URL is required in production. `UNTANGLE_API_URL` remains available for local Next.js testing;
it defaults to `http://127.0.0.1:8090`. Redeploy after environment changes.

## Load and update the graph

Users can add a public GitHub repository from the Repositories page. The durable import queue is processed by
the scheduled GitHub Actions worker. See [repository onboarding](REPOSITORY_IMPORTS.md) for setup, limits, recovery
and API contracts. This reuses the ingestion pipeline below without running it inside a Vercel request.

Store the same database and model settings in an ignored local `.env`. A `GITHUB_TOKEN` is optional for public
repositories and raises GitHub's rate limit. Run ingestion from a workstation or a persistent worker, since a full
Git history ingest is not appropriate for a serverless HTTP request:

```bash
uv sync --locked --all-extras
uv run untangle schema
uv run untangle ingest PDGamerSG/Untangle
uv run untangle stats --repo PDGamerSG/Untangle
```

Run `uv run untangle schema` once after upgrading so the `Translation` index exists. The API translates stored
Hindi and Hinglish text with Sarvam the first time a page shows it and caches the English in `(:Translation)` nodes,
so the first view of a handover call is slower than later ones.

Re-run ingestion after pushing repository changes to refresh the graph. It uses deterministic IDs and merges
existing records. Do not use `--reset` unless deliberately rebuilding the repository's graph.

## API surface

Interactive endpoint documentation is available at `/api/docs` on either public domain. Prefix each endpoint
below with `/api` when calling the deployed application (the local CLI server retains unprefixed routes).

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Graph connection, configured model, embeddings, and Sarvam readiness. |
| `GET /repos`, `GET /stats` | Ingested repositories and graph counts. |
| `GET/POST /repository-imports`, `GET /repository-imports/{id}` | Add a public repository and track durable import progress. |
| `GET /repository-overview` | Repository inventory, coverage and evidence-backed suggested questions. |
| `POST /ask` | Question, repository, optional historical date, and graph/vector comparison mode. |
| `GET /decisions/{id}`, `GET /entities/{id}` | Evidence chains and entities. |
| `GET /search`, `GET /timeline`, `GET /pulse` | Entity search, decision history, and risk signals. |
| `GET /repository-map`, `GET /repository-map/obsidian` | Feature/import graph and paginated commit history; linked Obsidian vault ZIP. |
| `GET /meetings`, `GET /meetings/{id}` | Handover summaries and transcripts. |
| `POST /kt/ingest` | Multipart upload containing `repo`, optional `title`, and exactly one `audio` or `transcript` file. |

Browser uploads are limited to 4 MB and the API function has a 300-second execution budget. Use the CLI for longer
recordings. Uploaded audio is processed temporarily and is not retained for playback.

## Verification

Run the backend suite against a disposable Neo4j database, followed by the web checks:

```bash
uv run ruff check .
uv run pytest -q
cd web
pnpm lint
pnpm build
pnpm test
pnpm exec playwright install chromium
pnpm test:e2e
```

Browser integration tests intercept API calls with recorded contracts. They verify navigation, answering and
refusal states, evidence links, timeline changes, Pulse, uploads, error recovery, and mobile layout. They do not
prove production credentials work.

The opt-in production browser checks use the deployed API and real billed answer calls. Run them from `web`
after every release. The command tests **both domains**, as required by root `AGENTS.md`, including the landing,
icons, phone navigation, restored import status, selected inventory, cited answers, history, risks and exports.
It reads `PDGamerSG/Untangle` and the completed `pallets/itsdangerous` smoke import without uploading data or
starting new jobs:

```bash
pnpm test:production
```

These checks require working Claude billing and indexed decisions/risks in both repositories. They are separate
from CI's recorded-contract suite and do not re-test Sarvam audio ingestion.

After deployment, separately verify health, repository counts, a cited Claude answer (with `llm.used` true in its
trace), graph/vector comparison, decision and timeline routes, and a short Sarvam audio upload. Health's model
availability checks configuration; a real completion is required to validate the key and selected model. Sarvam's
real-time endpoint does not support diarisation, so audio ingestion uses its batch endpoint first and retains a
non-diarised real-time fallback.
