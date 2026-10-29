# Untangle demo runbook

This five-minute tour uses `knadh/listmonk` as a public fixture repository. The handover transcript has fictional
speakers and illustrative rationale; call that out when showing a spoken explanation or ownership statement.

## Start in sample mode

Sample mode needs no API, Neo4j instance, or model key. From the repository root:

```bash
cd web
pnpm install --frozen-lockfile
NEXT_PUBLIC_UNTANGLE_SAMPLE=1 pnpm dev
```

Open `http://localhost:3000` and keep the **Sample data** banner visible. Questions replay the closest supported
recording, and the answer shows the recorded question. Unknown questions return the recorded refusal.

## Walkthrough

| Time | Page or action | What to explain |
|---|---|---|
| 0:00 | Ask | Engineers need the reason behind a value, not only the code that reads it. |
| 0:30 | Ask “why is app.concurrency set the way it is?” | Read the active decision, cited history, and labelled synthetic handover explanation. Open **Why this answer** to inspect query rows and the evidence subgraph. |
| 1:30 | Turn on **Compare with vector-only search** | Compare the graph's decision chain with passages returned by similarity. Point to the supersession dates and the sources actually used. |
| 2:15 | Ask “why does listmonk use MongoDB?” | Show the refusal and nearby context. No supporting decision is invented. |
| 2:45 | Meetings | Open the sample call, read an utterance, and follow a mentioned entity. Explain that spoken config statements confirm or contradict repository values without replacing code history. |
| 3:30 | Ask “who should I ask about internal/manager?” | Read authorship and review counts. Distinguish the real contributor ranking from the fictional ownership statement in the synthetic call. |
| 4:00 | Timeline and Pulse | Choose a historical date, then inspect the curated sample risk queue and its evidence actions. |
| 4:40 | Evaluation | Explain the small recorded gold set and its known misses. The saved figures are a historical snapshot, not a fresh benchmark from this tour. |

## Run against a live graph

Prepare Neo4j and `.env` as described in the [root README](../README.md). Then run:

```bash
uv sync --all-extras
uv run untangle schema
uv run untangle ingest knadh/listmonk
uv run untangle kt ingest --repo knadh/listmonk --transcript data/kt/listmonk-kt-sample.json
uv run untangle ask "why is app.concurrency set the way it is?" --repo knadh/listmonk
uv run untangle serve
```

Start the web app in a second terminal with sample mode unset:

```bash
cd web
pnpm dev
```

Use `NEXT_PUBLIC_UNTANGLE_API` in `web/.env.local` if the API is hosted somewhere other than
`http://localhost:8090`. Public web settings are applied at build time, so restart the development server or rebuild
a production client after changing them. The API's CORS origins must allow the web client's origin.

A live ingest can take time and consume GitHub API requests. Finish it before the tour and check `/health`; the web
client shows failures explicitly and does not fall back to sample mode automatically. A live run may differ from the
saved fixtures as repository history grows.

## Refresh the recorded results

With a reachable graph containing the repository and sample transcript:

```bash
uv run untangle eval --repo knadh/listmonk --gold eval/gold/listmonk.yaml
uv run python scripts/export_sample.py --repo knadh/listmonk
```

Review the generated files before committing. Keep synthetic labels intact, and report the evaluation timestamp,
backend, and gold-set limits when presenting metrics. See [EVAL.md](EVAL.md) and the [KT guide](../data/kt/README.md).
