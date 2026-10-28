# Kyun demo-first polish and hardening design

## Goal

Make Kyun feel like a finished product in its first five minutes: a visitor should understand the problem, ask a useful question, trust the evidence chain, and recover gracefully when a dependency is unavailable. Follow that with a small, compatibility-safe API hardening pass that improves diagnostics without changing answer or graph behavior.

## Current context

The repository already has a functioning FastAPI/Neo4j service and a Next.js 16 app. The graph answer model, sample fixtures, evidence chain, supersession handling, meetings, and timeline are implemented. The web app currently exposes those features, but the home screen is mostly a form, the result hierarchy is dense, and operational states are terse. The frontend builds and lint checks cleanly after installing the locked dependencies; Python tests pass with Neo4j-only tests skipped when no server is available.

## Design

### 1. First-run Ask experience

Keep `/` as the product entry point, but give it a clear narrative structure:

1. A compact editorial hero explains the promise in one sentence and names the evidence chain in plain language.
2. A highlighted Ask composer keeps repository, question, date, and baseline comparison controls together in one surface.
3. A small “how it works” strip shows the three concrete stages: history becomes a graph, the graph finds the active decision, and the answer cites the path it read.
4. Example questions remain one-click actions, but are presented as intent cards with short labels so visitors can choose by goal (decision, current value, owner, refusal) instead of scanning long strings.

The existing warm cream/orange visual language remains. New UI uses the existing CSS tokens and reusable classes rather than introducing a component framework.

### 2. Answer hierarchy and interaction polish

Keep the existing evidence and citation data untouched. Improve the presentation so the answer itself is the first focal point, metadata is scannable, and supporting panels are progressively disclosed:

- Add a clear result eyebrow for repository, date, and comparison mode.
- Make the answer card visually distinct from supporting evidence while preserving citation chips and links.
- Add a lightweight action row for copying the question and copying the answer text, with accessible status feedback.
- Keep evidence, supersession, confidence, sources, and “Why this answer” in the current order, but give each a stronger heading/spacing rhythm and mobile-safe overflow.
- Preserve refusal behavior and make the refusal reason/action (“closest entities” and “person to ask”) the primary content rather than an afterthought.

Copy actions are client-only and reversible. They must not expose hidden graph data or alter the API contract.

### 3. Responsive and accessibility behavior

- The composer, result metadata, evidence chain, and source rows must remain usable at narrow widths without horizontal page overflow.
- Interactive controls need visible labels, keyboard focus, disabled/busy states, and `aria-live` feedback for copy and answer loading.
- Decorative icons stay hidden from assistive technology; status and error messages remain in live/alert regions.
- Respect reduced-motion preferences for existing skeleton and any new transitions.

### 4. API hardening

Add operational signals around the existing API without changing route shapes or answer semantics:

- Add a request ID middleware/header so a user-facing error can be correlated with a server log entry.
- Include the request ID in the existing structured error envelope while keeping the `error` string backward compatible.
- Add a readiness-style health field that distinguishes process availability from graph reachability and reports configured optional backends without secrets.
- Add tests for request ID propagation and health response shape using the existing FastAPI test fixtures.

The API remains compatible with the current web client. No authentication, persistence, or new external service is introduced in this pass.

## Files and responsibilities

- `web/src/components/ask/AskPage.tsx`: first-run hero, composer surface, intent examples, loading/live-region wiring.
- `web/src/components/ask/AnswerCard.tsx`: answer result hierarchy and copy actions.
- `web/src/components/ask/CopyButton.tsx`: reuse or extend the existing copy primitive for explicit status feedback.
- `web/src/components/ask/EvidenceChain.tsx`, `web/src/components/ask/BaselineCompare.tsx`, `web/src/components/ask/WhyPanel.tsx`: only presentation-level spacing/overflow adjustments if needed.
- `web/src/components/states.tsx`: shared live-region and error-state semantics.
- `web/src/app/globals.css`: tokens/utilities for surfaces, responsive overflow, reduced motion, and polish.
- `src/kyun/api/main.py`: request ID middleware and error response metadata.
- `src/kyun/api/health.py` (new): pure health/readiness shaping so the endpoint stays small and testable.
- `tests/test_api.py`: API middleware and health contract coverage.
- `web/README.md`: update the user-visible behavior and validation commands.

## Verification

- `cd web && pnpm lint`
- `cd web && pnpm build`
- `uv run pytest`
- `uv run ruff check src tests`

The final review will include a narrow-width static inspection through the existing sample mode and a check that the API error envelope remains readable by the current `web/src/lib/api.ts` client.

