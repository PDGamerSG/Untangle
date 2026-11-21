# Use cases, pain points and regulatory drivers for a "why is the software this way" product (Untangle), as of November 2026

Evidence labels used below:
- **[Measured]** independent survey, academic study, or official statistic
- **[Vendor survey]** survey run or published by a company that sells a related product (useful, but self-interested)
- **[Vendor claim]** marketing or product-page claim, not independently verified
- **[Regulation]** legal text or official regulator/agency publication
- **[Secondary]** press or law-firm summary of a primary source that I could not open directly

## 1. Developer time and knowledge loss: how big is the "why" problem?

### Takeaway
Independent surveys consistently show developers lose a large share of their week to finding information and understanding existing code (about 58% of time on comprehension in a field study; 61% spend 30+ minutes a day searching; "finding information" is the top time-waster in Atlassian's 2025 survey). AI tools have not removed this. In 2025–2026 surveys the complaint shifted to AI output that "misses context" or "the original intent", which is the gap a decision-history graph fills.

### Cited Findings

**Stack Overflow Developer Survey**
- [Measured] 2024 (n=28,911 answering): 37.9% spend 30–60 min/day searching for answers, 18.3% spend 60–120 min, and 7.6% spend over 120 min. Stack Overflow's headline is "61% spend more than 30 minutes a day", but the chart values sum to 63.8%, so the page is internally inconsistent. About 26% spend 60+ minutes a day. — [Stack Overflow 2024, Professional Developers](https://survey.stackoverflow.co/2024/professional-developers)
- [Measured] 2024: 29.6% hit knowledge silos 10+ times a week (30.4% of ICs, 24.7% of managers), while 52.1% say they never do. Silos are concentrated rather than universal. 45.2% agree that silos stop ideas getting across the organisation. — [Stack Overflow 2024](https://survey.stackoverflow.co/2024/professional-developers)
- [Measured] 2024: 53% agree that "waiting on answers to questions often causes interruptions and disrupts my workflow". 26.8% need help from outside their team 10+ times a week. 48.8% often answer questions they have answered before, a repeated-question cost that falls on senior people. — [Stack Overflow 2024](https://survey.stackoverflow.co/2024/professional-developers)
- [Measured] 2025 (more than 49,000 respondents, released 29 July 2025): 84% use or plan to use AI tools. 46% distrust AI accuracy and 33% trust it. — [Stack Overflow blog, 2025 results](https://stackoverflow.blog/2025/07/29/developers-remain-willing-but-reluctant-to-use-ai-the-2025-developer-survey-results-are-here/); [InfoWorld](https://www.infoworld.com/article/4031673/)
- [Measured] 2025: 66% name AI answers that are "almost right, but not quite" as their top frustration, and 45% say debugging AI-generated code takes more time. InfoWorld's summary deck says 64% while its body says 66%, and some outlets mislabel the 45% figure. — [VentureBeat](https://venturebeat.com/ai/stack-overflow-data-reveals-the-hidden-productivity-tax-of-almost-right-ai-code); [The Register](https://www.theregister.com/2025/07/29/coders_are_using_ai_tools/)
- [Measured] 2025: 75% would still ask another person when they do not trust an AI answer. — [Stack Overflow 2025 TL;DR for leaders](https://stackoverflow.co/teams/resources/2025-stack-overflow-developer-survey-for-leaders/)
- [Measured] 2025, AI agents: about a third of developers use AI agents. 87% are concerned about agent accuracy and 81% about the security and privacy of their data. Stack Overflow's advice to leaders is "focus on your data first", meaning up-to-date, structured internal data. — [Stack Overflow 2025 leaders, AI agents](https://stackoverflow.co/internal/resources/2025-stack-overflow-developer-survey-for-leaders/ai-agents/)

**Atlassian State of Developer Experience**
- [Vendor survey] 2025 (3,500 developers and managers in six countries): 50% lose 10+ hours a week to non-coding inefficiencies and 90% lose 6+ hours. The top time-waster is "finding information (services, docs, APIs)", followed by adapting to new technology and context switching. Developers spend 16% of their time coding. 63% say leaders do not understand their pain points, up from 44%. — [Atlassian blog, DevEx 2025](https://www.atlassian.com/blog/developer/developer-experience-report-2025)
- [Vendor survey] 2025: the share losing 10+ hours rose from 33% in the 2024 report to 50%. — [Atlassian webinar listing](https://www.atlassian.com/ja/webinars/software/how-ai-is-shaping-developer-productivity); breakdown of 50% / 40% / 10% in [SD Times](https://sdtimes.com/ai/report-ai-productivity-gains-cancelled-out-by-friction-points-in-other-areas-that-slow-developers-down/)
- [Vendor survey, Secondary] 2026: the share saying AI saves them 10+ hours a week fell from 68% (2025) to about 25–26%. 49% spend 4+ hours a week managing AI tools, and **65% spend time correcting AI-generated work that missed the original intent**. 87% say AI helps them ship faster, but 72% report the same or more friction. Finding information and meetings remain the top friction points. — [SD Times](https://sdtimes.com/developer-experience/61556/); [CXOToday](https://cxotoday.com/others/atlassian-2026-devex-report-87-of-developers-code-faster-with-ai-but-72-face-same-or-higher-friction/); [LeadDev](https://leaddev.com/?p=36707); report page [Atlassian DevEx 2026](https://www.atlassian.com/teams/software-development/state-of-developer-experience-2026) (I could not extract the body text)

**DORA (Google Cloud)**
- [Measured] 2025 *State of AI-assisted Software Development*: nearly 5,000 respondents, surveyed 13 June to 21 July 2025. 90% use AI. AI is now linked to higher delivery throughput but still to instability. The central finding is that AI is an "amplifier" of existing strengths and weaknesses. The report introduces a seven-capability "DORA AI Capabilities Model". — [Google blog, DORA 2025](https://blog.google/technology/developers/dora-report-2025/); [dora.dev 2025 report](https://dora.dev/dora-report-2025/); [PDF](https://services.google.com/fh/files/misc/2025_state_of_ai_assisted_software_development.pdf)
- [Measured] 2023 *Accelerate State of DevOps*: high-quality documentation is associated with 25% higher team performance. DORA's model estimates that trunk-based development has 12.8x more impact on organisational performance when documentation quality is high (a model estimate, not an observed multiplier). — [Google Cloud blog, 2023 DORA](https://cloud.google.com/blog/products/devops-sre/announcing-the-2023-state-of-devops-report); [2023 report PDF](https://dora.dev/research/2023/dora-report/2023-dora-accelerate-state-of-devops-report.pdf)

**Program comprehension (academic)**
- [Measured] Xia et al., IEEE TSE 44(10), 2018: a field study of 78 professional developers across 3,148 working hours found that about **58% of developer time goes to program comprehension**. Seniors spend a significantly smaller share than juniors. The study was run at two companies in China. — [Xia et al. PDF](https://xin-xia.github.io/publication/TSE17.pdf); [SMU record](https://ink.library.smu.edu.sg/sis_research/3779)

**Onboarding and context (vendor surveys)**
- [Vendor survey] Cortex 2024 (n=50 engineering leaders at companies with 500+ staff): 72% say a new hire takes more than a month to reach their first three meaningful PRs, 18% say more than three months, and the most common answer is 1–3 months (54%). 40% name "finding context" as the most-cited developer pain point. Gathering context ties with waiting on approvals as the top productivity leak (26%). 58% estimate at least 5 hours per developer per week are lost. — [Cortex 2024 State of Developer Productivity](https://cortex.io/report/the-2024-state-of-developer-productivity)
- [Vendor survey] Qodo 2025 (n=609 developers): 65% of developers using AI for refactoring, and about 60% of those using it for testing, writing or review, say the assistant "misses relevant context". — [Qodo State of AI Code Quality 2025](https://www.qodo.ai/reports/state-of-ai-Code-quality/); [PR Newswire](https://www.prnewswire.com/il/news-releases/despite-78-claiming-productivity-gains-two-in-three-developers-say-ai-misses-critical-context-according-to-qodo-survey-302480084.html)

**Turnover cost**
- [Vendor survey] BlueOptima (benchmark of 400,000+ developers): it takes about 8 months on average to fully replace a developer who leaves, and about 4 more months for the new hire to reach consistent productivity. The leaver's output starts falling about 3 months before their last commit. — [BlueOptima, "8 Months"](https://www.blueoptima.com/resource/8-months-the-real-cost-of-replacing-software-developers)
- [Vendor claim] Cost-of-replacement rules of thumb range from 0.75x to 2x salary, and the "SHRM 100–200%" figure is usually cited without a primary link. — [daily.dev blog](https://daily.dev/blog/developer-retention-strategies-that-work/). Weak evidence; avoid in pitch material.

**Bus factor and open-source maintainers**
- [Measured] Avelino et al. 2016: across 133 popular GitHub projects, **65% have a truck factor of 2 or less**. — [arXiv 1604.06766](https://arxiv.org/abs/1604.06766v1). Versions differ: the PeerJ preprint reports 34% TF=1 and 30% TF=2. — [PeerJ preprint](https://peerj.com/preprints/1233)
- [Measured] Avelino et al. 2019: of 1,932 popular GitHub projects, 315 (16%) were abandoned by their truck-factor developers, and 41% of those survived because new core developers took over. The main barriers for newcomers were lack of time and difficulty getting push access. — [arXiv 1906.08058](https://arxiv.org/abs/1906.08058). A 2024 replication covers 36,464 projects. — [arXiv 2412.00313](https://arxiv.org/html/2412.00313v1)
- [Vendor survey] Tidelift 2024 (400+ maintainers): 60% are unpaid. Security work rose to 11% of their time, up from 4% in 2021. 61% of unpaid maintainers work alone. 66% are less trusting of PRs from non-maintainers after xz-utils. — [Business Wire, Tidelift 2024](https://www.businesswire.com/news/home/20240917030299/en/Tidelift-Study-Reveals-Paid-Open-Source-Maintainers-Do-Significantly-More-Critical-Security-and-Maintenance-Work-Than-Unpaid-Maintainers); [dev.to, Tidelift 3x security](https://dev.to/tidelift/maintainers-are-spending-3x-more-time-on-security-than-they-did-a-few-years-ago-3g89); [The New Stack](https://thenewstack.io/open-source-paid-maintainers-keep-code-safer-survey-says/)

**GitHub Octoverse 2025**
- [Measured, platform data] More than 5 million Indian developers joined GitHub in 2025, over 14% of all new accounts. India has 21.9 million developers on GitHub, second only to the US, and is projected to reach 57.5 million by 2030. Coverage of the report says India overtook the US as the largest base of open-source contributors. — [GitHub Octoverse 2025](https://github.blog/news-insights/octoverse/octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/); [Business Standard](https://www.business-standard.com/industry/news/github-india-57-million-developers-2030-ai-growth-125102801381_1.html); [Analytics India Magazine](https://analyticsindiamag.com/ai-news-updates/india-surpasses-us-as-worlds-largest-base-of-open-source-contributors-github-octoverse-2025)

### Inferences
- The strongest independent evidence is three measures: comprehension at about 58% of time (Xia), daily search time (Stack Overflow, 61–64% spend 30+ minutes), and "finding information" as the number one time-waster (Atlassian). Pitch material should lead with these rather than vendor dollar figures.
- The pain is uneven. 52% of developers never hit silos, but 30% hit them 10+ times a week. The buyer is therefore the team or organisation where knowledge is concentrated (legacy systems, high attrition, outsourced estates), not every team.
- The AI shift turns "why" knowledge from a nice-to-have into a prerequisite. Atlassian 2026 (65% correcting AI work that "missed the original intent"), Qodo (65% "misses relevant context") and Stack Overflow (87% concerned about agent accuracy; "data first") all point at missing intent and context. A decision graph with citations is a direct answer to that.
- A back-of-envelope cost: one hour a day searching across a 100-developer team is about 100 developer-hours a day (about 12 FTE). Salary multiples vary too much by market to quote one figure. Treat this as illustrative only.

### Gaps
- No 2025 Stack Overflow figure for time spent searching or knowledge silos was found; the 2025 survey dropped or changed those questions. The 2024 figures are the latest.
- I could not extract the seven DORA AI capability names from primary pages. Secondary coverage suggests they include internal data accessible to AI and strong version control practices, but this is unverified.
- I found no peer-reviewed, software-specific turnover-cost study. The dollar figures in circulation are vendor or blog estimates.
- The JetBrains State of Developer Ecosystem 2025 and Port's State of Internal Developer Portals were not checked in this pass.

## 2. Use cases: evidence of demand and what each needs from the product

### Takeaway
The use cases with the strongest combined evidence (measured pain, budget owner and regulatory pull) are: (1) decision context for AI coding agents via MCP; (2) handover and knowledge-risk when engineers or vendors leave; (3) change-rationale evidence for audits (SOC 2, ISO 27001, EU DORA, CRA); (4) dependency and CVE triage that explains why a pin or workaround exists; (5) onboarding. Incident "what changed" is high pain but crowded. M&A diligence and legacy modernisation are high value per engagement but services-heavy. OSS maintainer triage has low willingness to pay but is a useful distribution channel.

### Cited Findings

**Incident postmortems ("what changed before the outage?")**
- [Measured, practitioner] Google SRE: about 70% of outages are due to changes in a live system. — [Google SRE book, Introduction](https://sre.google/sre-book/introduction/)
- [Measured, Secondary] Uptime Institute Annual Outage Analysis 2025: configuration or change-management failure was the most common cause of major network outages (50%) and accounted for 62% of the most common causes of major IT system and software outages. Uptime links the rise to growing complexity, specifically change management and misconfiguration. — [Network World](https://www.networkworld.com/article/3980366/networking-errors-pose-threat-to-data-center-reliability.html); [Business Wire, Uptime 2025](https://www.businesswire.com/news/home/20250506733553/en/Uptime-Announces-Annual-Outage-Analysis-Report-2025). A 2026 edition exists, but its text could not be extracted. — [Uptime 2026 PDF](https://datacenter.uptimeinstitute.com/rs/711-RIA-145/images/2026.AnnualOutageAnalysis.pdf)
- [Measured] DORA 2025: AI adoption increases throughput but is still associated with higher delivery instability. — [Google blog, DORA 2025](https://blog.google/technology/developers/dora-report-2025/)

**Dependency upgrade research ("can we remove this pin or workaround?")**
- [Vendor survey, large dataset] Sonatype 2024: 80% of application dependencies go un-upgraded for over a year. When vulnerable components are consumed, a fixed version already exists 95% of the time. 3.6% of updated dependencies were updated to another vulnerable version. — [Sonatype SSCR 2024 introduction](https://www.sonatype.com/state-of-the-software-supply-chain/2024/introduction); [Sonatype press release](https://www.sonatype.com/press-releases/sonatypes-10th-annual-state-of-the-software-supply-chain-report)
- [Vendor survey] Endor Labs 2024 Dependency Management Report: security patches have a 75% chance of breaking the application, and 95% of version upgrades contain at least one breaking change. This explains why teams pin versions and why the reason for a pin matters. — [Infosecurity Magazine](https://www.infosecurity-magazine.com/news/open-source-updates-75-breaking/); [SecurityBrief UK](https://securitybrief.co.uk/story/75-of-security-patches-break-software-analysis-says); [Endor Labs report page](https://www.endorlabs.com/lp/2024-dependency-management-report)

**Security triage of CVEs against actual usage**
- [Vendor survey] Endor Labs 2024: fewer than 9.5% of vulnerabilities are reachable at the function level. In organisations with large phantom-dependency footprints, 56% of library vulnerabilities sit in phantom dependencies. — [Endor Labs report page](https://www.endorlabs.com/lp/2024-dependency-management-report); [Help Net Security](https://www.helpnetsecurity.com/2024/09/16/open-source-software-dependencies/). [Vendor claim] about 92% noise reduction from reachability. — [Endor Labs use case](https://www.endorlabs.com/use-case/sca-with-reachability)
- [Measured] Jerry Gamblin's count puts 2025 at 48,185 published CVEs, up 20.6% from 39,962 in 2024. Zafran counts 46,407. — [The Stack](https://www.thestack.technology/cves-in-2025-analysis/); [Zafran](https://www.zafran.io/resources/the-2025-spike-in-vulnerabilities-isnt-the-full-story)
- [Secondary] Zafran: only 28% of newly disclosed 2025 CVEs were fully analysed by NVD, down from 46.2% in 2024. Reports say NIST moved NVD to a triage model in April 2026 and reclassified a large backlog as "Not Scheduled". — [Zafran](https://www.zafran.io/resources/the-2025-spike-in-vulnerabilities-isnt-the-full-story); [Infosecurity Magazine](https://www.infosecurity-magazine.com/news/nvd-revamps-operations-cve-surge)
- [Conflicting] 2026 CVE volume: RuntimeWire counts 92,319 CVEs from January to October 2026 (2.24x the same period of 2025), and The Register reports the 2026 count passing 100,000. These are unreconciled. — [RuntimeWire](https://runtimewire.com/article/nvd-recorded-2-24-times-as-many-cves-from-january-through-october-as-in-the-same); [The Register](https://www.theregister.com/a/5309882)

**New-hire onboarding**
- See section 1: Cortex (72% take more than a month to first meaningful PRs), BlueOptima (about 4 months to consistent productivity), Xia (juniors spend more time on comprehension), Stack Overflow (time spent searching).
- [Vendor claim] Cortex suggests measuring onboarding as time to first commit or first milestone. — [Cortex blog](https://www.cortex.io/post/engineering-onboarding-the-key-to-devex-success)

**Handover when an engineer leaves**
- See section 1 (truck factor 65% ≤2; 16% abandonment; BlueOptima 8 months) and section 4 (Indian attrition and 90-day notice periods).

**Legacy modernisation and migration planning**
- [Analyst estimates, conflicting] 2026 market size: GII/Mordor put the legacy modernisation market at USD 29.39B in 2026, up from 24.98B in 2025. Technavio projects USD 24.97B of growth in application modernisation services over 2025–2030. — [GII Research](https://www.giiresearch.com/report/moi2035032-legacy-modernization-market-share-analysis.html); [Technavio](https://www.technavio.com/report/application-modernization-services-market-industry-analysis); [Mordor Intelligence](https://mordorintelligence.com/industry-reports/legacy-modernization-market)
- [Vendor survey] GAPVelocity AI: of 1,105 organisations that asked about modernising an application between August 2025 and August 2026, 67.6% named VB6. — [GAPVelocity 2026 PDF](https://www.gapvelocity.ai/hubfs/1-Website%20Assets/State_of_Legacy_Modernization_Demand_2026.pdf)
- [Market signal] Swimm, previously a per-seat code-documentation tool, now prices as engagement-based services ("Application Delivery, System Intelligence, AI Operability"). It starts with a one-week paid "grounding" engagement on a sample of the customer's code. — [Swimm pricing](https://swimm.io/pricing). Third-party listings still show old per-seat prices of $9–$39 that conflict with each other. — [Capterra](https://www.capterra.com/p/227606/Swimm/)

**Tech due diligence in M&A and investment**
- [Measured, consultancy survey] KPMG (September 2025, 135 US organisations, tech debt in M&A): the most common AI use is automated code refactoring or legacy code analysis (52%). — [KPMG, How AI can help reduce tech debt in M&A](https://kpmg.com/kpmg-us/content/dam/kpmg/pdf/2025/how-ai-can-help-reduce-tech-debt-in-ma.pdf)
- [Vendor claim] Black Duck: software diligence covers open-source licence obligations, security and code-quality risk, and the target's SDLC organisation and practices. Material findings can be priced into the deal. — [Black Duck, technology due diligence](https://www.blackduck.com/blog/technology-due-diligence.html)

**Open-source maintainer triage and contributor onboarding**
- See Tidelift and Avelino in section 1. Newcomer barriers include lack of time and difficulty getting push access. 66% of maintainers distrust PRs from non-maintainers after xz.
- [Regulation] CRA obligations for open-source software stewards (Article 24) apply from 11 December 2027. — [European Commission, CRA reporting](https://digital-strategy.ec.europa.eu/en/policies/cra-reporting)

**AI coding agents needing decision context (MCP server)**
- [Secondary] MCP Python and TypeScript SDKs together reached about 97 million monthly downloads by March 2026, and there are more than 10,000 public servers. These figures come from secondary blogs, not primary registry data. — [Pragmatic Engineer, MCP deep dive](https://newsletter.pragmaticengineer.com/p/mcp-deepdive); [dev.to](https://dev.to/gentic_news/mcp-hits-10k-servers-97m-monthly-sdk-downloads-by-may-2026-1jbk)
- [Vendor survey] Stacklok State of MCP in Software 2026 (senior technical leaders at software companies; not global): 41% have MCP servers in limited (29%) or broad (12%) production. 49% cite security and compliance as the top challenge, and 34% cite governance. — [Stacklok report](https://stacklok.com/resources/state-of-mcp-in-software-2026/); [PDF](https://stacklok.com/wp-content/uploads/2026/01/State-of-MCP-in-Software-2026_FINAL.pdf)
- [Market signal] Unblocked already sells "context" Q&A about "your software and its history", with an MCP connector to Claude, Cursor and Copilot, for $29/user/month. — [Unblocked pricing](https://getunblocked.com/pricing)
- Supporting demand data: Atlassian 2026 (65% correcting AI work that missed the original intent), Qodo 2025 (65% "misses relevant context"), and Stack Overflow 2025 (87% concerned about agent accuracy; "data first"). All are in section 1.

**Code review context ("this PR reverts a past decision")**
- [Vendor survey] Qodo 2025: about 60% of developers using AI for code review say it misses relevant context. — [Qodo](https://www.qodo.ai/reports/state-of-ai-Code-quality/)
- [Market signal] AI code review is an established paid category: CodeRabbit sells per-developer tiers and Greptile charges $30/seat/month (see section 5).

**Architecture review and ADR hygiene**
- No measured data found (see Gaps).

### Inferences
Prioritised use cases. The ranking weighs strength of evidence, budget owner, regulatory pull, and fit with what Untangle already ingests.

| # | Use case | Primary persona and buyer | Demand evidence (strength) | What the product needs |
|---|---|---|---|---|
| 1 | **Decision context for AI coding agents (MCP)** | Developers using Claude Code or Cursor; buyer: platform or DevEx lead | Atlassian 2026 65% "missed original intent"; Qodo 65% "misses context"; Stack Overflow 87% accuracy concern; a competitor (Unblocked) is already priced (strong) | MCP server with tools such as `why(file\|symbol\|line)`, `decisions_touching(path)`, `superseded?(decision)` and `who_to_ask(path)`; answers that carry citations and supersession status; permission-aware retrieval that mirrors repo ACLs (security is the number one MCP blocker at 49%); low latency; incremental re-index on push |
| 2 | **Handover, offboarding and knowledge-risk radar** (including vendor-to-vendor or vendor-to-GCC transitions in India) | Engineering manager, delivery or transition manager; buyer: EM, VP Eng, IT-services delivery head | Truck factor ≤2 in 65% of popular projects; about 13% annual attrition at large Indian IT firms; 90-day notice periods justified as KT time; BlueOptima 8 months to replace (strong) | Per-person ownership and "only-X-knows" detection; KT plans generated from the graph; ingestion of recorded handover calls with Hinglish speech-to-text and code-mixed entity linking; question lists for the leaver; a KT-completeness score; export to the customer's wiki or Confluence |
| 3 | **Change-rationale evidence for audit** (SOC 2 CC8.1, ISO 27001 A.8.32, EU DORA RTS Art. 17, CRA Annex VII, FDA) | Compliance or GRC lead, CISO; buyer with larger budgets | Auditors sample changes and match production to approved requests that state a reason; DORA requires documented purpose and expected outcomes; CRA requires architecture and design information and a risk assessment kept for 10 years (strong regulatory pull) | Traceability PR → ticket → decision → approval → deploy, plus gap reports (merged with no ticket or no rationale, emergency changes without retrospective approval); immutable, exportable evidence packs; data retention controls; CRA technical-file drafts (architecture narrative, support-period rationale, SBOM links) |
| 4 | **Dependency and CVE triage with "why is this pinned?"** | Security engineer, maintainer, platform team; buyer: AppSec | Sonatype 80% un-upgraded, 95% fix available; Endor 75% of patches break; under 9.5% reachable; about 48k CVEs in 2025 and a shrinking NVD analysis share (strong but crowded) | Link each pin, override or workaround to its originating PR or issue and to the upstream issue or changelog; EOL data (for example endoflife.date); "can we remove it?" check against upstream fixed versions; a usage map of where the package is called; VEX justification drafts that cite the decision |
| 5 | **New-hire onboarding** | New engineer; buyer: EM | Cortex 72% take more than a month; Xia: juniors spend more time on comprehension; Stack Overflow search time (moderate) | Guided "why tours" per service; a glossary; a feature/commit map; ranked "start here" decisions; an onboarding-progress metric |
| 6 | **Incident "what changed"** | SRE or on-call; buyer: SRE lead | About 70% of outages come from changes; Uptime 50–62% change or configuration (strong pain, crowded market) | A time-window query across code, config and dependency diffs and deploys; PagerDuty or incident-tool hooks; "previous incidents touching this area"; postmortem draft with citations |
| 7 | **Code review: "this PR reverts a past decision"** | Reviewer; buyer: EM or platform | Qodo about 60% say review misses context; the AI review category already exists (moderate) | A PR bot that comments when a diff touches code governed by an active decision or ADR, or re-introduces a superseded approach |
| 8 | **Legacy modernisation and migration planning** | Modernisation architect, SI partner; buyer: CIO, SI | Market about $25–30B (analyst); Swimm's pivot to services (moderate) | Bulk ingestion of old VCS (SVN/TFS), sparse-metadata handling, business-rule extraction with citations, on-prem or VPC deployment |
| 9 | **Tech due diligence (M&A, PE)** | Diligence consultant; buyer: deal team or advisory firm | KPMG 52% using AI for legacy code analysis in M&A context (moderate; episodic) | Fast time-boxed ingestion; risk report (bus factor, key-person risk, abandoned decisions, dependency EOL); read-only data room mode |
| 10 | **OSS maintainer triage and contributor onboarding** | Maintainer; low willingness to pay (60% unpaid) | Tidelift; Avelino; CRA steward duties from December 2027 (channel value more than revenue) | Free hosted tier for public repos; "why was this rejected before?" on new issues and PRs; contributor guides from decision history |
| 11 | **Architecture review and ADR hygiene** | Architect | No measured data | Detect decisions without ADRs; ADR drafts from PR and issue threads; supersession links. Better as a feature than a product |

- Use cases 1 and 3 complement each other: the same cited decision graph serves a developer-facing agent tool and a compliance-facing evidence export. That supports a bottom-up land (MCP, priced per seat) followed by a top-down expansion (compliance or enterprise).
- Internet research (CVEs, upstream changelogs, library issues, EOL data) mostly strengthens use case 4 and partly use case 6. It is a differentiator only if it is joined to internal decision history ("we pinned X because of upstream issue #123, which was fixed in 2.4"). On their own, CVE feeds are commodity.

### Gaps
- No measured data on how often PRs re-introduce previously rejected or superseded approaches. The code-review use case rests on inference.
- No survey data on ADR adoption or ADR staleness.
- No study quantifying postmortem time spent reconstructing "what changed".
- No public figure on what share of M&A tech diligence findings change price or terms.
- The 2026 Uptime figures for change-related outages could not be extracted.

## 3. Compliance and audit drivers: what evidence about "why a change was made" is required?

### Takeaway
Regulation requires documented change rationale in several regimes. EU DORA's change-management RTS (applies to EU financial entities since 17 January 2025) explicitly requires documenting each change's purpose, scope and expected outcomes. SOC 2 and ISO 27001 auditors sample changes for approved requests that state a reason. The CRA's technical documentation (enforced from 11 December 2027, reporting live since 11 September 2026) requires architecture and design information, a risk assessment and an SBOM, kept for 10 years. FDA requires software configuration-management documentation and SBOMs for cyber devices. None of these regimes requires a "decision graph", but each produces audit questions that one can answer.

### Cited Findings

**EU Cyber Resilience Act (Regulation (EU) 2024/2847)**
- [Regulation] Manufacturers' reporting obligations apply from **11 September 2026**: actively exploited vulnerabilities and severe incidents are reported through ENISA's Single Reporting Platform, which went live that day. Deadlines are a 24-hour early warning and a 72-hour notification. Final reports are due 14 days after a corrective measure is available (exploited vulnerabilities) or within one month of the 72-hour notification (severe incidents). Open-source steward reporting starts **11 December 2027**. — [European Commission, CRA reporting](https://digital-strategy.ec.europa.eu/en/policies/cra-reporting)
- [Secondary] The remaining substantive obligations apply from **11 December 2027**: essential requirements, vulnerability handling, technical documentation and conformity assessment. Reporting covers products already on the market. Fines for reporting breaches reach €15M or 2.5% of worldwide turnover. — [CMS](https://cms.law/en/lux/legal-updates/ready-respond-report-the-cyber-resilience-act-s-reporting-regime-is-here); [Kirkland](https://www.kirkland.com/publications/kirkland-alert/2026/09/the-eu-cyber-resilience-act); [CSA research note](https://labs.cloudsecurityalliance.org/research/csa-research-note-eu-cra-reporting-deadline-20260903-csa-sty/)
- [Regulation] Annex VII (technical documentation) requires:
  - design and development information, including a description of the system architecture explaining how software components build on or feed into each other;
  - vulnerability-handling specifications, including the SBOM, the coordinated vulnerability disclosure policy, a reporting contact and the secure update distribution method;
  - a cybersecurity risk assessment;
  - the information used to set the support period;
  - the harmonised standards applied, or a description of alternative solutions;
  - test reports;
  - the EU declaration of conformity.
  The SBOM is supplied to market surveillance authorities on request and need not be public. — [Annex VII text, Springlex](https://www.springlex.eu/en/packages/cra/cra-regulation/annex-7/)
- [Secondary] Technical documentation must be kept for at least 10 years or for the support period, whichever is longer. — [Revenera CRA checklist](https://resources.flexera.com/web/eloqua/pdf/Revenera-EU-CRA-Checklist.pdf)
- [Secondary] The Digital Omnibus proposal (19 November 2025, procedure 2025/0360(COD)) would create a single incident-reporting entry point covering NIS2, GDPR, DORA, CER, eIDAS and the CRA, built on the CRA platform. It was still under Council negotiation as of March 2026. German industry criticised it for not reforming the CRA itself. — [Bird & Bird](https://cm.twobirds.com/en/insights/2025/digital-omnibus-package-single-eu-harmonised-incident-reporting-regime-across-cyber-and-data-protect); [Taylor Wessing](https://www.taylorwessing.com/de/global-data-hub/2026/the-digital-omnibus-proposal/gdh---the-digital-omnibus-and-incident-reporting); [EP Legislative Observatory](https://oeil.europarl.europa.eu/oeil/en/document-summary?id=1866785)

**SBOM (US)**
- [Regulation] CISA published a draft *2025 Minimum Elements for an SBOM* on 22 August 2025, with comments closing 3 October 2025. It adds component hash, licence, tool name and generation context. — [CISA 2025 Minimum Elements](https://www.cisa.gov/resources-tools/resources/2025-minimum-elements-software-bill-materials-sbom); [CISA alert](https://www.cisa.gov/news-events/alerts/2025/08/22/cisa-requests-public-comment-updated-guidance-software-bill-materials)
- [Secondary] The 2026 Minimum Elements were released in late July 2026 with international co-authors and replace the 2021 NTIA guidance. They add hash algorithm, licence, generation tool and generation context, and a digital signature is discussed. They point to VEX and CSAF for linking SBOMs to vulnerability status. The binding status is not stated in the coverage. — [Help Net Security](https://www.helpnetsecurity.com/2026/07/30/cisa-sbom-guidance-updated/); [Australian Cyber Security Centre](https://www.cyber.gov.au/publication/2026-minimum-elements-for-a-software-bill-of-materials-sbom)

**SOC 2 (CC8.1) and ISO 27001 (A.8.32)**
- [Secondary, practitioner] SOC 2 CC8.1 auditors sample change records to verify authorisation and testing, compare production changes against approved requests, and check emergency changes for retrospective approval. A change request is expected to record the reason for the change, affected systems, owner, risk or impact assessment, implementation plan and rollback plan. A common control is that no PR merges without a linked ticket. — [soc2auditors.org](https://soc2auditors.org/insights/soc-2-change-management-controls/); [Sprinto](https://sprinto.com/blog/soc-2-change-management/); [Linford & Co](https://linfordco.com/blog/change-management-risks/). These are not the AICPA text.
- [Secondary, practitioner] ISO 27001:2022 A.8.32 replaces the 2013 controls 12.1.2 and 14.2.2–14.2.4. The ISO 27002 guidance lists procedure elements including impact assessment that considers dependencies, and updating operating documentation when changes occur. — [ISMS.online](https://www.isms.online/iso-27001/annex-a-2022/8-32-change-management-2022/); [Advisera](https://advisera.com/iso27001/control-8-32-change-management/)

**EU DORA (Digital Operational Resilience Act, financial entities)**
- [Regulation] DORA entered into force on 16 January 2023 and applies from **17 January 2025** to 20–21 types of financial entities (EIOPA and ESMA give different counts). — [ESMA, DORA](https://www.esma.europa.eu/digital-operational-resilience-act-dora); [ESAs public statement](https://www.eba.europa.eu/sites/default/files/2024-12/0133f341-fcf5-48d1-812b-d0a66e2b3e8c/JC%202024%2099_ESAs%20Public%20Statement%20on%20DORA%20application%20%281%29.pdf)
- [Regulation] Delegated Regulation (EU) 2024/1774, Article 17 (ICT change management), requires financial entities to:
  - document and communicate change details, including **purpose, scope, implementation timeline and expected outcomes**;
  - keep the functions that approve changes independent;
  - set fall-back and abort procedures;
  - document, re-assess and approve emergency changes after implementation;
  - assess each change's impact on existing ICT security measures.
  — [Springlex, RTS Article 17](https://www.springlex.eu/en/packages/dora/rts-rmf-regulation/article-17/)
- [Regulation, Secondary] DORA Article 8(3) requires a risk assessment on each major change to network and information systems. — [FMA Austria](https://www.fma.gv.at/en/dora-ict-risk-management/); see also [MFSA, ICT change management under DORA](https://www.mfsa.mt/publication/ict-change-management-under-the-digital-operational-resilience-act-dora/)

**NIS2**
- [Regulation] Commission Implementing Regulation (EU) 2024/2690 sets technical requirements for the NIS2 Article 21(2) measures. Its Annex section 6.4 covers "change management, repairs and maintenance". It applies directly to certain digital-infrastructure and digital-service entities, and national authorities may use it to interpret NIS2 for other sectors. — [EUR-Lex 2024/2690](https://eur-lex.europa.eu/eli/reg_impl/2024/2690/oj/eng); [Hunton](https://huntonak.com/privacy-and-information-security-law/implementing-regulation-developing-nis2-rules-for-certain-digital-service-providers-enters-into-force); [ENISA implementation guidance](https://enisa.europa.eu/publications/implementation-guidance-on-nis-2-security-measures/@@download/fullReport)

**FDA (medical device software)**
- [Regulation] *Content of Premarket Submissions for Device Software Functions* (final, 14 June 2023) replaces the 2005 Level of Concern approach with Basic and Enhanced documentation levels. It covers software development, configuration management and maintenance practices, and includes architecture-diagram examples. — [FDA guidance page](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/content-premarket-submissions-device-software-functions); [Federal Register](https://www.govinfo.gov/content/pkg/FR-2023-06-14/html/2023-12723.htm)
- [Regulation] FD&C Act section 524B requires SBOMs in submissions for "cyber devices". FDA finalised the select 524B updates to its premarket cybersecurity guidance on 27 June 2025, and has expected 524B content since 1 October 2023. — [Federal Register, June 2025](https://www.govinfo.gov/content/pkg/FR-2025-06-27/html/2025-11669.htm); [FDA cybersecurity FAQ](https://www.fda.gov/medical-devices/digital-health-center-excellence/cybersecurity-medical-devices-frequently-asked-questions-faqs); [King & Spalding](https://www.kslaw.com/insights/articles/fda-finalizes-premarket-cybersecurity-guidance-for-medical-devices)

### Inferences
- **Evidence auditors and regulators ask for, mapped to Untangle features:**
  - *Reason and purpose of each change*: SOC 2 change-request contents; DORA Art. 17 "purpose, scope, expected outcomes". Untangle needs to extract the rationale from PR, ticket and ADR text and flag changes with none.
  - *Approval and segregation*: SOC 2 and DORA (approver independence). Untangle needs a reviewer/approver per change and the reviewer-versus-author relationship.
  - *Production reconciled to approved requests*: SOC 2. Untangle needs deploy or commit coverage reports listing changes with no linked ticket or decision.
  - *Emergency changes justified after the fact*: SOC 2 and DORA. Untangle needs detection of hotfix or bypass merges and a post-hoc rationale workflow.
  - *Impact on dependencies and security measures*: ISO 27002 8.32 and DORA. Untangle needs the feature/commit impact map and dependency diffs.
  - *Architecture and design rationale with risk assessment, kept for 10 years*: CRA Annex VII. Untangle needs exportable, versioned design-rationale narratives with citations to source evidence.
  - *SBOM plus vulnerability status*: CRA, CISA 2026, FDA 524B. Untangle should link SBOM components to the decisions that introduced or pinned them and draft VEX "not affected" justifications with citations.
- The CRA's 24-hour and 72-hour reporting clock (live since September 2026) is the most time-pressured new driver. A product that answers "which versions and components are affected, and why do we use them?" in minutes fits incident triage for CRA reporting.
- Compliance buyers will want write-once, exportable evidence and retention controls more than chat. The compliance use case needs non-chat surfaces (reports, exports, auditor read-only access).

### Gaps
- The exact AICPA points of focus for CC8.1 and the ISO 27002:2022 8.32 wording were not checked (paywalled or not fetched); only practitioner summaries were used.
- The EUR-Lex text of 2024/2690 section 6.4 could not be extracted, so its record-keeping specifics are unverified.
- I did not verify whether the CRA conformity-assessment-body provisions (Chapter IV, reported elsewhere as applying from 11 June 2026) are on schedule.
- Whether CISA's 2026 SBOM minimum elements are binding on federal suppliers (for example through OMB memos) was not confirmed.
- EO 14028 (May 2021) was not re-checked against a primary source in this pass, and later executive actions affecting SBOM attestation were not reviewed.

## 4. Indian market context: IT services KT culture, attrition and vendor transitions

### Takeaway
At about 13% LTM attrition on headcounts of hundreds of thousands, plus standard 90-day notice periods justified explicitly as "knowledge transfer" time, Indian IT services runs a constant, high-volume handover process. Vendor-to-vendor and vendor-to-GCC transitions (2,117 GCCs, 2.36M staff) add a second stream. KT is still largely meeting-based (shadow and reverse-shadow phases). Recorded, code-mixed (Hinglish) KT calls linked to code are a plausible, underserved wedge, but there is no hard data on KT cost.

### Cited Findings
- [Company disclosures, Secondary] Q2 FY27 (quarter to 30 September 2026): TCS reported LTM attrition in IT services of 13.3% (13.6% in the prior quarter) and headcount of 598,056 after a net addition of 4,258. — [People Matters](https://www.peoplematters.in/amp/news/recruiting-and-onboarding/tcs-adds-4258-employees-onboarded-10000-freshers-in-q2-52615); [Finology Ticker](https://ticker.finology.in/discover/market-update/tcs-q2-fy27-results-analysis)
- [Company disclosures, Secondary, conflicting] Q2 FY26 (September 2025), by source:
  - People Matters: Wipro 13.8% voluntary, Infosys 12.7% LTM, HCLTech 12.8% LTM (excluding involuntary and DPO), TCS 13.3%.
  - Analytics India Magazine: Wipro 14.9%, HCLTech 12.6%, Infosys 14.3%, TCS 13.3%, and rates at their lowest in about five years.
  Definitions differ between firms. — [People Matters](https://www.peoplematters.in/news/business/indian-it-hiring-in-q2-hcltech-adds-6450-employees-as-wipro-loses-6716-52954); [Analytics India Magazine](https://analyticsindiamag.com/it-services/indias-top-it-firms-stabilise-workforce-while-driving-ai-focused-reskilling)
- [Secondary] TCS cut its workforce by nearly 20,000 in Q2 FY26 amid restructuring, and skipped publishing an attrition rate for that quarter. — [Business Today](https://www.businesstoday.in/latest/corporate/story/tcs-q2-fy26-results-it-giants-workforce-shrinks-by-nearly-20000-in-q2-fy26-amid-restructuring-497579-2025-10-09); [The Wire](https://thewire.in/labour/tcs-sheds-nearly-20000-jobs-in-q2-surpassing-its-earlier-layoff-plan)
- [Secondary] Notice periods: almost 1 in 3 Indian IT roles carries a 90-day notice period. HCLTech has justified three months as necessary for "efficient knowledge transfer to ensure business continuity", while employees argue KT takes 15–20 days. — [Analytics India Magazine, notice periods](https://analyticsindiamag.com/report-notice-periods-in-india-it/); [Free Press Journal](https://www.freepressjournal.in/pune/exploitation-it-professionals-in-punes-hinjawadi-magarpatta-kharadi-speak-out-against-90-day-notice-period)
- [Measured, academic] Williams (Information Systems Journal, 2010), survey of 140 offshore software engineers in India: formal knowledge transfer (training and documentation) had a strong effect on engineers' understanding of the client. Embedment helped only those with onshore experience. Informal offshore discussion had no significant effect. — [BCS, "A steep learning curve"](https://www.bcs.org/articles-opinion-and-research/a-steep-learning-curve/)
- [Measured, academic] A TCS case study identifies eight practices for managing dispersed expertise, including formal KT and knowledge-retention methodologies. — [LSE Research Online](https://researchonline.lse.ac.uk/id/eprint/24105)
- [Vendor claim] Practitioner KT plans use shadow then reverse-shadow phases. Reverse KT should be planned from contract signing and typically includes 60–90 days of vendor availability after transition. An "IDC 2024: shadow-based KT cuts time-to-productivity 35%" figure circulates, but I could not verify it. — [Opsio blog](https://opsiocloud.com/in/blogs/knowledge-transfer-plan-it-outsourcing/)
- [Measured, industry body] Nasscom-Zinnov GCC Landscape 2026 (May 2026): 2,117 GCCs in India employing 2.36M people, with about USD 98.4B FY26 revenue and 100+ new centres in FY26. — [Zinnov–Nasscom report](https://zinnov.com/centers-of-excellence/zinnov-nasscom-india-gcc-landscape-2026-report/); [YourStory](https://yourstory.com/enterprise-story/2026/05/gccs-number-touch-2117-in-india-revenue-just-short-of-100-billion)
- [Measured, platform data] India has 21.9M GitHub developers and added 5M+ in 2025. — [GitHub Octoverse 2025](https://github.blog/news-insights/octoverse/octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/)

### Inferences
- Rough scale: 13.3% attrition on about 598,000 TCS employees implies roughly 80,000 departures a year at one firm. Each departure from a delivery role triggers some KT. Across the top four firms this is hundreds of thousands of handovers a year. These are calculations from the figures above, not reported numbers.
- KT in Indian IT services is contractually and culturally formalised (notice periods justified by KT, shadow and reverse-shadow phases, transition contracts). It is also mostly verbal, in mixed Hindi-English. A product that records KT calls, transcribes Hinglish, and links statements to commits, PRs and decisions turns a ritual into durable, searchable evidence. That evidence could also serve client-side "transition acceptance" checks.
- GCC growth (vendor work insourced into captive centres) and vendor consolidation produce transitions where the incoming team has no access to the outgoing team's tacit knowledge. A transition-readiness report ("decisions with only one knowledgeable person", "areas with no recorded rationale") gives the incoming party leverage, and the client may pay for it.
- Buyers in India differ from the US/EU per-seat model. Likely buyers are delivery or transition heads at IT services firms (who could resell to clients as part of transition services) and GCC engineering leaders. Per-seat prices of USD 20–60/month look high against Indian engineer salaries. Per-transition or per-repository pricing may fit better. This is speculative and needs validation.

### Gaps
- No Nasscom or analyst figure was found for the cost or duration of KT/transition phases in IT outsourcing contracts, or for how often transitions fail.
- No data found on Hinglish/code-mixed speech-to-text accuracy for technical meetings. This should be tested directly.
- Infosys, Wipro and HCLTech attrition for Q2 FY27 was not retrieved; only TCS was confirmed.
- No survey found on whether Indian IT firms record KT sessions today, or on client-contract clauses requiring KT documentation.

## 5. Willingness to pay and buyer: who buys and at what price?

### Takeaway
Adjacent tools have established per-seat price points of about USD 19–72 per user per month. Developer context and code-intelligence tools cluster at USD 19–59 (Sourcegraph USD 19/59, Unblocked USD 29/35), and developer portals and AI review at USD 24–72 (Port USD 30/48, CodeRabbit USD 24–72, Greptile USD 30). Enterprise tiers add SSO, on-prem deployment and permission enforcement. Swimm's move from per-seat documentation to services-led modernisation engagements suggests documentation alone is hard to sell per seat. The budget sits with platform or DevEx leads for agent context, with compliance or security for audit evidence, and with services and diligence firms per engagement.

### Cited Findings
- [Vendor pricing] Sourcegraph: Enterprise Starter at USD 19/user/month (teams up to 50 developers). Enterprise (Dedicated Cloud or Self-Hosted) at USD 59/user/month for 25+ developers. — [Sourcegraph Enterprise pricing](https://sourcegraph.com/docs/pricing/enterprise); [Sourcegraph Enterprise Starter changelog](https://sourcegraph.com/changelog/enterprise-starter). A USD 16k annual Enterprise minimum is buyer-reported via a competitor blog and weakly sourced. — [Activepieces](https://www.activepieces.com/blog/sourcegraph-pricing-2026-plans-costs-and-minimums)
- [Vendor pricing] Unblocked: Platform at USD 29/user/month annual or USD 35 monthly, with a 21-day trial. It includes context Q&A about "your software and its history", MCP connectors to Claude, Cursor and Copilot, an autonomous coding agent and API access. Enterprise (custom price) adds SSO, "Data Shield" permission enforcement, on-prem options and GitHub Enterprise, Jira DC and Bitbucket DC support. Integrations cover GitHub, GitLab, Bitbucket, Slack, Jira and Confluence. The vendor states SOC 2 Type II. — [Unblocked pricing](https://getunblocked.com/pricing). A tracker shows the earlier USD 19 tier was removed in 2026. — [PricingSaaS](https://pricingsaas.com/companies/unblocked/diffs/2026W44)
- [Vendor pricing] Port (internal developer portal): Free up to 5 seats; Basic from USD 30/seat/month (annual, up to 50 seats); Standard from USD 48/seat/month (adds SSO and fine-grained permissions); Enterprise is a platform fee plus per-seat. — [Port pricing](https://www.port.io/pricing)
- [Secondary pricing] CodeRabbit: Essentials USD 24 (annual) or USD 30 (monthly); Team USD 48; Advanced USD 72 per developer per month; Enterprise is custom. Tier names have changed over time. — [dev.to, CodeRabbit pricing 2026](https://dev.to/rahulxsingh/coderabbit-pricing-in-2026-free-tier-pro-plans-and-enterprise-costs-1pc4); official page [CodeRabbit pricing](https://www.coderabbit.ai/pricing?utm_category=ai) (not fetched)
- [Secondary pricing] Greptile: USD 30/seat/month including 50 credits, then USD 1 per extra credit. Billing is tied to active PR authors. — [dev.to, Greptile review](https://dev.to/jovan_chan_9500711396d4e6/greptile-review-2026-82-bug-catch-rate-the-1review-trap-and-who-should-pay-30month-4jao); [Sacra](https://sacra.com/chat/h/cdc3466e-6cd4-4188-a63d-3d092687c2df/)
- [Vendor pricing] Swimm: no public per-seat pricing. Engagements start with a one-week paid grounding sample under NDA, and the fee is credited to the follow-on work. — [Swimm pricing](https://swimm.io/pricing)
- [Vendor survey] Cortex 2024 (n=50 leaders): coding assistants are the top planned investment, 37% plan build and test optimisation tools, and 33% plan internal developer portals. The average importance placed on improving productivity this year is 8.2/10. — [Cortex 2024](https://cortex.io/report/the-2024-state-of-developer-productivity)
- [Vendor survey] Stacklok 2026: security and compliance (49%) and governance (34%) are the top blockers for MCP rollouts. Security sign-off is therefore part of the buying process for any agent-context product. — [Stacklok](https://stacklok.com/resources/state-of-mcp-in-software-2026/)
- [Vendor survey] Atlassian 2025: 63% of developers say leaders do not understand their pain points. The person who feels the pain (the IC) is often not the budget holder. — [Atlassian 2025](https://www.atlassian.com/blog/developer/developer-experience-report-2025)

### Inferences
- **Buyer map:**
  - Agent context, onboarding and code review: platform engineering or DevEx lead, or VP Engineering. Per seat, USD 20–40 per month (anchored by Unblocked at USD 29 and Sourcegraph Starter at USD 19).
  - Audit evidence and CRA technical file: CISO, GRC or compliance, often a separate budget line, priced per product, repository or org rather than per developer. Likely higher price, but more security review and procurement.
  - Dependency and CVE triage: AppSec. Competes with SCA tools (Endor, Sonatype, Snyk), so position as "rationale and remediation history" added to SCA output, not as a replacement.
  - Handover and transitions: EMs, IT-services delivery heads and GCC leaders. Likely per transition or per repository, especially in India.
  - Diligence and modernisation: advisory firms or SIs, per engagement (Swimm's model).
- Enterprise must-haves: SSO and SCIM, permission enforcement that mirrors source ACLs, on-prem or VPC deployment, support for self-hosted Git and Jira (DC), and no training on customer data. Every competitor lists these.
- Differentiation for Untangle against Unblocked or Sourcegraph: explicit decision objects with supersession and timelines (not only retrieval Q&A); recorded handover calls, including Hinglish; and compliance-grade evidence exports. Unblocked's MCP and history Q&A at USD 29 means "cited why answers via MCP" alone is not a moat.

### Gaps
- Cortex, DX (acquired by Atlassian), Jellyfish, LinearB and Glean pricing were not retrieved.
- No public data on willingness to pay specifically for knowledge-transfer or handover tooling, or for CRA technical-documentation tooling.
- No data found on what IT services firms currently spend per transition on KT (labour or tooling).
- CodeRabbit and Greptile prices come from secondary sources; their official pages were not verified in this pass.
