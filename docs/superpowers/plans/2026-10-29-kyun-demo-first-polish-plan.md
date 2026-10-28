# Kyun demo-first polish and hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Kyun web app feel finished and trustworthy on first use, then add request-correlated API diagnostics without changing graph or answer semantics.

**Architecture:** Keep the existing Next.js pages and token-based CSS system. Improve the home/result components in place, extract only the API health/error shaping that needs independent tests, and preserve the existing client-facing route contracts. Client-only copy and live-region behavior stays inside the existing ask components.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, Tailwind 4, lucide-react, FastAPI, Pydantic, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-10-29-kyun-demo-first-polish-design.md`

## Global Constraints

- Keep the existing warm cream/orange visual identity and CSS token system.
- Do not change graph schema, answer composition, citation ids, or API route paths.
- Keep sample mode working without a running API or Neo4j instance.
- Do not add a component library or a new runtime dependency.
- Copy actions must be client-only and must expose accessible success/failure feedback.
- The API `error` string remains backward compatible; request IDs are additive metadata.
- Verify with `cd web && pnpm lint`, `cd web && pnpm build`, `uv run pytest`, and `uv run ruff check src tests`.

### Task 1: Establish the polished first-run Ask surface

**Files:**
- Modify: `web/src/components/ask/AskPage.tsx`
- Modify: `web/src/components/RepoSelect.tsx`
- Modify: `web/src/app/globals.css`

**Interfaces:**
- Consumes: existing `useRepo`, `api.ask`, `AskRequest`, and sample-mode behavior.
- Produces: the same `AskPage` request/result behavior with a more legible first-run layout.

- [ ] **Step 1: Add intent metadata for example prompts**

Replace the plain `string[]` examples with objects containing `label`, `question`, and `kind`, then render the existing five prompts as compact intent buttons. Keep the exact question strings so sample-mode matching remains unchanged.

- [ ] **Step 2: Group the composer into a surface**

Wrap repository selection, question input, date, comparison checkbox, and intent buttons in a `card` with a short helper line. Keep the existing form submit handler and disabled conditions unchanged.

- [ ] **Step 3: Add the “how Kyun works” strip**

Render three short, static steps below the composer using existing icon dependencies and semantic list markup. The copy must explain history → graph → cited answer in plain language and collapse to one column on narrow screens.

- [ ] **Step 4: Add loading and request status semantics**

Add an `aria-live="polite"` status adjacent to the form that announces when an answer is being requested and when it is ready. Preserve the existing skeleton visual and add CSS for reduced motion.

- [ ] **Step 5: Run focused frontend checks**

Run `cd web && pnpm lint` and `cd web && pnpm build`.

Expected: both commands pass with no TypeScript or eslint errors.

- [ ] **Step 6: Commit the first-run surface**

```bash
git add web/src/components/ask/AskPage.tsx web/src/components/RepoSelect.tsx web/src/app/globals.css
git commit -m "feat(web): clarify first-run ask experience"
```

### Task 2: Strengthen answer hierarchy and copy interactions

**Files:**
- Modify: `web/src/components/ask/AnswerCard.tsx`
- Modify: `web/src/components/CopyButton.tsx`
- Modify: `web/src/components/ask/EvidenceChain.tsx`
- Modify: `web/src/components/states.tsx`
- Modify: `web/src/app/globals.css`

**Interfaces:**
- Consumes: existing `AskResponse`, citation map, and `CopyButton` props.
- Produces: unchanged answer data rendering plus copy controls with accessible feedback.

- [ ] **Step 1: Inspect and pin the copy primitive contract**

Read `web/src/components/CopyButton.tsx` and keep its current public props compatible. If it has no status callback, extend it with an optional `label`/`value` contract that defaults to the current behavior.

- [ ] **Step 2: Add copy question and answer actions**

Place an action row under the answer heading. Copy the literal question and rendered answer text; use `navigator.clipboard.writeText`, catch failures, and show a transient `aria-live` label without throwing during SSR.

- [ ] **Step 3: Clarify result metadata**

Keep repository/date/comparison metadata in the existing header, but add a consistent uppercase eyebrow and separate the answer title from the content card. Do not alter citations or the `AnswerText` parser.

- [ ] **Step 4: Improve refusal emphasis**

Ensure the refusal card leads with the no-evidence state, then presents closest entities and person-to-ask content in readable sections. Keep the existing no-confidence explanation.

- [ ] **Step 5: Make supporting panels narrow-screen safe**

Adjust evidence-chain and source row classes so long ids/paths wrap or scroll within their own region. Add a reusable visually-hidden live status style if the components need it.

- [ ] **Step 6: Verify the result surface**

Run `cd web && pnpm lint && pnpm build` and inspect the sample fixtures by running the app in sample mode if needed.

- [ ] **Step 7: Commit answer polish**

```bash
git add web/src/components/ask/AnswerCard.tsx web/src/components/CopyButton.tsx web/src/components/ask/EvidenceChain.tsx web/src/components/states.tsx web/src/app/globals.css
git commit -m "feat(web): improve answer hierarchy and sharing"
```

### Task 3: Add request-correlated API diagnostics

**Files:**
- Create: `src/kyun/api/health.py`
- Modify: `src/kyun/api/main.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: existing `service.health()` result and FastAPI `Request`/`Response` lifecycle.
- Produces: `GET /health` with additive readiness fields, `x-request-id` response headers, and error bodies containing `request_id`.

- [ ] **Step 1: Write failing API tests**

Add tests that call the existing ASGI app with `TestClient` and assert:

```python
def test_request_id_is_echoed_and_added_to_errors(client):
    response = client.get("/decisions/missing")
    assert response.headers["x-request-id"]
    assert response.json()["request_id"] == response.headers["x-request-id"]

def test_health_exposes_process_and_graph_status(client, monkeypatch):
    response = client.get("/health")
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert "graph" in payload
    assert "optional_backends" in payload
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run `uv run pytest tests/test_api.py -q`.

Expected: the new assertions fail because the request id and readiness fields do not exist yet.

- [ ] **Step 3: Implement pure health shaping**

Create `health.py` with a typed function that accepts the existing health mapping and returns a mapping containing `status`, `graph`, and `optional_backends`. Do not include API keys or connection strings; report backend names/configured booleans only.

- [ ] **Step 4: Add request id middleware and error enrichment**

Generate a UUID per request unless an incoming `x-request-id` exists, set it on every response, and store it on `request.state`. Update `_error` and each exception handler to include the current request id through a small helper. Preserve status codes and the existing `error` field.

- [ ] **Step 5: Use the health shaper in `/health`**

Keep `service.health()` as the source of graph/backend facts and pass its result through the pure shaper. Do not make `/health` perform an extra graph query beyond what `service.health()` already does.

- [ ] **Step 6: Run backend checks**

Run `uv run pytest tests/test_api.py -q` and `uv run ruff check src tests`.

Expected: focused tests pass and ruff reports no new issues.

- [ ] **Step 7: Commit API diagnostics**

```bash
git add src/kyun/api/health.py src/kyun/api/main.py tests/test_api.py
git commit -m "feat(api): add request-correlated health diagnostics"
```

### Task 4: Documentation and full verification

**Files:**
- Modify: `web/README.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: final UI behavior and additive API health/error fields from Tasks 1–3.
- Produces: accurate setup and demo guidance for the polished experience.

- [ ] **Step 1: Document the new first-run flow**

Update the web page table and sample-mode section to mention intent cards, copy actions, and the evidence-first result layout.

- [ ] **Step 2: Document API diagnostics**

Add a short API note describing `x-request-id`, `request_id` in errors, and the `/health` readiness fields without suggesting any new secrets or services.

- [ ] **Step 3: Run the complete verification suite**

Run:

```bash
cd web && pnpm lint && pnpm build
cd .. && uv run pytest && uv run ruff check src tests
```

Expected: all commands pass; Neo4j-dependent tests may remain skipped when no Neo4j server is available.

- [ ] **Step 4: Review the final diff**

Run `git diff --check`, `git status --short`, and `git log --oneline -4` to confirm there are no generated artifacts or accidental dependency changes.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md web/README.md
git commit -m "docs: describe polished demo and API diagnostics"
```

