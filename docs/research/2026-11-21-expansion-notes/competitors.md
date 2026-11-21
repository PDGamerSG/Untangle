# Competitor and adjacent products to Untangle (as of 21 November 2026)

Scope note: research was done on 21 Nov 2026 with web search and fetches of vendor pages. Many pricing figures come from third-party trackers (PricingSaaS, UsagePricing, aggregators) because vendors often do not publish them. Where a vendor page was fetched directly it is marked "(vendor page, fetched Nov 2026)". Older information is dated inline. Vendor claims such as benchmarks and testimonials are self-reported.

## 1. Which products compete with or overlap Untangle?

### Takeaway
The closest direct competitor is **Unblocked**. It ingests code, PRs, Jira/Linear, Confluence/Notion, Slack/Teams and meeting notes (Fireflies, Granola), gives cited answers about "your software and its history", and advertises "reference obsoletion" and "conflict resolution" across sources. Around it are four adjacent clusters: (a) auto-generated repository wikis (DeepWiki, Google Code Wiki, Mintlify Autopilot, Dosu, Driver); (b) context engines and code search for agents (Sourcegraph, Augment, Qodo Aware, Glean, GitHub Copilot Spaces and Memory); (c) AI PR reviewers that build a "learnings" knowledge base (CodeRabbit, Greptile, Rovo Dev, Macroscope); (d) behavioural/ownership analytics and developer portals (CodeScene, Port, Backstage, Cortex). A new 2026 category records the "why" of agent-written code at commit time (Entire Checkpoints, Cursor Blame / Agent Trace, Copilot Memory). Several small open-source "git why" tools also appeared. Swimm has largely moved out of code docs into legacy-modernisation services.

### Cited Findings
**Direct overlap ("why", history, cited answers across tools)**
- Unblocked calls itself "the context layer for agentic software development" and supplies cited, organisation-specific context to agents and developers. It ingests GitHub/GitLab/Bitbucket/Azure DevOps code and PRs, CI, Confluence/Notion/Google Drive/SharePoint, Jira/Linear/Asana, Slack/Teams/Zendesk, meeting tools Fireflies and Granola, Datadog/Sentry, and "External websites" listed under documentation — [Unblocked AI info page, updated 13 Nov 2026](https://getunblocked.com/ai-info/index.md)
- Unblocked describes grounding answers in past decisions, discussions, incidents and PR history, with "reference obsoletion" (flagging outdated information) and conflict resolution across sources. It does not describe a dedicated decision log — [Unblocked AI info page](https://getunblocked.com/ai-info/index.md)
- Unblocked raised a $20M Series A (B Capital, Radical Ventures, Artisanal Ventures) in May 2025. It is based in Vancouver and came out of stealth in Oct 2023 — [TechCrunch, 6 May 2025](https://www.techcrunch.com/2025/05/06/unblocked-raises-20-million-for-its-ai-assistant-to-help-devs-understand-legacy-codebases); [BetaKit](https://betakit.com/unblocked-raises-27-5-million-series-a-to-make-sure-developers-actually-understand-their-code/)
- Unblocked's own pitch is that it gives agents "the decisions, discussions, and history scattered across GitHub, Slack, Jira, and Confluence" — [Unblocked Series A blog](https://getunblocked.com/blog/series-a/index.md)

**Auto-generated repo wikis / documentation agents**
- DeepWiki (Cognition) generates wikis for public GitHub repos. Its MCP server (`https://mcp.deepwiki.com/mcp`) is free, remote and needs no authentication for public repos. Private repos need a Devin account and the Devin MCP server with an API key — [Cognition blog: DeepWiki MCP server](https://cognition.ai/blog/deepwiki-mcp-server); [Devin docs](https://docs.devin.ai/work-with-devin/deepwiki-mcp)
- Google Code Wiki launched in public preview on 13 Nov 2025 for public repos. It regenerates docs after each code change, auto-generates architecture, class and sequence diagrams, and hyperlinks every wiki section and chat answer to code files and definitions — [Google Developers Blog](https://developers.googleblog.com/en/introducing-code-wiki-accelerating-your-code-understanding/)
- Code Wiki's Gemini CLI extension for private repos was still waitlisted as of 6 May 2026 (third-party guide). I found no evidence that it has launched since — [Smartscope guide](https://smartscope.blog/en/generative-ai/google-gemini/google-code-wiki-repository-documentation-guide/); [Google Developers Blog](https://developers.googleblog.com/en/introducing-code-wiki-accelerating-your-code-understanding/)
- Mintlify Autopilot is an always-on agent that watches connected repos and tools such as Slack, drafts doc updates and opens PRs for review. Each PR it opens or updates costs 250 credits. A third-party aggregator dates the beta to 20 Oct 2026 for Pro/Enterprise — [Mintlify blog: Autopilot](https://mintlify.com/blog/autopilot); [Mintlify changelog](https://mintlify.com/docs/changelog)
- Dosu offers Self-Documenting PRs that detect documentation gaps when code changes and update the docs. It integrates with GitHub, GitLab, Confluence, Notion, Slack and Microsoft Teams. In Q1 2026 PricingSaaS described it as having "pivoted from issue tracking to documentation tools" — [EveryDev listing](https://www.everydev.ai/tools/dosu); [PricingSaaS Dosu 2026Q1](https://pricingsaas.com/companies/dosu/diffs/2026Q1)
- Driver (Driver AI, Austin, founded 2023) raised an $8M seed led by GV in Oct 2024. It breaks codebases into components for LLM documentation and exposes a "compiler-inspired" codebase context through MCP or API — [PR Newswire, Oct 2024](https://prnewswire.com/news-releases/driver-launches-with-8m-in-seed-funding-led-by-gv-to-simplify-technical-documentation-and-speed-product-time-to-market-302269404.html); [YC launch](https://www.ycombinator.com/launches/Pqj-driver-context-for-codebases)
- Swimm now sells "agentic modernization" (Application Delivery, System Intelligence, AI Operability) built on a "grounding layer". A deterministic engine maps flows and extracts business rules, an LLM explains them, and expert pods verify. The vendor claims 95%+ accuracy, and agents reach the layer over MCP — [Swimm pricing page, fetched Nov 2026](https://swimm.io/pricing)
- Swimm 2.0 was introduced in May 2026 as "the understanding platform for AI modernization", with a COBOL/mainframe focus — [Swimm blog via search](https://swimm.io/blog); [Swimm COBOL post](https://swimm.io/blog/blackbox-to-blueprint-illuminating-cobol-systems)

**Context engines / code search for agents**
- Sourcegraph spun Amp out as an independent company in Dec 2025. Sourcegraph kept code search and Deep Search (agentic search across mono- and multi-repo codebases) — [Sourcegraph blog](https://sourcegraph.com/blog/why-sourcegraph-and-amp-are-becoming-independent-companies); [Wikipedia](https://en.wikipedia.org/wiki/Sourcegraph)
- Sourcegraph's pricing page lists only Enterprise, "Starting at $16K" a year. It includes Code Search, Deep Search, code insights and monitoring, Batch Changes, an MCP server, APIs and a CLI, plus self-hosted or single-tenant cloud deployment and pooled AI credits. Cody is not mentioned — [Sourcegraph pricing, fetched Nov 2026](https://sourcegraph.com/docs/pricing)
- Augment's Context Engine became available as an MCP server on 6 Feb 2026 for Cursor, Claude Code, Zed and other MCP clients; a changelog entry marks the MCP as GA — [Augment blog](https://augmentcode.com/blog/context-engine-mcp-now-live); [Augment changelog](https://www.augmentcode.com/changelog/context-engine-mcp-in-ga)
- Qodo's Context Engine/Aware combines LSP analysis, knowledge graphs and vector embeddings. Its MCP tools include `deep_research` across repositories with follow-up sessions. Qodo reports 80% fact recall against Codex 74%, Claude Code 64% and Gemini CLI 45% on its own open benchmark — [Qodo docs](https://docs.qodo.ai/developer-tools/context-engine-mcp-tools); [Qodo blog](https://www.qodo.ai/blog/introducing-qodo-aware-deep-codebase-intelligence-for-enterprise-development); [PR Newswire](https://www.prnewswire.com/il/news-releases/qodo-unveils-top-deep-research-agent-for-coding-outperforming-leading-ai-labs-on-multi-repository-benchmark-302552359.html)
- Glean's GitHub connector indexes repos and metadata, source files, commits, READMEs, and issues and issue comments. Code Search is on by default and is also exposed through Glean's MCP server to Claude Code and Cursor. The connector is marked Beta — [Glean docs: GitHub connector](https://docs.glean.com/connectors/native/github/); [Glean docs: Code Search](https://docs.glean.com/user-guide/assistant/code-search)
- GitHub Copilot Spaces collect repos, files, PRs, issues and docs as context, can be shared org-wide, and are reachable from the IDE through the remote GitHub MCP server. Billing follows Copilot Chat — [GitHub changelog: Spaces GA](https://github.blog/changelog/2026-06-02-copilot-spaces-is-now-generally-available/)
- Copilot knowledge bases were retired on 1 Nov 2025 and replaced by Spaces, with a conversion tool — [GitHub changelog, 20 Aug 2025](https://github.blog/changelog/2025-08-20-sunset-notice-copilot-knowledge-bases/); [GitHub changelog, 17 Oct 2025](https://github.blog/changelog/2025-10-17-copilot-knowledge-bases-can-now-be-converted-to-copilot-spaces)
- The Copilot Spaces API became GA on 18 May 2026 — [GitHub changelog](https://github.blog/changelog/2026-05-18-copilot-spaces-api-now-generally-available)

**PR-review bots with knowledge bases**
- CodeRabbit's "Knowledge Base" combines Learnings (from prior PRs, issues and guidelines; viewable and editable), Code Guidelines, issue trackers, connected MCP servers and cross-repo analysis — [CodeRabbit pricing](https://coderabbit.ai/pricing); [CodeRabbit changelog](https://docs.coderabbit.ai/changelog)
- Greptile Pro includes "Learning and custom context", a Knowledge Base MCP, cross-repo context, and Jira/Linear/Notion integrations — [Greptile pricing, fetched Nov 2026](https://www.greptile.com/pricing.md)
- Atlassian Rovo Dev Code Reviewer works on Bitbucket Cloud and GitHub and checks PRs against Jira acceptance criteria. It draws on Atlassian's Teamwork Graph, which Atlassian says links goals, docs, tickets, incident history, team decisions and code. Rovo Dev also runs in a CLI and in VS Code — [Atlassian Rovo Dev code review](https://www.atlassian.com/software/rovo-dev/code-review); [Rovo Dev](https://www.atlassian.com/software/rovo-dev)
- Macroscope launched in Sep 2025 for codebase understanding and bug finding. Its "Status" product turns commits into readable summaries and sprint/project reports — [TechCrunch, 17 Sep 2025](https://techcrunch.com/2025/09/17/meet-macroscope-an-ai-tool-for-understanding-your-code-base-fixing-bugs/); [MakerStack review](https://makerstack.co/reviews/macroscope-review/)

**Ownership / knowledge-risk analytics and portals**
- CodeScene is behavioural code analysis that combines complexity metrics with version-control history. Thoughtworks Radar notes renewed interest because of coding agents — [Thoughtworks Radar](https://www.thoughtworks.com/es/radar/tools/codescene)
- CodeScene's off-boarding simulation estimates how much code depends on departed contributors and flags low-bus-factor areas as key-person risks — [CodeScene docs: off-boarding simulator](https://codescene.io/docs/guides/simulations/offboarding-simulator.html); [CodeScene knowledge-sharing use case](https://codescene.com/resources/use-cases/improve-knowledge-sharing)
- The CodeScene CodeHealth MCP Server (a local MCP service for AI assistants) launched on Product Hunt on 29 Apr 2026 — [Product Hunt](https://www.producthunt.com/products/codescene-codehealth-mcp-server); [CodeScene MCP page](https://codescene.com/product/mcp-server)
- Port raised $100M at an $800M valuation in Dec 2025 to compete with Backstage. It runs an MCP server, AI agents and an AI registry — [TechCrunch, 11 Dec 2025](https://techcrunch.com/2025/12/11/port-raises-100m-at-800m-valuation-to-take-on-spotifys-backstage); [Port blog](https://www.port.io/blog/ai-agents-port)
- Spotify Portal for Backstage exposes tools over MCP through `@backstage/plugin-mcp-actions-backend`. CIMD OAuth agent connection is in Beta — [Backstage Portal MCP docs](https://backstage.spotify.com/docs/portal/core-features-and-plugins/mcp)
- Stepsize: the only 2026 source found (a low-authority directory, Apr 2026) describes Stepsize AI as Jira/Linear analytics that produces AI-written product development reports. That suggests it is no longer a code-knowledge tool — [The Daily Workflow listing](https://thedailyworkflow.com/service/Stepsize%20AI)

**New 2025–2026 entrants focused on "why" and provenance**
- Entire (founded by former GitHub CEO Thomas Dohmke) launched Checkpoints in Feb 2026. It captures agent prompts, reasoning, transcripts, tool calls and token usage, links them to commits through a 12-character Checkpoint ID trailer, and stores metadata on an `entire/checkpoints/v1` branch. GitLab squash merges can drop the trailer — [Entire blog](https://entire.io/blog/hello-entire-world); [Entire docs](https://docs.entire.io/guides/checkpoints/overview); [ostechnix](https://ostechnix.com/entire-cli-git-observability-ai-agents/); [Towards AI ($60M seed headline)](https://pub.towardsai.net/the-60-million-bet-on-the-future-of-coding-how-githubs-former-ceo-is-building-the-git-for-ai-c125471a136d)
- Cursor Blame (Cursor 2.4, Enterprise plan, off by default) labels lines as Tab, Agent (with model) or human. Hovering shows a summary of the conversation that produced a line. Cursor also published Agent Trace, a draft open spec for line-level AI attribution — [Cursor docs](https://cursor.com/docs/integrations/cursor-blame); [InfoQ, Feb 2026](https://www.infoq.com/news/2026/02/agent-trace-cursor)
- GitHub Copilot Memory stores repository-level facts with citations to supporting code. It validates those citations against the current branch before using a memory and deletes unused memories after 28 days. It entered public preview on 15 Jan 2026 and was on by default for Pro/Pro+ from 4 Mar 2026 — [GitHub docs](https://docs.github.com/en/copilot/concepts/agents/copilot-memory); [GitHub changelog, 15 Jan 2026](https://github.blog/changelog/2026-01-15-agentic-memory-for-github-copilot-is-in-public-preview/); [GitHub changelog, 4 Mar 2026](https://github.blog/changelog/2026-03-04-copilot-memory-now-on-by-default-for-pro-and-pro-users-in-public-preview/)
- GitLens "AI Commit Explain" (Pro and higher) explains the intent and impact of a commit from the Commit Graph and blame hovers — [GitLens docs](https://help.gitkraken.com/gitlens/gl-gk-ai/)
- Small open-source "why" tools from 2026:
  - archeologist: AST-aware lineage of a function's decision history — [PyPI](https://pypi.org/project/archeologist/)
  - git-why: offline, heuristic answers from local history — [PyPI](https://pypi.org/project/git-why/)
  - mcp-server-dig: a `git_why` MCP tool built on blame, commits and co-changes — [Socket](https://socket.dev/npm/package/mcp-server-dig)
  - decision-memory: scoped ADR-like files surfaced when matching files are edited — [GitHub](https://github.com/tarunagnihotri534/decision-memory)
  - Tacit: a local-first MCP decision store — [DEV](https://dev.to/alexleotz23086493/solving-ai-amnesia-why-your-coding-agents-needs-institutional-memory-5c46)
- A May 2026 hackathon "code-archaeologist" uses a post-validator that strips any claim whose commit SHA is missing from `git log`. That is conceptually the same as Untangle's validated citations — [lablab.ai](https://lablab.ai/submissions/shwuqbtppeztzs0t82h5850k)
- JetBrains described an internal tool, CommitAtlas, that lets agents query git history for project conventions before writing code (Mar 2026) — [JetBrains TeamCity blog](https://blog.jetbrains.com/teamcity/2026/03/how-we-taught-ai-agents-to-see-the-bigger-picture/)

**Knowledge-transfer / offboarding capture (adjacent to Untangle's handover-call ingestion)**
- Sensay runs AI voice interviews with departing staff and turns them into a searchable knowledge base in Slack or Teams — [Barchart press release](https://www.barchart.com/story/news/36018738/sensay-launches-worlds-first-ai-offboarding-platform-for-knowledge-transfer)
- Squirro describes transcribing exit interviews into a knowledge graph that can be queried by chat — [Squirro blog](https://squirro.com/squirro-blog/ai-tacit-knowledge-capture)
- Granola pitches AI meeting notes as institutional memory. Unblocked ingests Granola and Fireflies — [Granola blog](https://www.granola.ai/blog/institutional-knowledge-meeting-notes); [Unblocked AI info](https://getunblocked.com/ai-info/index.md)

### Inferences
- Unblocked is the benchmark Untangle will be compared against. It already covers multi-source ingestion, cited answers, meeting tools, MCP, Slack and a PR bot, and names "obsoletion" and "conflict resolution". Untangle's defensible ground is narrower and deeper:
  - an explicit, inspectable, bi-temporal Decision graph with SUPERSEDES chains
  - CONFIRMS/CONTRADICTS links between handover statements and repo evidence
  - documented refusal behaviour
  - a "person to ask" pointer
  - Pulse risk ranking
  - code-mixed (Hinglish) handover calls
- The wiki cluster (DeepWiki, Code Wiki, Mintlify, Dosu) explains *what* code does from the current snapshot. Untangle answers *why* it became that way. That is a positioning contrast to stress.
- Entire, Cursor Blame and Copilot Memory record "why" going forward for agent-written code. Untangle reconstructs "why" backwards for legacy, human-written code. The two are complementary, and Untangle could ingest Entire checkpoint trailers and Agent Trace data as new evidence types.
- CodeScene is the closest overlap with Pulse (ownership gap, bus factor). Its signals are statistical rather than rationale-based, so "rationale gap", "contradiction" and "drift" appear unique to Untangle.

### Gaps
- No primary source confirmed DeepWiki's or Glean's citation format in this session. From general knowledge both show source links, but this was not verified here.
- Stepsize's current product could not be confirmed from a primary source.
- Cortex's 2026 AI features were not researched in depth.
- No funded startup was found whose core product is "decision history / why" for codebases, other than Unblocked's partial positioning. The market appears to be open-source projects and hackathon entries.

## 2. Per-product profile: use case, evidence, citations, temporal awareness, refusal, pricing, self-host, buyer

### Takeaway
Most products ground in code plus PRs and issues. Only Unblocked, Glean and Rovo span chat, docs and tickets broadly, and only Unblocked documents meeting-tool ingestion. Citations are common. Formal temporal modelling (supersession, validity windows) is essentially absent: Copilot Memory's citation revalidation and 28-day expiry, and Unblocked's "reference obsoletion", are the nearest. No vendor I found documents explicit refusal or abstention when evidence is missing. Pricing is volatile in 2026 across the board (credit/usage models replacing seats), and self-hosting is almost always Enterprise-only.

### Cited Findings
**Unblocked**
- Platform costs $29/user/month annual or $35 monthly, with a 21-day trial and no card. It includes Unblocked Code (an agent that opens draft PRs), MCP, "questions about your software and its history", incognito mode and API access — [Unblocked pricing, fetched Nov 2026](https://getunblocked.com/pricing/index.md)
- Enterprise adds SSO, Data Shield permission enforcement, on-prem deployment options, GitHub Enterprise, Jira DC and Bitbucket DC — [Unblocked pricing](https://getunblocked.com/pricing/index.md)
- In Sep 2026 Unblocked removed its $19 Code Review tier, so the entry price rose 53% to $29 — [PricingSaaS](https://pricingsaas.com/companies/unblocked)
- Surfaces: web app, macOS app, Slack/Teams, MCP server (Claude Code, Cursor, Windsurf, Copilot, Codex, VS Code), CLI, Answers API, PR review and `@unblocked` PR chat. Every answer links to the files, PRs, tickets or docs used, and the main branch is treated as source of truth. Refusal and confidence behaviour is not described — [Unblocked AI info](https://getunblocked.com/ai-info/index.md)

**DeepWiki / Devin (Cognition)**
- Public deepwiki.com was to remain free when Cognition retired its Core/Team plans for Free/Pro/Max/Teams/Enterprise on 14 Apr 2026 — [Cognition blog, 14 Apr 2026](https://www.cognition.ai/blog/new-self-serve-plans-for-devin)
- Aggregators list Devin Pro at $20/month, Max at $200 and Teams from $80. Some say premium DeepWiki now needs Pro, which conflicts with Cognition's statement — [dev.to review](https://dev.to/jovan_chan_9500711396d4e6/devin-20-review-2026-the-500-ai-engineer-is-now-20-and-bundled-with-windsurf-2h2e); [Tailkits](https://tailkits.com/tools/devin/)
- Aggregators also report that Windsurf was renamed Devin Desktop on 2 Jun 2026 (unverified against a primary source) — [Tailkits](https://tailkits.com/tools/devin/)
- Evidence is the code in the repo snapshot. I found no description of PR, issue or chat ingestion for history — [Cognition DeepWiki MCP blog](https://cognition.ai/blog/deepwiki-mcp-server)

**Google Code Wiki**
- Free public preview covering public repos. Every section and answer is hyperlinked to code — [Google Developers Blog](https://developers.googleblog.com/en/introducing-code-wiki-accelerating-your-code-understanding/)
- There was no pricing for the private-repo extension, and the page carries a "can make mistakes" disclaimer — [The Register, 17 Nov 2025](https://www.theregister.com/2025/11/17/google_previews_code_wiki/)

**Swimm**
- Pricing is based on the lines of code to be understood, by quote. A paid one-week "grounding sample" under NDA is credited toward the project, and pricing pages list cloud, on-prem and air-gapped options — [Swimm pricing](https://swimm.io/pricing); [GetApp search summary](https://www.getapp.com/all-software/a/swimm/)
- Aggregators give conflicting self-serve figures ($39 and $11/dev/month), probably stale — [AIsoTools](https://aisotools.com/pricing/swimm); [Toolradar](https://toolradar.com/tools/swimm)
- The buyer is a large enterprise with legacy or mainframe estates — [Swimm pricing](https://swimm.io/pricing)

**Greptile**
- Starter is free (1 developer, 50 credits/month). Pro is $1/credit with no seat fees, credits pooled across the org. Review depth costs Base 1, Plus 3 or Apex 10 credits. Enterprise is custom and adds self-hosting, SSO/SAML, GHES, GitLab Self-Managed, Bitbucket DC, Gitea and Perforce — [Greptile pricing, fetched Nov 2026](https://www.greptile.com/pricing.md)
- History: the Mar 2026 v4 model was $30/seat including 50 reviews, then $1 per review; before that it was a flat $30/dev/month. Plus and Apex tiers arrived on 25 Sep 2026 — [Greptile v4 blog](https://www.greptile.com/blog/greptile-v4); [UsagePricing](https://www.usagepricing.com/blueprint/activity/greptile-2026-09-25-launch)

**Sourcegraph**
- Enterprise only, from $16K/year minimum, with self-hosted or single-tenant options and pooled AI credits for Deep Search — [Sourcegraph pricing](https://sourcegraph.com/docs/pricing)
- An AWS Marketplace listing shows Deep Search credits as a $10,000 line item — [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-namq3ifjc4zky)
- Evidence is code across repos. Nothing found shows PR or chat ingestion.

**Augment Code**
- Standard is $20/month flat and Business $100/month flat (no per-seat charge, up to 50 seats); Enterprise is custom. Usage covers LLM, Context Engine and compute, with LLM usage billed at provider list price plus a 40% fee. Context Engine, MCP and Code Review are on all plans. Enterprise adds SSO/SCIM, CMEK and ISO 42001. Self-host or VPC is not mentioned — [Augment pricing, fetched Nov 2026](https://augmentcode.com/pricing)
- Search snippets also showed a $60 Standard tier, which conflicts with the fetched page — [Augment pricing (search snippet)](https://www.augmentcode.com/pricing?utm_category=agents)
- The Register covered the move to token-based pricing in Oct 2025 — [The Register, 15 Oct 2025](https://www.theregister.com/2025/10/15/augment_pricing_model/)

**GitHub Copilot (Spaces, Memory, code review)**
- Spaces are available to "all Copilot users" and billed like Copilot Chat — [GitHub changelog](https://github.blog/changelog/2026-06-02-copilot-spaces-is-now-generally-available/)
- Copilot Memory creates repo-level facts only from actions by users with write access, and owners can review or delete them — [GitHub docs](https://docs.github.com/en/copilot/concepts/agents/copilot-memory)

**CodeRabbit**
- Tier names and prices conflict between sources: Free / Pro $24 / Pro Plus $48 / Enterprise, or Essentials $24 / Team $48 / Advanced $72 per seat per month (Activepieces, checked 2 Nov 2026). Learnings are on paid tiers only — [Activepieces](https://www.activepieces.com/blog/coderabbit-pricing-2026-plans-costs-and-limits.md); [CodeRabbit pricing](https://coderabbit.ai/pricing)
- On 12 Oct 2026 Security Scan was renamed Deep Scan and agent-minute pricing was dropped — [PricingSaaS](https://pricingsaas.com/companies/coderabbit/diffs/2026D299)

**Dosu**
- Pricing changed repeatedly in 2026:
  - Business ($30/user) folded into Pro
  - credits introduced (Free 20, Pro 400)
  - credits raised 10x in Jul 2026 (Free 200, Pro 4000)
  - Pro price variously reported at $10, $16 and $20
  — [PricingSaaS Dosu](https://pricingsaas.com/companies/dosu); [PricingSaaS 2026W28](https://pricingsaas.com/companies/dosu/diffs/2026W28)
- A free maintainers tier exists for OSS — [EveryDev](https://www.everydev.ai/tools/dosu)

**CodeScene**
- About €18 per active author per month (Toolradar) or $18/user/month (GetApp, Mar 2026), with enterprise quotes — [Toolradar](https://toolradar.com/tools/codescene/pricing); [GetApp](https://www.getapp.com/all-software/a/codescene)
- The MCP server is included in the license — [CodeScene MCP](https://codescene.com/product/mcp-server)
- Evidence is git history and code metrics, not rationale text — [Thoughtworks Radar](https://www.thoughtworks.com/es/radar/tools/codescene)

**Glean**
- No public list price. Estimates run about $50–75/user/month with roughly 50–250-seat minimums. Flex pricing pools credits — [Activepieces](https://www.activepieces.com/blog/glean-pricing-in-2026-cost-seats-and-minimums.md); [Vendr](https://www.vendr.com/buyer-guides/glean); [Glean Flex docs](https://docs.glean.com/glean-enterprise-flex-pricing)
- Per-user OAuth maps GitHub identities so permissions are enforced — [Glean GitHub connector](https://docs.glean.com/connectors/native/github/)

**Atlassian Rovo Dev**
- Standard gives 2,000 Rovo Dev credits/user/month; Jira users get 350 free; overage is $0.01/credit — [Atlassian Rovo Dev pricing](https://www.atlassian.com/software/rovo-dev/pricing); [Atlassian Community](https://community.atlassian.com/forums/Rovo-questions/How-can-I-find-out-how-much-Rovo-will-cost-from-the-1st-March/qaq-p/3187868)
- Code Reviewer moves to usage-based pricing inside Jira subscriptions on 3 Dec 2026, when Rovo credit metering starts — [Atlassian licensing](https://www.atlassian.com/licensing/rovo-dev); [Atlassian usage](https://www.atlassian.com/resources/usage)

**Macroscope**
- Status costs $0.05 per commit processed (prepaid) and code review about $0.35/PR, per mirrored docs; third parties describe a $100 free credit or $30/dev/month Teams plan (conflicting) — [Macroscope pricing docs mirror](https://apis.emri.workers.dev/https-docs.macroscope.com/pricing); [ToolQuestor](https://toolquestor.com/tool/macroscope); [Toolify](https://www.toolify.ai/tool/macroscope)

**Port / Backstage / Cortex**
- Port is free up to 15 users; paid tiers are reported at $30–40/seat (sources conflict) — [Port pricing](https://port.io/pricing); [PricingSaaS](https://pricingsaas.com/companies/port)
- Cortex is quote-only, per seat — [Dupple](https://dupple.com/learn/best-internal-developer-portals)
- Backstage is open source; Spotify Portal is the commercial version — [Backstage Portal docs](https://backstage.spotify.com/docs/portal/core-features-and-plugins/mcp)

**Mintlify**
- Autopilot costs 250 credits per PR opened or updated, and is on by default for Pro — [Mintlify blog](https://mintlify.com/blog/autopilot); [Mintlify changelog](https://mintlify.com/docs/changelog)

**Entire / Cursor Blame**
- Entire Checkpoints is an open-source CLI supporting Claude Code, Codex, Gemini CLI, OpenCode and Pi — [Entire docs](https://docs.entire.io/cli/checkpoints)
- Cursor Blame is Enterprise-only — [Cursor docs](https://cursor.com/docs/integrations/cursor-blame)

### Inferences
Summary matrix, derived from the findings above. "n/f" means not found in this research; "?" means uncertain.

| Product | Core use case | Evidence beyond code | Cites sources | Temporal/history awareness | Documented refusal | Entry price (Nov 2026) | Self-host | Buyer |
|---|---|---|---|---|---|---|---|---|
| **Untangle** | "Why is code like this?" | Git history, PRs/reviews/issues, ADRs/docs, config/dependency diffs, Hinglish handover calls | Yes, validated | Bi-temporal Decisions, SUPERSEDES, CONFIRMS/CONTRADICTS | Yes | — | — | — |
| Unblocked | Cited Q&A + context for agents | PRs, Jira/Linear, Confluence/Notion, Slack/Teams, Fireflies/Granola, Datadog/Sentry, chosen websites | Yes | "Reference obsoletion", conflict resolution, PR history | n/f | $29/user/mo | Enterprise on-prem | Eng teams of any size |
| DeepWiki/Devin | Auto-wiki + Q&A | n/f (repo snapshot) | ? (not verified) | n/f | n/f | Free public; Devin Pro ~$20 | n/f | Individual devs → Devin funnel |
| Google Code Wiki | Auto-wiki + chat | n/f | Yes (hyperlinks) | Regenerates each change; no history | Disclaimer only | Free preview | Private via CLI ext (waitlisted) | OSS devs |
| Swimm | Legacy modernisation "grounding layer" | Schemas, mainframe code | Yes ("traced to code") | n/f | Expert-verified | Quote by LOC | Historically on-prem/air-gapped | Large enterprises, mainframe |
| Greptile | PR review + learnings | Jira/Linear/Notion | ? | Learns from past PRs | n/f | Free / $1 per credit | Enterprise | Eng teams |
| CodeRabbit | PR review | Issues, MCP sources, **web search** | ? | Learnings from prior PRs | n/f | ~$24/seat | Enterprise (unverified) | Eng teams |
| Sourcegraph | Code search + Deep Search | n/f | ? | n/f | n/f | $16K/yr min | Yes | Large enterprises |
| Augment | Context Engine for agents | Jira/Linear/Notion via MCP | ? | n/f | n/f | $20/mo flat | n/f | Teams up to 50 + enterprise |
| Copilot Spaces/Memory | Curated context + agent memory | PRs, issues, docs | Memory has code citations | Revalidates memories; 28-day expiry | n/f | Copilot plan | GitHub-hosted | GitHub customers |
| Qodo Aware | Deep research across repos | OSS libraries (Open Aware) | ? | n/f | n/f | Enterprise | ? | Enterprise |
| Glean | Enterprise search incl. code | Everything in workplace SaaS | ? (not verified) | n/f | n/f | ~$50–75/user est. | n/f | Enterprise-wide |
| Rovo Dev | Jira-aware coding and review | Teamwork Graph (tickets, docs, incidents, decisions) | ? | n/f | n/f | Credits; 350 free with Jira | n/f | Atlassian shops |
| Dosu | Self-updating docs / knowledge base | Slack/Teams, Confluence/Notion | ? | Doc drift on PRs | n/f | Free; Pro ~$10–20 | n/f | OSS maintainers, small teams |
| CodeScene | Code health + knowledge-loss analytics | Git history (behavioural) | N/A | Strong (VCS history analytics) | N/A | ~€18/author | Yes (on-prem historically; unverified here) | Eng managers |
| Entire | Capture agent reasoning per commit | Agent transcripts | N/A | Per-commit | N/A | OSS CLI | Local | AI-heavy teams |
| Macroscope | Commit summaries + review | n/f | ? | Commit stream | n/f | $0.05/commit | n/f | Eng leaders |

- The column most likely to differentiate Untangle is "Documented refusal": I found no competitor that describes refusing for lack of evidence.
- The pricing anchor for a team buyer is $20–35/user/month (Unblocked, Augment Standard, CodeRabbit). A usage-priced alternative (Greptile credits, Macroscope per-commit) suits Untangle's ingest-heavy, query-light usage pattern.

### Gaps
- Citation and refusal behaviour for DeepWiki, Greptile chat, Sourcegraph Deep Search, Augment, Glean and Rovo was not confirmed from primary docs in this session.
- CodeRabbit's self-hosting availability and current official tier names are unconfirmed (sources conflict).
- Copilot Spaces GA date conflicts: the fetched changelog page (URL slug 2026-06-02) stated GA on 24 Sep 2025, and a Java Code Geeks piece says September. Treat the date as uncertain; GA itself is not in doubt.

## 3. Do any of them research the public internet to explain or validate code decisions?

### Takeaway
Only a few use external evidence, and none uses it to explain *historical* decisions. CodeRabbit is the clearest case: it runs web queries automatically during reviews to pull in current docs. Renovate (non-AI) embeds upstream changelogs into dependency PRs. Qodo's Open Aware and DeepWiki's free public MCP index popular OSS repos that agents can query for upstream context. Unblocked can index chosen "external websites" as documentation. No product was found that links a past commit or decision to the upstream changelog entry, CVE, library issue or Stack Overflow thread that motivated it, at the time it was made. That looks like an open gap for Untangle.

### Cited Findings
- CodeRabbit automatically runs web queries for recent public information, including material newer than the model's training cut-off, to fetch current documentation for reviews. It can be disabled with `web_search: false` under `knowledge_base` — [CodeRabbit docs (changelog entry)](https://docs.coderabbit.ai/changelog/code-graph-analysis)
- Unblocked lists "External websites" as a documentation source, which implies indexing chosen sites rather than open-ended web research — [Unblocked AI info](https://getunblocked.com/ai-info/index.md)
- Qodo's open-source Open Aware indexes popular open-source libraries and offers a free MCP setup — [Qodo blog](https://www.qodo.ai/blog/introducing-qodo-aware-deep-codebase-intelligence-for-enterprise-development); [GitHub open-aware](https://github.com/qodo-ai/open-aware)
- DeepWiki's MCP gives free, unauthenticated access to any public repo's wiki, so an agent can ask about an upstream dependency's code — [Cognition blog](https://cognition.ai/blog/deepwiki-mcp-server)
- Renovate's `fetchChangeLogs` (default `pr`) embeds upstream release notes in dependency-update PRs for GitHub, GitLab and Bitbucket-hosted changelogs. Users report gaps, for example pre-release notes missing — [Renovate docs: changelogs](https://docs.renovatebot.com/key-concepts/changelogs); [Renovate config diff](https://git.code.tecnalia.com/smartdatalab/public/applications/renovate/-/commit/f70f0c82beda4712f11f93a4a111ca4f56d4ea5a.diff)
- Lack of external awareness hurts snapshot tools. Code Wiki did not flag that the vuejs/vue repo is obsolete and end-of-life. On whether PostgreSQL can back an ASP.NET Core distributed cache, it was only "half right" because it ignored external Microsoft docs — [The Register](https://www.theregister.com/2025/11/17/google_previews_code_wiki/)
- External evidence itself is getting noisier. JFrog reported fabricated SQLite CVEs that were later rejected, and commentators warn that a CVE ID alone is not technical verification — [The Register, Aug 2026](https://assets.theregister.com/2026/08/03/202615/)
- Practitioners say LLM security review needs runtime confirmation, describing it as "a hypothesis engine" — [ProjectDiscovery](https://projectdiscovery.io/blog/ai-code-review-vs-neo)
- Web search can make answers wrong in other ways: the HalluHard benchmark (Feb 2026) found frontier models still hallucinated about 30% of the time with web search enabled — [arXiv 2602.01031](https://arxiv.org/html/2602.01031)

### Inferences
- An "external evidence" layer could be a strong Untangle feature: time-aligned upstream changelogs, GitHub release notes, CVE/OSV advisories, library issues, and docs snapshots from the version in use *at commit time*. It should keep Untangle's refusal discipline, citing only fetched, archived URLs, and should mark web evidence as a separate trust tier from repo evidence. Each external claim should be stored as its own evidence node with a capture timestamp (bi-temporal fit).
- Dependency diffs are already ingested, so the natural first step is: dependency bump → fetch the upstream release note or advisory for that exact version range → CONFIRMS/CONTRADICTS the commit or PR rationale.

### Gaps
- I did not verify whether Unblocked, Greptile, Augment, Sourcegraph Deep Search, Devin or Copilot code review run open-web search inside their Q&A or review. General-purpose agents (Claude Code, Cursor, Copilot agent) have generic web tools, but none of the code-knowledge products documents using them for decision rationale.
- No product reviews or benchmarks were found measuring how well any tool explains decisions with external sources.

## 4. Recurring gaps and user complaints

### Takeaway
Complaints cluster into five themes:
1. Confidently wrong or stale auto-generated docs (DeepWiki, Code Wiki).
2. Noisy, low-precision PR comments (CodeRabbit, AI reviewers in general).
3. Snapshot-only reasoning with no history.
4. Pricing churn and usage-meter anxiety (Unblocked, Greptile, Dosu, Augment, Atlassian).
5. Privacy and self-hosting locked to Enterprise tiers.

Independent practitioner discussion of Unblocked and Swimm is sparse. Most visible content is vendor-authored.

### Cited Findings
- **DeepWiki accuracy.** Maintainers and communities report errors:
  - On HN, one commenter called docs for LLVM incomplete to plainly incorrect — [HN 45002092](https://hn.svelte.dev/item/45002092)
  - Another HN thread described stale details for a maintainer's project — [HN 45884169](https://hn.svelte.dev/item/45884169)
  - A maintainer called the output confusing, misleading or flatly wrong — [blopker](https://blopker.pages.dev/writing/12-deepwiki)
  - Scala contributors said most details in the Scala 3 wiki were wrong — [Scala contributors](https://contributors.scala-lang.org/t/ai-slop-claiming-to-be-documentation/7382)
  - Julia and OpenWrt communities flagged incorrect package details — [Julia Discourse](https://discourse.julialang.org/t/ai-generated-documentation-deepwiki-julia/128447); [OpenWrt forum](https://forum.openwrt.org/t/important-consideration-deepwiki-ai-generated-docs-may-contain-inaccuracies/249471)
- Some defenders say DeepWiki is a decent starting point where official docs are sparse — [OpenWrt forum](https://forum.openwrt.org/t/important-consideration-deepwiki-ai-generated-docs-may-contain-inaccuracies/249471)
- A 2025 arXiv paper (CodeWiki) reports DeepWiki scoring below the authors' system on a documentation-quality benchmark (author-favourable comparison) — [arXiv 2510.24428](https://arxiv.org/html/2510.24428v1)
- **Code Wiki.** A Vue expert called the output "educated guess" documentation, verbose and swinging between too vague and too specific. A commenter worried that constant regeneration means nothing persists — [The Register](https://www.theregister.com/2025/11/17/google_previews_code_wiki/)
- **Review noise.**
  - G2 reviewers of CodeRabbit cite bulk useless comments and slowness — [G2 CodeRabbit reviews](https://www.g2.com/products/coderabbit/reviews)
  - An academic study of CodeRabbit comments in the wild found many false-positive, redundant or out-of-scope suggestions — [alphaXiv 2607.03316](https://www.alphaxiv.org/abs/2607.03316)
  - A CodeRabbit-cited figure puts default-config full-stream precision at 26.4%, with 110 nitpicks — [G2/search summary](https://www.g2.com/products/coderabbit/reviews)
  - CodeRabbit publishes a "reduce noise" guide — [CodeRabbit docs](https://docs.coderabbit.ai/configuration/guides/reduce-noise.md)
- **Snapshot vs history.** An IndieHackers post advises checking whether a tool reasons over commit history and PR context or only the current snapshot, and describes a bug an agent would have shipped without a history-aware pass — [IndieHackers](https://www.indiehackers.com/post/we-stopped-pointing-ai-agents-at-legacy-codebases-without-a-history-aware-pass-first-heres-the-bug-it-would-ve-shipped-d5e18cc78b)
- A git-why write-up notes that history-derived answers are "not a replacement for a full architecture decision record" — [positioniseverything](https://www.positioniseverything.net/how-git-why-stores-ai-intent-in-git-commit-trailers/)
- **Provenance tooling gaps.** Cursor forum users report Cursor Blame lines with no conversation summary or link — [Cursor forum](https://forum.cursor.com/t/cursor-blame-missing-agent-conversation-summary/150719)
- Entire's checkpoint trailers can be lost on GitLab squash merges — [Entire docs](https://docs.entire.io/guides/checkpoints/overview)
- **Pricing churn.**
  - Unblocked's entry price rose 53% in Sep 2026 — [PricingSaaS](https://pricingsaas.com/companies/unblocked)
  - Greptile changed models three times in 2026 — [Greptile v4](https://www.greptile.com/blog/greptile-v4); [UsagePricing](https://www.usagepricing.com/blueprint/activity/greptile-2026-09-25-launch)
  - Dosu repriced several times — [PricingSaaS Dosu](https://pricingsaas.com/companies/dosu)
  - Augment moved to token pricing with a 40% LLM fee — [Augment pricing](https://augmentcode.com/pricing); [The Register](https://www.theregister.com/2025/10/15/augment_pricing_model/)
  - Atlassian meters Rovo credits from 3 Dec 2026 — [TechRepublic](https://www.techrepublic.com/fr/article/news-atlassian-rovo-automation-pricing/); [TechTarget](https://www.techtarget.com/it-infrastructure/news/366622263/Atlassian-Rovo-pricing-shifts-amid-industry-AI-struggles)
- **Privacy / deployment.** On-prem or self-host is Enterprise-only at Unblocked and Greptile. Sourcegraph offers self-host only on its $16K+ Enterprise plan — [Unblocked pricing](https://getunblocked.com/pricing/index.md); [Greptile pricing](https://www.greptile.com/pricing.md); [Sourcegraph pricing](https://sourcegraph.com/docs/pricing)
- Glean needs per-user OAuth before private repos are visible — [Glean docs](https://docs.glean.com/connectors/native/github/)
- **Ownership metrics in the AI era.** Commentators argue bus factor is less reliable when AI writes code nobody understands, and that VCS-based estimates miss senior engineers who rarely commit — [Qodo glossary](https://www.qodo.ai/glossary/what-is-bus-factor/); [CodeRabbit guide](https://coderabbit.ai/guides/ai-second-brain-for-engineering)
- An arXiv study examines how GenAI distorts truck-factor models — [arXiv 2507.08160](https://arxiv.org/html/2507.08160v1)
- Thoughtworks Radar lists "codebase cognitive debt" as a technique concern — [Thoughtworks Radar](https://www.thoughtworks.com/en-th/radar/techniques/codebase-cognitive-debt)

### Inferences
- The two most-cited failure modes, confident wrongness and staleness, line up directly with Untangle's validated citations, refusal and bi-temporal SUPERSEDES modelling. Lead with those in positioning, ideally with a published refusal/precision eval.
- AI authorship erodes the reliability of commit-author ownership signals. Pulse's "ownership gap" should consider Agent Trace or Entire metadata so it does not count AI-authored lines as a human owner's knowledge.
- Price predictability is a buying concern in 2026. A simple, predictable plan, for example per repository, may be a differentiator against credit-metered competitors.

### Gaps
- No substantive r/ExperiencedDevs or HN threads about Unblocked or Swimm were found. Searches returned vendor content only, so practitioner sentiment on the closest competitor is unknown.
- No G2 review data was gathered for Unblocked, Greptile or Swimm specifically.

## 5. Table stakes vs differentiators in 2026

### Takeaway
By late 2026 an **MCP server** is table stakes: almost every product here ships one. So are a **PR bot / review integration**, **Slack or Teams Q&A**, **cited answers**, **GitHub + Jira/Linear + Confluence/Notion connectors**, and an **SSO/Enterprise tier with on-prem**. The real differentiators are temporal correctness (supersession, staleness, validity), contradiction detection between sources, explicit abstention, knowledge-risk scoring, meeting/handover ingestion, external-evidence grounding, and multilingual or code-mixed speech. None of these is well served today. Unblocked partly covers the first two and meeting ingestion, CodeScene partly covers risk scoring, and Copilot Memory partly covers revalidation.

### Cited Findings
- **MCP is ubiquitous.** Products shipping an MCP server include:
  - Unblocked — [Unblocked](https://getunblocked.com/ai-info/index.md)
  - DeepWiki/Devin — [Cognition](https://cognition.ai/blog/deepwiki-mcp-server)
  - Augment — [Augment](https://augmentcode.com/blog/context-engine-mcp-now-live)
  - Sourcegraph — [Sourcegraph](https://sourcegraph.com/docs/pricing)
  - Qodo — [Qodo](https://docs.qodo.ai/developer-tools/context-engine-mcp-tools)
  - Glean — [Glean](https://docs.glean.com/user-guide/assistant/code-search)
  - Greptile KB MCP — [Greptile](https://www.greptile.com/pricing.md)
  - Copilot Spaces via GitHub MCP — [GitHub](https://github.blog/changelog/2026-06-02-copilot-spaces-is-now-generally-available/)
  - CodeScene — [CodeScene](https://codescene.com/product/mcp-server)
  - Port — [Port](https://www.port.io/blog/integrate-software-catalog-every-workflow-port-mcp-server/)
  - Backstage Portal — [Backstage](https://backstage.spotify.com/docs/portal/core-features-and-plugins/mcp)
  - Swimm — [Swimm](https://swimm.io/pricing)
  - Driver — [YC](https://www.ycombinator.com/launches/Pqj-driver-context-for-codebases)
- **PR review is bundled almost everywhere.** Unblocked, Augment, Greptile, CodeRabbit, Rovo Dev, Macroscope and Devin Review all include it — [Unblocked](https://getunblocked.com/ai-info/index.md); [Augment](https://augmentcode.com/pricing); [Rovo Dev](https://www.atlassian.com/software/rovo-dev/code-review); [Macroscope](https://toolquestor.com/tool/macroscope); [dev.to Devin](https://dev.to/jovan_chan_9500711396d4e6/devin-20-review-2026-the-500-ai-engineer-is-now-20-and-bundled-with-windsurf-2h2e)
- **Chat surfaces.** Slack/Teams in Unblocked, Dosu and Sensay; IDE and CLI in Augment, Rovo Dev (VS Code, CLI), Copilot and Unblocked CLI — [Unblocked](https://getunblocked.com/ai-info/index.md); [EveryDev Dosu](https://www.everydev.ai/tools/dosu); [Rovo Dev](https://www.atlassian.com/software/rovo-dev)
- **Autonomous agents opening PRs are becoming standard add-ons**: Unblocked Code, Mintlify Autopilot (doc PRs), Dosu Self-Documenting PRs — [Unblocked pricing](https://getunblocked.com/pricing/index.md); [Mintlify](https://mintlify.com/blog/autopilot); [EveryDev Dosu](https://www.everydev.ai/tools/dosu)
- **Partial differentiators that already exist.**
  - Unblocked: reference obsoletion and conflict resolution — [Unblocked](https://getunblocked.com/ai-info/index.md)
  - Copilot Memory: citation revalidation and 28-day expiry — [GitHub docs](https://docs.github.com/en/copilot/concepts/agents/copilot-memory)
  - CodeScene: off-boarding / knowledge-loss simulation — [CodeScene](https://codescene.io/docs/guides/simulations/offboarding-simulator.html)
  - Swimm: deterministic extraction plus human expert verification — [Swimm](https://swimm.io/pricing)
  - Rovo: validation against Jira acceptance criteria — [Rovo Dev](https://www.atlassian.com/software/rovo-dev/code-review)
  - Entire and Cursor: commit-level reasoning capture — [Entire](https://docs.entire.io/guides/checkpoints/overview); [Cursor](https://cursor.com/docs/integrations/cursor-blame)
- **Graph-based context is already a marketed technique.** Qodo combines knowledge graphs with LSP and vectors — [Qodo](https://docs.qodo.ai/developer-tools/context-engine-mcp-tools)
- CodeRabbit ships "Code Graph Analysis" — [CodeRabbit](https://docs.coderabbit.ai/changelog/code-graph-analysis)
- Greptile analyses code through repository graphs — [Scrimba roundup](https://scrimba.com/articles/best-ai-tools-for-onboarding-developers-2026/)

### Inferences
- "Uses a knowledge graph" is not a differentiator by itself. Untangle should market *what the graph models*: decisions as first-class, time-versioned entities with supersession and contradiction edges, which no competitor documents.
- Table stakes Untangle may need to reach parity on: an MCP server exposing `why(file|symbol|feature)`, `decisions_for(path)` and `who_to_ask(path)`; a PR-bot comment that surfaces superseded or contradicted decisions touching a diff; and a Slack bot. Without MCP, Untangle risks being invisible to the coding agents through which developers increasingly consume context.
- Candidate differentiators, in rough order of uniqueness found:
  1. Explicit abstention ("no evidence; ask X") with a measured refusal rate.
  2. Handover-call ingestion in code-mixed languages (Hinglish), with CONFIRMS/CONTRADICTS against repo evidence. No competitor found mentions multilingual or code-mixed speech.
  3. Pulse knowledge-risk ranking based on rationale (rationale gap, drift, contradiction), not just ownership statistics.
  4. Time-aligned external evidence (upstream changelogs, advisories) validated per decision.
  5. Ingesting agent provenance (Entire checkpoints, Agent Trace) as a new rationale source, bridging legacy and agent-era "why".

### Gaps
- I found no adoption or usage data showing which surfaces (MCP vs Slack vs IDE vs PR bot) drive retention for code-knowledge tools.
- No competitor documentation on Hinglish or code-mixed transcription was found. This is absence of evidence, not proof that it does not exist (e.g., inside Fireflies or Granola transcription, which Unblocked relies on).
