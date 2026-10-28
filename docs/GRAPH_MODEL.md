# Why a graph, and this graph in particular

The Neo4j track asks each team to explain its graph model and why a graph fits the problem. This is Untangle's answer.

## The question is a path

"Why is `app.concurrency` 10?" is answered by one walk:

```
(ConfigKey app.concurrency) <-[:ABOUT]- (Decision "app.concurrency is 10")
      -[:DECIDED_IN]-> (PullRequest #812 "Throttle sends after SES errors")
      -[:CLOSES]-> (Issue #790 :Incident "Campaign stalls with 454 throttling")
(Decision) -[:STATED_BY]-> (Person Kailash Nadh)
(Decision) -[:IMPLEMENTED_BY]-> (Commit 3fa2c1d, 2023-03-14)
```

Every hop is a different table in a relational design (keys, decisions, pull requests, issues, people,
commits) and each hop is a join. In the graph it is one pattern, `cypher/31_decisions_about.cypher`,
and it comes back in milliseconds with the evidence attached. The organisers' own brief says this is
"a graph problem end to end, because the value sits in the relationships and not in the text".

## Supersession is a chain with time on it

Decisions are bi-temporal, the project's temporal graph model: `valid_from`/`valid_to` say when a value
was in force, `created_at`/`expired_at` say when Untangle learned about it. A newer decision with the same `key`
and a different value expires the older one and links to it:

```
(Decision "concurrency is 10", active, valid_from 2023-03-14)
   -[:SUPERSEDES {signal: 'config_diff'}]-> (Decision "concurrency is 5", superseded, valid 2021-06-02 → 2023-03-14)
```

Nothing is overwritten. "What did the team believe on 2022-05-01?" is a range filter along the chain
(`33_belief_at`). "Do we still use exponential backoff?" is "is the newest decision on this key the one
you are quoting?". A vector store cannot represent this: it would return the 2021 text and the 2023 text
as two equally confident hits, and the brief names exactly that failure ("a decision that was reversed
two years later still sits in the archive looking authoritative").

Supersession signals are deterministic wherever possible, because the judges reward "evidence that the
graph structure, and not the model, is doing the work":

| Signal | What it links |
|---|---|
| `config_diff` | the same dotted key with a new scalar value in a later commit |
| `lockfile_diff` | the same dependency with a new version (or removed) |
| `revert_commit` | `Revert "…"` / `This reverts commit …` → the reverted change's decisions |
| `adr_status` | an ADR whose status says `Superseded by ADR-0007` |
| `supersedes_text` | "supersedes #N", "replaces #N" in PR or commit text |
| `llm_pr_thread`, `llm_kt`, `heuristic_kt` | model- or rule-extracted rationale, always with a quote that must exist in a source node |

## Speech and code are reconciled, not merged

A handover call is valuable because it carries the reason a commit message leaves out, and dangerous because
people misremember. Untangle keeps spoken decisions on their own keys (`kt|…`) and links each one to the repository's
active record on the same subject: `(kt)-[:CONFIRMS]->(code)` when the values agree, `(kt)-[:CONTRADICTS]->(code)`
when they do not. An answer then leads with the code, adds the call's reason when it confirms, and says the two
conflict when it does not. That judgement is a relationship, not a prompt.

## Entity resolution is graph clustering

The brief calls it "the hard part": the same module carries four names across five years. Untangle keeps
one `File` node per historical path and records `(File)-[:RENAMED_FROM {at, sha}]->(File)` from git's
rename detection; a question about today's path reaches every decision made under the old names by
following the chain. People are resolved the same way: `Identity` nodes (emails, GitHub logins, meeting
speaker labels) point at one `Person`, so a commit author, a PR reviewer and the voice on a handover
call become the same node.

## "Person to ask" is centrality

`34_person_to_ask` ranks people by recency-weighted paths to the entity: commits that touched it,
reviews of PRs that touched it, review comments on its lines, decisions they stated. The score's parts
are returned so the UI can say "authored 12 of 20 commits on this file, reviewed 4 PRs". It is the
truck-factor idea (Avelino et al., ICPC 2016) expressed as a two-hop query.

## Impact is reachability

A superseded decision that still has code `IMPLEMENTED_BY` commits nobody reverted, or a KT statement
that contradicts the active value, is one more pattern. The web app's timeline and the "Supersession"
banner come from the same queries the answer uses, so what the judge sees is what the model was given.

## What runs where on AuraDB

Untangle uses only what AuraDB Free offers: one database, unique constraints, range, full-text and vector
indexes. No APOC, no GDS, no CDC. Every node carries `repo` so several repositories share one instance.
The vector index exists for the **baseline**, not the product: the side-by-side in the UI runs the same
question through vector-only retrieval to show that it quotes the dead decision.

## Node and relationship inventory

See `docs/CONTRACTS.md` §2 for properties. Labels: Repo, Person, Identity, Commit, File, Module, Symbol,
ConfigKey, Dependency, PullRequest, Issue (+Incident), Comment, Document, Chunk, Decision, Meeting,
Utterance. Relationship types: AUTHORED, COMMITTED, TOUCHED, RENAMED_FROM, IN, DEFINED_IN, SET_IN,
DECLARED_IN, PART_OF, REVERTS, OPENED, REVIEWED, ON, WROTE, ABOUT_LINE, CLOSES, REFERENCES, STORED_AS,
SUPERSEDED_BY, FROM, ABOUT, DECIDED_IN, EVIDENCED_BY, STATED_BY, IMPLEMENTED_BY, MOTIVATED_BY,
SUPERSEDES, CONFIRMS, CONTRADICTS, HAS, NEXT, SPOKEN_BY, MENTIONS, ABOUT_REPO, IDENTITY_OF.
