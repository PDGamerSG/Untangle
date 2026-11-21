# Untangle — Finale Build Plan

**Team:** Untangle · **Live build:** https://untangle.pallabdas.me (mirror: https://untangle-code.vercel.app)
**Repository:** https://github.com/PDGamerSG/Untangle · **Submitted:** 21 November 2026

## The product in one line

Untangle answers "why is the code like this?" from a Neo4j knowledge graph of a repository's history and its
recorded handover calls, cites the evidence for every answer, shows when a decision was replaced, and refuses when
the evidence is not there.

## Where we start the finale

| Area | State on 21 November |
| --- | --- |
| Primary workflow | Live: import a public GitHub repository, then Ask (cited answers or refusal), Timeline, Pulse (knowledge risks), Map (feature and commit impact), Meetings (Hinglish handover calls) and exports. |
| Neo4j | Core of the product: bi-temporal decisions with `SUPERSEDES` chains, `CONFIRMS`/`CONTRADICTS` between handover calls and code, full-text and vector indexes, durable import queue. |
| Security release | Built, tested and pushed, **not yet deployed**: accounts and sessions, per-user limits, ownership of uploads, security headers, private API docs, safe errors. Deployed after the ArgosX baseline scan. |
| Tests | 299 backend and 53 browser tests pass; CI green on `main`. |

## What we will build and deliver at the finale

| # | Deliverable | Gate or criterion | Done when |
| --- | --- | --- | --- |
| 1 | **ArgosX baseline scan** of the current live build; download the report | Submission gate | Report saved before the security release goes live |
| 2 | **Deploy the security release** (accounts, limits, headers, safe errors) to both domains | Security, authentication | Live suite passes on both domains |
| 3 | **Neo4j agent memory over MCP**: coding agents (Claude Code, Cursor) connect with a personal token and use graph tools: `why`, `decisions_for`, `timeline`, `who_to_ask`, `search`, and `remember_decision`, which writes an agent's decision into the graph with supersession and provenance | Partner technology (Neo4j: knowledge graph, GraphRAG, agent memory); second user segment | An MCP client lists the tools, gets cited answers and refusals, and a remembered decision appears in Timeline |
| 4 | **Agent access page**: create, list and revoke personal tokens; ready-to-paste connection command | Second segment's journey in the live build | Token works for MCP and is revoked instantly |
| 5 | **Fix ArgosX findings**: critical and high first, then medium | Security improvement | Final scan by 11 AM on 22 November; report downloaded |
| 6 | **Remediation log**: what was found, fixed, what remains and why | Risk understanding | One page, mapped to both reports |
| 7 | **Market Fit Canvas** (one page) | Validate the market | Every parameter backed by a number or a source |
| 8 | **3 Customer Test**: three people from the target segment during the finale | Validate the market | For each: assumption, finding, product change; pre-finale research labelled separately |
| 9 | **Persona Use Case Matrix**: three segments, two or more use cases each | Expand impact | Primary and agent segments working live; third segment partial with an architecture path |

## Segments

1. **Primary — engineering leads and new engineers who inherit a codebase** in Indian IT services firms and global
   capability centres (handover after attrition, vendor transitions). Live today: import, Ask, Timeline, Pulse,
   Meetings with Hinglish handover calls.
2. **AI coding agents and the platform teams that run them.** Built at the finale: Neo4j decision memory over MCP.
3. **Security and dependency owners** asking "why is this version pinned and can we change it?" Partial: dependency
   decisions and their history are live; upstream advisory and release evidence is the next build.

## Schedule (IST)

| Time | Milestone |
| --- | --- |
| 21 Nov, by 18:00 | ArgosX baseline scan and report |
| 21 Nov, by 20:00 | Security release deployed; live suite green on both domains |
| 21 Nov, by 23:30 | MCP agent memory and agent access page built and tested |
| 22 Nov, by 02:00 | Deployed; ArgosX findings triaged and critical/high fixed |
| 22 Nov, during the day | Three customer conversations; canvas and matrix updated with what we learn |
| 22 Nov, by 11:00 | Final ArgosX scan, report, remediation log; all documents submitted |

## How we verify

Local: `uv run pytest`, `pnpm lint`, `pnpm build`, browser tests. Live: `pnpm test:production` against both
domains after every deploy, with results recorded per domain. Nothing is called done until it works on the live
build.

## Risks

| Risk | Mitigation |
| --- | --- |
| Deploy breaks the live demo | Deploy to a preview URL first, run the live suite there, then promote. Previous release stays available to roll back. |
| Requiring sign-in slows evaluators | Sign-up takes about ten seconds; the landing page links straight to it. |
| Agent tools misuse or abuse | Personal tokens stored as hashes, revocable, per-user limits, agent-written decisions labelled and attributed. |
| Scheduled import worker delays | Shown honestly in the UI with wait estimates; an always-on worker is on the roadmap. |
