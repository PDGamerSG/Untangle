# Kyun Pulse knowledge risk radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, evidence-backed knowledge risk radar that works in live and sample mode and is visible from the main Ask experience.

**Architecture:** Compute risk signals in a bounded Neo4j read query, normalize scores and ids in a pure Python module, map rows through the existing answer service and Pydantic contracts, then render a dedicated Next.js dashboard plus a small Ask teaser. Keep the existing answer, timeline, and meeting routes unchanged.

**Tech Stack:** Neo4j Cypher, Python 3.12, FastAPI, Pydantic 2, pytest, Next.js 16, React 19, TypeScript, Tailwind 4, lucide-react.

**Spec:** `docs/superpowers/specs/2026-10-29-kyun-pulse-design.md`

## Global Constraints

- Risk scores are deterministic and every returned risk includes human-readable reasons.
- Exclude `Decision.kind = 'kt'` from the active code-risk roots; use KT decisions only as contradiction evidence.
- Do not change existing answer, timeline, meeting, or graph-ingestion semantics.
- Do not add a runtime dependency or require Neo4j in sample mode.
- Keep risk query results bounded (`limit` defaults to 24 and is capped at 50).
- Preserve the current warm editorial visual system and responsive behavior.
- Verify with `uv run pytest`, `uv run ruff check src tests`, `cd web && pnpm lint`, and `cd web && pnpm build`.

### Task 1: Add Pulse domain models and deterministic scoring

**Files:**
- Create: `src/kyun/pulse.py`
- Modify: `src/kyun/answer/models.py`
- Test: `tests/test_pulse.py`

**Interfaces:**
- Consumes: raw signal maps from the Cypher query.
- Produces: `PulseRisk`, `PulseSummary`, `PulseResponse`, and pure helpers for score/category/id generation.

- [ ] **Step 1: Write failing pure scoring tests**

Cover contradiction precedence, additive score clamping, ownership/rationale/stale reasons, stable risk ids, and summary counts. Example assertion:

```python
signals = {"contradiction": True, "drift": True, "ownership_gap": False, "rationale_gap": False, "stale": False}
assert classify(signals) == "contradiction"
assert score(signals) == 0.88
```

- [ ] **Step 2: Run the focused tests to confirm they fail**

Run `uv run pytest tests/test_pulse.py -q`.

Expected: import/function failures because the domain module does not exist.

- [ ] **Step 3: Implement pure helpers and Pydantic models**

Add typed `SIGNAL_WEIGHTS`, `classify(signals)`, `score(signals)`, `risk_id(repo, decision_id, entity_id)`, reason generation, and model classes. Keep `PulseRisk.decision` as the existing `DecisionCard` shape and evidence as existing `Ref` cards.

- [ ] **Step 4: Run focused tests**

Run `uv run pytest tests/test_pulse.py -q`.

Expected: all focused tests pass.

- [ ] **Step 5: Commit domain contract**

```bash
git add src/kyun/pulse.py src/kyun/answer/models.py tests/test_pulse.py
git commit -m "feat: add deterministic pulse risk contract"
```

### Task 2: Query and expose live Pulse data

**Files:**
- Create: `cypher/60_pulse.cypher`
- Modify: `src/kyun/answer/service.py`
- Modify: `src/kyun/api/main.py`
- Modify: `tests/test_api.py`
- Test: `tests/test_pulse.py`

**Interfaces:**
- Consumes: `PulseResponse` and pure helpers from Task 1; existing `Graph.run_named`/`Recorder` conventions.
- Produces: `service.pulse(repo, graph=None, now_ms=None, limit=24) -> PulseResponse` and `GET /pulse?repo=`.

- [ ] **Step 1: Add a bounded Cypher query**

Return one row per active non-KT decision/entity with nested entity/decision/owner/evidence/contradiction maps, `last_touched`, `owner_last_active`, booleans for the five signals, and an active-decision count. Order by deterministic score descending and limit to 50.

- [ ] **Step 2: Add service mapping tests with a fake graph**

Feed `service.pulse` rows containing one contradiction and one drift case; assert the response maps `DecisionCard`, owner, evidence, ISO timestamps, score, and summary counts correctly.

- [ ] **Step 3: Implement service mapping**

Call `run_named("pulse", {repo, now, stale_before, owner_stale_before, limit})`, normalize rows through `version_from_row`/`decision_card`/`ref_card`, create `PulseRisk` objects, filter zero-score rows, and build summary counts with `coverage = (active_decisions - risks) / active_decisions`.

- [ ] **Step 4: Add the FastAPI route**

Add `@app.get("/pulse", response_model=PulseResponse)` with `repo: Query(min_length=3)` and an optional bounded `limit` query parameter. Preserve existing graph error handlers.

- [ ] **Step 5: Add API contract tests**

Assert `/pulse` appears in OpenAPI and a mocked service response serializes with `summary`, `risks`, `score`, and `reasons`.

- [ ] **Step 6: Verify backend**

Run `uv run pytest tests/test_pulse.py tests/test_api.py -q` and `uv run ruff check src tests`.

- [ ] **Step 7: Commit the live API**

```bash
git add cypher/60_pulse.cypher src/kyun/answer/service.py src/kyun/api/main.py tests/test_api.py tests/test_pulse.py
git commit -m "feat(api): expose repository knowledge risks"
```

### Task 3: Add sample mode and client contracts

**Files:**
- Create: `web/sample/pulse.json`
- Modify: `web/src/lib/types.ts`
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/lib/sample.ts`

**Interfaces:**
- Consumes: `/pulse` API response shape and existing sample decision cards.
- Produces: `PulseResponse` TypeScript type and `api.pulse(repo)` with live/sample implementations.

- [ ] **Step 1: Create a realistic listmonk Pulse fixture**

Include three risks: a KT contradiction around `smtp.my0.max_msg_retries`, an ownership gap around `internal/manager`, and a rationale/drift risk around `docker-compose.yml`. Reuse ids and evidence excerpts from `web/sample/decisions.json` where possible.

- [ ] **Step 2: Add TypeScript models and API method**

Add `PulseEvidence`, `PulseRisk`, `PulseSummary`, `PulseResponse`, and `api.pulse(repo, signal)`; in sample mode return `samplePulse(repo)`.

- [ ] **Step 3: Add sample loader and validation**

Load the JSON fixture, replace the repo field with the selected repo for the same behavior as `sampleAsk`, and keep delays consistent with existing sample calls.

- [ ] **Step 4: Run frontend checks**

Run `cd web && pnpm lint && pnpm build`.

- [ ] **Step 5: Commit sample/client support**

```bash
git add web/sample/pulse.json web/src/lib/types.ts web/src/lib/api.ts web/src/lib/sample.ts
git commit -m "feat(web): add pulse sample contract"
```

### Task 4: Build the Pulse dashboard and Ask teaser

**Files:**
- Create: `web/src/app/pulse/page.tsx`
- Create: `web/src/components/PulsePage.tsx`
- Create: `web/src/components/PulseRiskCard.tsx`
- Modify: `web/src/components/Nav.tsx`
- Modify: `web/src/components/ask/AskPage.tsx`
- Modify: `web/src/app/globals.css`

**Interfaces:**
- Consumes: `useRepo`, `api.pulse`, `PulseResponse`, existing `ErrorState`, `Skeleton`, `SectionTitle`, `EntityChip`, and `hrefFor` conventions.
- Produces: responsive `/pulse` route, accessible risk cards, and a compact top-risk teaser on `/`.

- [ ] **Step 1: Build reusable risk card**

Render category/score, affected entity, decision summary, owner, reasons, evidence count, and actions. Link the decision id to `/decisions/[id]`; make Ask action route to `/` with a query string that AskPage can consume.

- [ ] **Step 2: Build page summary and states**

Show a “knowledge coverage” summary, contradiction/drift/ownership counts, risk queue, loading skeleton, empty state, and retry error. Use RepoSelect compact and existing `useResource` patterns.

- [ ] **Step 3: Add navigation and Ask teaser**

Add Pulse to primary nav and render the top three risks under the Ask composer when data is available. Keep the Ask form usable when Pulse fails.

- [ ] **Step 4: Add query-string handoff**

Use `useSearchParams` in AskPage to prefill a risk-generated question when the user clicks Ask. Do not auto-submit; let the user review and send it.

- [ ] **Step 5: Add visual and motion polish**

Add category colors, score meter, risk card hover/focus treatment, responsive stacking, and reduced-motion-safe transitions using existing tokens only.

- [ ] **Step 6: Verify frontend**

Run `cd web && pnpm lint && pnpm build`.

- [ ] **Step 7: Commit the dashboard**

```bash
git add web/src/app/pulse/page.tsx web/src/components/PulsePage.tsx web/src/components/PulseRiskCard.tsx web/src/components/Nav.tsx web/src/components/ask/AskPage.tsx web/src/app/globals.css
git commit -m "feat(web): launch knowledge risk radar"
```

### Task 5: Document and run full verification

**Files:**
- Modify: `README.md`
- Modify: `web/README.md`
- Modify: `docs/CONTRACTS.md`
- Modify: `docs/DEMO.md`

**Interfaces:**
- Consumes: final Pulse API/UI behavior.
- Produces: accurate product story, demo flow, and API contract.

- [ ] **Step 1: Document Pulse in the product story**

Update the “What we built” and roadmap sections to describe the live risk radar and its deterministic signals.

- [ ] **Step 2: Document `/pulse` and sample mode**

Update the web route table and sample fixture list.

- [ ] **Step 3: Add the API contract**

Document `GET /pulse` fields and the score explanation rule.

- [ ] **Step 4: Update the five-minute demo**

Add a 30-second Pulse beat before Ask: open the risk queue, click a contradiction, then ask the generated question.

- [ ] **Step 5: Run all checks**

Run:

```bash
uv run pytest
uv run ruff check src tests
cd web && pnpm lint && pnpm build
git diff --check
```

- [ ] **Step 6: Commit docs and inspect status**

```bash
git add README.md web/README.md docs/CONTRACTS.md docs/DEMO.md
git commit -m "docs: add Kyun Pulse product and demo flow"
git status --short
```

