# Untangle graph model

Untangle connects code entities to the decisions, evidence, and people that explain them. It uses Neo4j so retrieval
can follow explicit relationships and decision dates rather than treating every matching passage as equally current.

## A question becomes an evidence path

The following is an illustrative path, not a claim about the sample repository's pull request numbers or history:

```text
(ConfigKey retry_limit) <-[:ABOUT]- (Decision "retry_limit is 3")
      -[:DECIDED_IN]-> (PullRequest "Reduce retries after duplicate delivery")
      -[:CLOSES]-> (Issue :Incident "Duplicate deliveries after timeout")
(Decision) -[:STATED_BY]-> (Person)
(Decision) -[:IMPLEMENTED_BY]-> (Commit)
```

The answer service resolves the entity, reads decisions through `31_decisions_about`, and retrieves evidence with
`32_why_path`. The API returns citations, a route, query row counts, and the subgraph, so a reader can inspect how an
answer was formed. Missing relations remain missing; the service does not invent a motivating incident or rationale.

## Decisions retain their history

Each decision has a key, value, status, and two sets of timestamps:

| Fields | Meaning |
|---|---|
| `valid_from`, `valid_to` | When the decision's value was in force in repository history. |
| `created_at`, `expired_at` | When the graph learned the decision and recorded its supersession. |

A later value on the same key expires the previous active decision and links to it with `SUPERSEDES`. The earlier
node and evidence stay readable. The `33_belief_at` query selects values in force at a requested time, while
`32_why_path` exposes the chain. Same-key ingestion runs in chronological rounds to keep these transitions ordered.

| Signal | Evidence that creates or connects decisions |
|---|---|
| `config_diff` | A scalar configuration value changed in Git history. |
| `lockfile_diff` | A dependency version changed or was removed. |
| `revert_commit` | A commit explicitly reverted an earlier change. |
| `adr_status` | An ADR records a changed status or an explicit successor. |
| `supersedes_text` | PR or commit text explicitly references a replaced decision. |
| `llm_pr_thread`, `llm_kt`, `heuristic_kt` | Extracted rationale linked to source evidence; model extractions must retain a supporting quote. |

Full-text and vector retrieval help locate relevant material, but decision validity and supersession come from the
graph. The vector-only baseline deliberately omits this temporal logic so the evaluation can compare the approaches.

## Handover statements remain distinct

Spoken decisions use `kt|…` keys. A later call can supersede a statement from an earlier call, but cannot replace the
repository's code-history decision. `24_reconcile_kt` links spoken configuration values to active repository values:

| Relationship | Meaning in an answer |
|---|---|
| `CONFIRMS` | The call and repository agree; the call can provide additional rationale. |
| `CONTRADICTS` | The call and repository disagree; the answer names the conflict and lowers confidence. |

The synthetic sample call demonstrates both outcomes. Its fictional speakers and rationale are marked in the fixture;
they are not statements by real maintainers.

## Identity and ownership

A `File` node represents one historical path. `RENAMED_FROM {at, sha}` retains detected rename history. An `Identity`
node maps an email, GitHub login, or meeting speaker to a `Person`, allowing contributor and meeting evidence to share
an identity when a matching login or email is provided.

`34_person_to_ask` ranks paths from people to the resolved entity: authorship, reviews, review comments, and stated
decisions, weighted by recency. Counts are returned with the result so the recommendation can explain its basis.
A ranked contributor is a useful contact suggestion, not proof of current responsibility or availability.

## Graph boundaries

| Area | Contract |
|---|---|
| Isolation | Repository-scoped nodes carry `repo`; multiple repositories can share a database. |
| Queries | Numbered files in `cypher/` are the source of truth and are also bundled in Python wheels. |
| Neo4j features | Constraints plus range, full-text, and vector indexes; no APOC or GDS dependency. |
| Timestamps | Epoch milliseconds in graph storage; ISO-8601 companion fields in API responses. |
| Updates | Deterministic IDs and `MERGE` make repeated ingestion idempotent. |
| Explanations | Citations and query traces expose the evidence actually read by the answer service. |

See [CONTRACTS.md](CONTRACTS.md) for the complete node properties, relationships, CLI commands, and API shapes, and
[EVAL.md](EVAL.md) for the recorded evaluation and its limits.
