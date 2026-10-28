# Kyun web (क्यों)

The web app of Kyun: ask "why is the code like this?" and get an answer with its chain of evidence, supersession, a graph-derived confidence score, the Cypher that ran, and the subgraph it read. Or an honest refusal.

Next.js 16 (App Router, React 19, Tailwind 4, TypeScript strict). No component library; `d3-force` draws the subgraph, `lucide-react` provides icons.

## Run

```bash
cd web
pnpm install
pnpm dev            # http://localhost:3000, talks to the API at NEXT_PUBLIC_KYUN_API
pnpm build && pnpm start
pnpm lint
```

The API is the FastAPI server from the Python package (`kyun serve`, port 8090 by default). CORS must allow `http://localhost:3000` (`CORS_ORIGINS` in the root `.env`).

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_KYUN_API` | `http://localhost:8090` | Base URL of the Kyun API. |
| `NEXT_PUBLIC_KYUN_SAMPLE` | unset | Set to `1` to read the fixtures in `web/sample/` instead of calling the API. A "Sample data" banner is shown. |

Both are `NEXT_PUBLIC_*`, so they are inlined at build time: rebuild after changing them. Put them in `web/.env.local` or on the command line:

```bash
NEXT_PUBLIC_KYUN_SAMPLE=1 pnpm dev
```

## Sample mode

`web/sample/*.json` are **snapshots of real API responses** from the live graph of `knadh/listmonk`, written by
`uv run python scripts/export_sample.py --repo knadh/listmonk` (re-run after re-ingesting). Nothing in them is
hand-written: the answers, citations, confidence, Cypher calls, subgraphs, the vector-only baseline (asked with
`mode: both`), the decision pages and the handover call are exactly what Kyun returned.

- six recorded questions: why `app.concurrency` is set the way it is (and the same as of 1 Jan 2020), whether
  `github.com/lib/pq` is still used, who to ask about `internal/manager`, what changed in `docker-compose.yml`, and a
  refusal ("why does listmonk use MongoDB?"),
- every decision those answers touch, each with its why-path page,
- the synthetic Hinglish handover call in `data/kt/listmonk-kt-sample.json` as the graph stores it.

`src/lib/sample.ts` picks the recorded answer whose question resembles the one typed (the recorded question text is
shown, so a visitor sees what was actually asked; anything unrecognised gets the recorded refusal), honours `at`
(a date before `app.concurrency` changed on 2 Apr 2020 returns the earlier snapshot) and `mode: both`, and computes the
timeline from the decision cards' `valid_from`/`valid_to`.

`web/sample/pulse.json` contains the listmonk risk queue used by the Pulse dashboard in sample mode, including a code-vs-handover contradiction, an ownership gap, and a drift/rationale warning.

The app never falls back to the sample data when the API fails: errors are shown with a retry button.

## Pages

| Route | What it shows |
|---|---|
| `/` | Ask: repo selector (remembered in `localStorage`), a guided composer with intent-labelled examples, optional "as of" date (`at`), and "Compare with vector-only search" (`mode: both`). The result card renders the answer with `[id]` citations as kind-coloured chips, copy-question/copy-answer actions, the evidence chain stepper, the supersession banner, the confidence meter with the reasons verbatim, the sources, "Why this answer" (route, Cypher calls with copy buttons, LLM backend/model/used, d3-force subgraph with SUPERSEDES dashed red and hover props), and the graph-vs-vector side-by-side when a baseline is present. Refusals get a muted card with the closest entities and the person to ask, and no confidence bar. |
| `/decisions/[id]` | The why-path: decision card, evidence with excerpts and links, the full chain older → newer as a vertical timeline, the motivating incident, implementing commits, and the Cypher. |
| `/pulse` | Knowledge Risk Radar: deterministic contradiction, drift, ownership, rationale, and staleness signals with evidence-backed scores and Ask/evidence-path actions. |
| `/timeline` | Date slider (earliest decision → today, debounced) with "In force on ‹date›" and "Superseded since then". |
| `/meetings`, `/meetings/[id]` | Handover calls; a meeting page with the audio player, speakers, utterances (Hinglish with the English rendering underneath, entity mentions, "play from here"), and the decisions extracted. A `501` from the API shows "KT ingestion not configured". |

Nav: Ask · Pulse · Timeline · Meetings · GitHub, with a health dot (`GET /health`; hover for Neo4j version/Aura, LLM backend, embedding backend). Light and dark follow `prefers-color-scheme`; tokens live in `src/app/globals.css`.

The API adds an `x-request-id` response header to every request. Errors from the API include the same value as `request_id`, which makes a user-facing failure easy to correlate with server logs. `GET /health` keeps the legacy fields and also reports `status`, a safe `graph` readiness summary, and `optional_backends` without exposing secrets.

## Layout of `src/`

```
app/                 routes (layout, page, decisions/[id], timeline, meetings, meetings/[id], not-found)
components/          Nav, HealthDot, RepoSelect/RepoContext, DecisionCard, Chip, states, pages
components/ask/      AskPage, AnswerCard, AnswerText, EvidenceChain, SupersessionBanner,
                     ConfidenceMeter, WhyPanel, Subgraph, BaselineCompare
lib/types.ts         the API contract from docs/CONTRACTS.md §6
lib/api.ts           fetch client (ApiError with status), sample-mode switch, link resolution
lib/sample.ts        fixture loader for sample mode
lib/hooks.ts         useResource, useStoredValue (localStorage via useSyncExternalStore), useDebounced
lib/format.ts        dates, kinds, labels
```
