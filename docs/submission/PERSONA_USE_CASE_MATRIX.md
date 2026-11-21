# Untangle — Persona Use Case Matrix

The problem: **the reason behind code is lost, so people and AI agents change it without knowing what it
protected against.** Live build: https://untangle.pallabdas.me. "Working" means the journey runs end to end on the
live build with a real account, real repository data and the Neo4j graph.

| User segment | Their version of the problem | Use cases | Feature that serves them | Status |
| --- | --- | --- | --- | --- |
| **Primary: engineering lead taking over an application in a team transition** (IT services firm or GCC; same customer as the Market Fit Canvas) | "The people who built this leave in 90 days. My new team needs the *why* behind the code, and the KT calls are hours of Hinglish recordings nobody can search." | 1. Ask why a config value, dependency or file is the way it is, with sources. 2. Upload a handover call and see each statement linked to code, confirmed or contradicted by history. 3. Find who to ask about a module. 4. Before someone leaves, see which decisions have no owner or no rationale. 5. Export an evidence brief for a review. | Repositories import, **Ask** (cited answers, refusal), **Meetings** (Hinglish transcription, extraction, CONFIRMS/CONTRADICTS), person to ask, **Pulse** knowledge-risk radar, **Timeline** and Markdown exports, **Map** for change impact | **Working** |
| **Segment 2: teams using AI coding agents** (Claude Code, Cursor) and the platform engineers who run them | "The agent confidently changes a value that was set for a reason it cannot see, and the next agent repeats the mistake." | 1. Before editing, the agent asks why a value or dependency is set and who knows. 2. The agent lists decisions and their history for a file. 3. After settling something, the agent records the decision so the next agent or engineer finds it. 4. The lead reviews what agents recorded. | **MCP server** on the same Neo4j graph (`ask_why`, `list_decisions`, `decision_timeline`, `who_to_ask`, `search_repository`, `remember_decision`, `recall_agent_notes`), **Agents page** for personal tokens and agent notes; notes supersede each other and never replace code evidence | **Working** (built at the finale) |
| **Segment 3: security and dependency owners** | "A CVE lands. Why is this version pinned, and is it safe to upgrade, or was the pin a workaround for a bug?" | 1. Trace a dependency's version history and the commit or PR behind each change. 2. See whether a pin was later superseded or reverted. 3. Check whether the upstream issue behind a workaround is fixed and the fix released. 4. Join advisories (CVE, exploited-in-the-wild) to pinned versions. | Lockfile decisions with supersession, Ask and `list_decisions` for dependencies (**working**); upstream evidence from OSV.dev, deps.dev, endoflife.date and GitHub releases (**planned**) | **Partial** |
| **Segment 4: compliance and audit owners** (SOC 2, ISO 27001, EU DORA, Cyber Resilience Act) | "Auditors sample changes and ask why each was made and who approved it." | 1. Export the reason and sources for decisions in a period. 2. Show what changed between two dates. | Timeline snapshot and Pulse evidence exports (**working**); PR-to-ticket-to-approval traceability and retention (**planned**) | **Partial** |

## Journeys an evaluator can run on the live build

**Primary segment (about 5 minutes):** create an account → Repositories → add a public GitHub repository (or open
an indexed one) → Ask "why is `<config key>` set to `<value>`?" and open a citation → Timeline: move the date back
and see the earlier value → Meetings: upload a transcript (JSON or `Speaker: words` lines) → open the call and its
extracted decisions → Pulse: filter risks and export the brief.

**Segment 2 (about 3 minutes):** Agents → create a token → run the shown command in Claude Code
(`claude mcp add --transport http untangle https://untangle.pallabdas.me/api/mcp --header "Authorization: Bearer …"`)
→ ask the agent "use untangle to explain why `<subject>` is set this way" → ask it to record a decision with
`remember_decision` → the note appears on the Agents page and in `list_decisions`, labelled as an agent note.
Without an agent, any MCP client (for example MCP Inspector) can connect with the same URL and header.

## How the architecture takes on the remaining use cases

Every segment reads and writes **one Neo4j graph** in which a `Decision` has a subject (`ABOUT` a file, key,
dependency or module), evidence (`DECIDED_IN`, `EVIDENCED_BY`), validity dates and a `SUPERSEDES` chain, and every
answer must cite nodes it actually retrieved. New use cases add evidence, not new reasoning:

- **Segment 3:** the scheduled worker adds `Advisory`, `PackageVersion`, `Release` and `ExternalIssue` nodes from
  free sources (OSV.dev, deps.dev, endoflife.date, GitHub issues, compare and releases), linked to existing
  `Dependency` and `Decision` nodes. "Can this pin go?" becomes a graph query: the decision's upstream issue is
  closed and the first release containing the fix is known. Designed in
  [the expansion research](../research/2026-11-21-expansion-research.md).
- **Segment 4:** add `Ticket` and `Approval` nodes from Jira or Linear and GitHub reviews, then export a signed
  evidence pack per period from the same Timeline queries.
- **Teams and private code:** an `Organisation` node scopes users, repositories and handover calls; a GitHub App
  installation supplies private repositories without sharing passwords.
- **Agents:** the MCP tools already sit on these queries, so every new evidence type is available to agents
  without new tools.
