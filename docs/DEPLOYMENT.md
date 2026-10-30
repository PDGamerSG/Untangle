# Production deployment

The public frontend is https://untangle-code.vercel.app. The landing page's **Open dashboard** buttons open `/dashboard`, the application's home.
The FastAPI project is https://untangle-code-api.vercel.app; the frontend proxies `/api/*` to it.
The selected repository is `PDGamerSG/Untangle`.

## Vercel projects

| Project | Root directory | Framework | Configuration |
| --- | --- | --- | --- |
| `untangle-code-api` | Repository root | FastAPI | `vercel.json`, `app.py` |
| `untangle-code` | `web` | Next.js | `web/vercel.json` |

The frontend build needs files outside its root directory: `web/scripts/build-landing.mjs` builds the sibling
`landing` project and copies its assets into `web/public/welcome`. Enable Vercel's option to include source files
outside the root directory. Generated assets and private `.env` files are excluded from Git and deployment uploads.

## Credentials and environment variables

Set these on the **API project's Production environment**. Never put private credentials in `NEXT_PUBLIC_*` variables.

| Variable | Value / purpose |
| --- | --- |
| `NEO4J_URI` | Reachable Neo4j endpoint, usually the Aura `neo4j+s://…databases.neo4j.io` URI. |
| `NEO4J_USER` | Database username, normally `neo4j`. |
| `NEO4J_PASSWORD` | Database password. |
| `NEO4J_DATABASE` | Database name, normally `neo4j`. |
| `ANTHROPIC_API_KEY` | Claude API key with billing available. |
| `LLM_BACKEND` | `anthropic` — Claude handles answers and decision extraction. |
| `LLM_MODEL` | A Claude model ID available to the supplied API key. |
| `SARVAM_API_KEY` | Sarvam key for speech transcription and translation. |
| `SARVAM_STT_MODEL` | `saaras:v4`. |
| `SARVAM_STT_MODE` | `codemix`. |
| `EMBED_BACKEND` | `fastembed`. |
| `EMBED_MODEL` | `BAAI/bge-small-en-v1.5`. |
| `EMBED_DIM` | `384`. |
| `CORS_ORIGINS` | `https://untangle-code.vercel.app`. |
| `UNTANGLE_DISPLAY_LANGUAGE` | `en` (default). Responses render stored Hindi and Hinglish in English; `original` turns this off. |

The embedding model runs on CPU through ONNX and needs no paid API or key. Vercel instances download it into
`/tmp/untangle`; a cold instance can take longer to answer. It does not silently substitute fake embeddings if
initialization fails. Sarvam is used for speech; no OpenAI key is needed for this deployment.

Set `UNTANGLE_API_URL=https://untangle-code-api.vercel.app` on the **frontend project's Production environment**.
Leave `NEXT_PUBLIC_UNTANGLE_API` at its `/api` default and leave `NEXT_PUBLIC_UNTANGLE_SAMPLE` unset.
Redeploy after environment changes.

## Load and update the graph

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

Interactive endpoint documentation is available at the API's `/docs` route.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Graph connection, configured model, embeddings, and Sarvam readiness. |
| `GET /repos`, `GET /stats` | Ingested repositories and graph counts. |
| `POST /ask` | Question, repository, optional historical date, and graph/vector comparison mode. |
| `GET /decisions/{id}`, `GET /entities/{id}` | Evidence chains and entities. |
| `GET /search`, `GET /timeline`, `GET /pulse` | Entity search, decision history, and risk signals. |
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

After deployment, separately verify health, repository counts, a cited Claude answer (with `llm.used` true in its
trace), graph/vector comparison, decision and timeline routes, and a short Sarvam audio upload. Health's model
availability checks configuration; a real completion is required to validate the key and selected model. Sarvam's
real-time endpoint does not support diarisation, so audio ingestion uses its batch endpoint first and retains a
non-diarised real-time fallback.
