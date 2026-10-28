# Untangle web

The Untangle web app lets engineers ask why a repository is the way it is and inspect the evidence behind the answer. It includes Ask, the Pulse knowledge-risk queue, decision pages, a date-aware timeline, and handover-call views.

## Run locally

From the repository root, start the API with `uv run untangle serve`, then run the web client:

```bash
cd web
pnpm install
pnpm dev            # http://localhost:3000
```

The API is the FastAPI server from the Python package. Its default address is `http://localhost:8090`; set `CORS_ORIGINS` in the root `.env` if the client runs elsewhere.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_UNTANGLE_API` | `http://localhost:8090` | Base URL of the Untangle API. |
| `NEXT_PUBLIC_UNTANGLE_SAMPLE` | unset | Set to `1` to read checked-in fixtures from `web/sample/` instead of calling the API. |

Sample mode is useful for a product walkthrough without Neo4j:

```bash
NEXT_PUBLIC_UNTANGLE_SAMPLE=1 pnpm dev
```

The banner identifies sample mode, and the selected repository is `knadh/listmonk`, the fixture repository used by the demo. Sample responses include Ask, Pulse, decisions, timeline, meetings, and the vector-only comparison.

## Routes

| Route | Purpose |
|---|---|
| `/` | Ask a question and inspect the grounded answer. |
| `/pulse` | Review ranked contradictions, drift, ownership gaps, and missing rationale. |
| `/decisions/:id` | Follow a decision's evidence and supersession chain. |
| `/timeline` | See which decisions were in force on a chosen date. |
| `/meetings` | Browse handover calls and extracted decisions. |

## Client structure

| Folder | Contents |
|---|---|
| `src/app/` | App Router pages and global styles. |
| `src/components/` | Navigation, repository context, pages, cards, evidence panels, and state components. |
| `src/lib/api.ts` | API client and sample-mode switch. |
| `src/lib/sample.ts` | Fixture loaders used only when sample mode is enabled. |
| `sample/` | Checked-in response fixtures for the local walkthrough. |

The interface keeps the answer path visible: the question resolves to a repository entity, the entity leads to a decision, and the decision expands into supporting discussions, people, dates, and source links. Copy actions are client-only and do not send answer text anywhere.

## Checks

```bash
pnpm lint
pnpm build
```
