# Kyun Pulse knowledge risk radar design

## Goal

Turn Kyun from a system people query into a system that proactively identifies knowledge at risk: code that drifted away from its recorded decision, handover statements that contradict code, ownership that is concentrated or missing, and live decisions with too little rationale to safely change.

## Product behavior

`/pulse` is a repository-level dashboard. It presents a ranked queue of risk cards and a compact summary. Each card names the risk category, affected entity, active decision, owner, dates, and the evidence that triggered the score. The user can open the decision path or send the entity into the existing Ask composer.

The first release uses five deterministic signals:

1. **Contradiction:** a KT decision points to the active code decision through `CONTRADICTS`.
2. **Drift:** the related file/entity was touched after the active decision became valid.
3. **Ownership gap:** the decision has no stated person, or its stated person has no recent activity in the repository.
4. **Rationale gap:** the decision has neither a rationale nor an evidence relationship.
5. **Staleness:** the active decision is older than the configured radar window.

Scores are additive, clamped to `[0, 1]`, and accompanied by the exact reasons. The model never chooses a risk or a score. KT-only decisions are excluded from the code-risk list; they are used as contradiction and handover evidence against code decisions.

## API contract

`GET /pulse?repo=owner/name` returns:

```json
{
  "repo": "owner/name",
  "generated_at_iso": "…",
  "summary": {
    "active_decisions": 120,
    "risks": 8,
    "critical": 3,
    "coverage": 0.93,
    "contradictions": 1,
    "drift": 4,
    "ownership_gaps": 2
  },
  "risks": [
    {
      "id": "risk:…",
      "category": "contradiction",
      "score": 0.92,
      "reasons": ["Handover call contradicts the active code decision"],
      "entity": {"id": "…", "label": "ConfigKey", "name": "…", "path": "…"},
      "decision": {"…": "DecisionCard"},
      "owner": {"…": "PersonCard"},
      "evidence": [{"…": "Ref"}],
      "contradictions": [{"…": "Ref"}],
      "last_touched_iso": "…",
      "owner_last_active_iso": "…"
    }
  ]
}
```

Existing routes and `AskResponse` remain unchanged. The sample client returns a checked-in fixture through the same `api.pulse` method.

## Implementation boundaries

- `cypher/60_pulse.cypher` returns active non-KT decisions, their primary entity, owner, evidence, contradiction links, and timestamps. It computes signal booleans and a score in the query so the API does not infer facts from text.
- `src/kyun/pulse.py` owns pure category/score normalization and risk id generation.
- `src/kyun/answer/models.py` owns the JSON contract; `src/kyun/answer/service.py` owns graph access and mapping rows into models.
- `src/kyun/api/main.py` adds one thin endpoint.
- `web/src/components/PulsePage.tsx` and `web/src/components/PulseRiskCard.tsx` render the dashboard. The Ask page receives a small top-risk teaser; the full queue lives on `/pulse`.
- `web/sample/pulse.json` makes the feature work in sample mode with the current listmonk story, including a visible handover contradiction and ownership/rationale risks.

## Safety and performance

- Read-only query with a bounded result limit; no graph writes or new services.
- No secrets or raw transcript audio are returned; evidence excerpts are already bounded by existing graph projections.
- Risk cards link to existing decision/evidence pages, so every warning remains inspectable.
- Empty, unavailable, and sample states use the existing loading/error components.

## Verification

- Pure scoring tests cover each signal, clamping, category precedence, and stable ids.
- API tests cover `/pulse` mapping with a fake graph and request validation.
- Frontend lint/build must pass with sample mode enabled at build time.
- Full Python tests and ruff must remain green.

