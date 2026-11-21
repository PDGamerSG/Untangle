# Project structure

Untangle contains a Python service, a Next.js application and a separately built landing page.
Each keeps its own source and build configuration. Shared repository resources live at the root.

```text
Untangle/
├── src/untangle/          Python package and CLI
│   ├── api/              HTTP endpoints, health and response translation
│   ├── answer/           Question routing, retrieval and cited answers
│   ├── graph/            Database adapter and named-query loader
│   ├── ingest/           Git, GitHub, source and document ingestion
│   ├── repositories/     Import queue, worker, estimates and inventory
│   ├── repository_map/   Static imports, map reads and exports
│   ├── kt/               Handover transcripts and speech processing
│   └── eval/             Evaluation runner and reports
├── web/
│   ├── src/app/          Next.js routes, page metadata and global styles
│   ├── src/components/   Components grouped by feature (see below)
│   ├── src/lib/          API contracts, client, hooks and pure helpers
│   ├── public/           Browser assets; welcome/ is generated
│   ├── sample/           Recorded response fixtures for sample mode
│   ├── scripts/          Landing build and production-test orchestration
│   └── tests/            API-client, browser and production suites
├── landing/
│   ├── src/              Landing page and scene code
│   ├── public/           Static landing assets
│   └── blender/          Source asset-generation scripts
├── cypher/               Numbered database queries, bundled into the Python wheel
├── tests/                Python unit, API, database and ingestion tests
│   └── fixtures/         Recorded GitHub responses
├── scripts/              Sample export and audio-generation helpers
├── data/kt/              Synthetic handover data and consent guidance
├── eval/gold/            Evaluation question sets
├── docs/
│   ├── architecture/     Graph model and contracts
│   ├── development/      Setup, deployment, evaluation and this folder guide
│   ├── guides/           Repository, map and demonstration guides
│   ├── verification/     Dated test evidence and verification records
│   └── superpowers/      Historical specifications and implementation plans
├── .github/workflows/    CI and scheduled repository imports
└── .untangle/            This repository's feature-map definitions
```

## Web components

| Folder | Responsibility |
| --- | --- |
| `ask/` | Question composer, answers, citations and evidence graph. |
| `dashboard/` | Dashboard, search/stat panels and entity inspection. |
| `decisions/` | Decision cards, workbench, detail and timeline. |
| `layout/` | Navigation, branding, connection status and sample banner. |
| `map/` | Repository graph rendering and map explorer. |
| `meetings/` | Handover list, detail and upload. |
| `pulse/` | Risk queue, cards and triage page. |
| `repositories/` | Selected repository context, selector, imports and inventory. |
| `ui/` | Shared chips, buttons, exports and loading/error states. |

Routes in `web/src/app/` compose feature components. Components in the same folder use
relative imports; cross-feature imports use `@/components/<feature>/<name>`. Shared data access
and pure logic stay in `web/src/lib/`. Feature-map entry points are kept in `.untangle/features.json`.

## Root files and generated output

`app.py` is the deployment entry point. `pyproject.toml`, `uv.lock`, `vercel.json` and
`docker-compose.yml` remain at the root because packaging, CI and deployment read them there.
`AGENTS.md` supplies repository-wide contributor instructions; `web/AGENTS.md` adds Next.js guidance.

Generated dependencies, builds and test output stay beside their tools and are ignored by Git:
`.venv/`, `.cache/`, `dist/`, `node_modules/`, `web/.next/`, `web/test-results/`,
`web/playwright-report/`, `landing/dist/` and `web/public/welcome/`.
Environment files remain local; `.env.example` documents the available settings.

## Checks after moving files

Run the Python checks, web lint/build and browser suites listed in the [root development guide](../../README.md#-development).
Build the Python wheel when query or package paths change. Check documentation links and
`.untangle/features.json` entry points whenever their target files move.
For a deployment, follow the [two-domain production verification](DEPLOYMENT.md#verification).
