# Academic and technical methods for recovering design rationale and decision knowledge from software repositories (as of November 2026)

Scope note: these notes cover research methods, datasets and reported accuracy that Untangle could adopt for its Decision extraction (subject/predicate/value, valid_from/valid_to, SUPERSEDES), knowledge-risk ranking (contradiction, drift, ownership gap, rationale gap, staleness) and person-to-ask suggestions. Numbers are quoted as reported by each source. Where I only saw an abstract or a search snippet, that is flagged. arXiv IDs with a 26xx prefix are 2026 preprints.

## 1. Design rationale mining from commits, PRs, issues and mailing lists, and how accurate LLM extraction is

### Takeaway
Rationale is almost always present in good commit messages, but it is spread across artifacts: commits and PRs carry the GOAL, while NEED and ALTERNATIVES tend to sit in issues and PRs. LLM extraction gets high recall but low-to-moderate precision (about 27-51% precision in the two best-measured studies). A required supporting quote plus a precision-oriented verifier is the right design, and cross-artifact joining (commit + PR + linked issue) is necessary.

### Cited Findings
- **Taxonomy (foundational).** Al Safwan & Servant, "Decomposing the Rationale of Code Commits: The Software Developer's Perspective", ESEC/FSE 2019. From interviews with 20 developers and a survey of 24 more, they decompose commit rationale into 15 components, including goal, need, benefits and constraints. — [FSE'19 PDF](https://people.cs.vt.edu/~khsaf/public/papers/fse19.pdf)
- A JSS 2022 follow-up ("Developers' need for the rationale of code commits: An in-breadth and in-depth study") shows that each of the 15 components is needed, found and recorded to different degrees. — [RIUMA record](https://riuma.uma.es/entities/publication/1aed5207-cc82-47c3-b1aa-adebdfe80dbd); Al Safwan's 2023 Virginia Tech dissertation consolidates both. — [Dissertation PDF](https://people.cs.vt.edu/~khsaf/public/papers/Alsafwan_KA_D_2023.pdf)
- **Linux kernel rationale dataset.** Dhaouadi, Oakes & Famelis, "Rationale Dataset and Analysis for the Commit Messages of the Linux Kernel Out-of-Memory Killer", ICPC 2024. Each sentence is labelled Decision, Rationale, Supporting Facts or Inapplicable by three raters. 98.9% of commits contain rationale sentences, and experienced developers put rationale in about 60% of their commit sentences. The data is on Zenodo. — [arXiv 2403.18832](https://arxiv.org/abs/2403.18832); [ICPC listing](https://conf.researchr.org/details/icpc-2024/icpc-2024-research/20/Rationale-Dataset-and-Analysis-for-the-Commit-Messages-of-the-Linux-Kernel-Out-of-Mem); [Zenodo v2](https://zenodo.org/records/10063089)
- **Kantara (rationale knowledge graph).** Dhaouadi et al.'s architecture for extracting and managing rationale as a KG, applied to 180 commits from a Linux subsystem. — [arXiv 2311.03358](https://arxiv.org/abs/2311.03358)
- **Automated extraction plus conflict and erosion detection.** Dhaouadi, Oakes & Famelis, "Automated Extraction and Analysis of Developer's Rationale in Open Source Software" (arXiv, April 2025). It instantiates Kantara with pre-trained models and LLMs, and adds structure-based mechanisms that detect reasoning conflicts with past decisions and possible design erosion. Evaluated on OOM-Killer plus five other active OSS projects. The abstract claims "effective" extraction but gives no numbers. — [arXiv 2506.11005](https://arxiv.org/abs/2506.11005)
- **Cross-artifact rationale recovery (closest to Untangle).** Sun, Saha, De Silva, Mastropaolo & Chaparro, "Recovering Fine-Grained Code Change Rationale from Multiple Software Artifacts" (arXiv, April 2026, revised July 2026). The study covers 63 commits from 5 Java projects and uses 9 taxonomy components, 7 of which occur in practice. Commit messages and PRs mainly capture GOAL, while NEED and ALTERNATIVE are more often in issues and PRs, and no single artifact type holds all components. Their LLM approach ARGUS identifies GOAL/NEED/ALTERNATIVE sentences at **51.4% precision and 93.2% recall**, and 12 Java programmers in a user study rated its summaries accurate. Identification varied across LLMs; summaries were consistently accurate. — [arXiv 2604.10345](https://arxiv.org/abs/2604.10345)
- **LLM-generated architecture rationale vs. human experts.** Zhou, Li, Liang, Zhang, Shahin, Li & Yang, "Using LLMs in Generating Design Rationale for Software Architecture Decisions", TOSEM 2025. The dataset is 100 architecture problems (50 Stack Overflow posts, 25 GitHub issues, 25 GitHub discussions), run on 5 LLMs with zero-shot, chain-of-thought and multi-agent prompting. Against expert rationale: **precision 0.267-0.278, recall 0.627-0.715, F1 0.351-0.389**. Of the LLM arguments that the humans had not mentioned, 64.45-69.42% were judged helpful, 4.12-4.87% of uncertain correctness and 1.59-3.24% potentially misleading. — [arXiv 2504.20781](https://arxiv.org/abs/2504.20781)
- **Architectural design decisions from commits.** Karan, Dhar, Soliman & Vaidhyanathan, "Can LLMs Extract Architectural Design Decisions from Source Code Commits?", IdeaArch workshop @ ECSA 2026. The study tested 30 developer-written ADDs on Gemini 3 Pro, DeepSeek R1, Kimi K2 and Qwen3. All models reached BERTScore-F1 above 0.81, and few-shot prompting raised Gemini from 0.828 to 0.847. Failure modes: output too long, focused on implementation detail rather than architecture, and frequently **missing the rationale**. No precision, recall or hallucination rates are reported. — [arXiv 2609.03721](https://arxiv.org/abs/2609.03721)
- A systematic review of 18 articles on LLMs in software architecture lists design-rationale extraction as one of the main task categories. — [arXiv 2505.16697](https://arxiv.org/abs/2505.16697)
- Design information mining from issue logs is a related line of work (I did not verify its numbers). — [arXiv 2405.19623](https://arxiv.org/abs/2405.19623)

### Inferences
- Untangle's "required supporting quote" matches how this literature evaluates extraction, at sentence level against labelled spans. The OOM-Killer labels (Decision / Rationale / Supporting Facts) map directly onto Untangle's Decision node plus a rationale field. Untangle could run its extractor on the Zenodo set and report sentence-level precision and recall.
- Because the measured LLMs are high-recall and low-precision (ARGUS 51% P / 93% R; Zhou et al. about 27% P / 63-72% R), the extractor should over-generate and then filter. Useful filters: exact-quote span matching, an NLI/entailment check that the quote supports the triple, and a second-pass judge.
- **Rationale gap should be scored per component.** A Decision whose sources supply a GOAL but no NEED or ALTERNATIVE is a partial rationale gap, so Untangle should search the linked issue or PR for those before flagging. Use the Al Safwan/Servant 15 components, or the 9-component subset used by ARGUS.
- Karan et al.'s failure modes (too implementation-focused, missing rationale) suggest giving the prompt explicit "decision vs. implementation detail" guidance, plus few-shot examples taken from real ADRs.
- Kantara-style conflict detection against past decisions corresponds to Untangle's contradiction risk, which can cite Dhaouadi et al. 2025 as prior art.

### Gaps
- Rastkar & Murphy (e.g., "Why did this code change?", ICSE 2013 NIER, which summarizes rationale from linked bug reports and commits) and mailing-list rationale mining did not come up in my searches, so I did not verify their details or URLs this session.
- I found no per-artifact percentages for ARGUS or exact extraction F1 for Dhaouadi et al. 2025 on the abstract pages. The full PDFs are needed.
- I found no study that measures LLM hallucination rates specifically for decision triples (subject/predicate/value) extracted from config or lockfile diffs. This appears to be an open evaluation gap that Untangle could fill.

## 2. Architectural decision records (ADRs), architecture knowledge management and erosion/drift detection

### Takeaway
ADR adoption in OSS is low, often abandoned after a few records, and the status field is unreliable (about 63% of ADRs are created already "accepted"). ADR status alone is therefore a weak signal, and Untangle should corroborate it with code and config evidence. Erosion detection research gives a ready-made symptom taxonomy and text classifiers for review comments.

### Cited Findings
- Buchgeher et al., "Using Architecture Decision Records in Open Source Projects - An MSR Study on GitHub", IEEE Access 11:63725-63740, 2023 (DOI 10.1109/ACCESS.2023.3287654). Adoption is low but growing yearly, and about half of repositories with ADRs hold only 1-5 records, which suggests a trial that was then abandoned. In systematic repositories, recording was a team activity by 2+ users over a long period. Most use Michael Nygard's template. — [DOAJ](https://doaj.org/article/f838f2a538ea48e7a3b15ce99befe612); [JKU](https://research.jku.at/en/publications/using-architecture-decision-records-in-open-source-projects-an-ms/)
- Garcia de Santana Junior et al., "Architecture Decision Records Adoption Impact and Developer Engagement in Open Source", ICSA 2026. The study covers 921 GitHub repositories from earlier ADR studies. Adoption remains inconsistent, and of 5,800 ADRs about **63% were opened directly with "accepted" status**, skipping the proposed/deliberation stage. — [ICSA 2026 listing](https://conf.researchr.org/details/icsa-2026/icsa-2026-papers/34/Architecture-Decision-Records-Adoption-Impact-and-Developer-Engagement-in-Open-Sou)
- A 2026 paper on LLM-generated ADRs ("Context Matters: Evaluating Context Strategies for Automated ADR Generation Using LLMs") describes the "adoption gap" and high post-pilot abandonment, and evaluates context strategies for generating ADRs. — [arXiv 2604.03826](https://arxiv.org/abs/2604.03826)
- **Erosion symptoms in code review.** Li, Soliman, Liang & Avgeriou, "Symptoms of Architecture Erosion in Code Reviews: A Study of Two OpenStack Projects" (2022). Of 21,274 review comments, 502 discuss erosion. The most frequent symptoms are architectural violation, duplicate functionality and cyclic dependency. — [arXiv 2201.01184](https://arxiv.org/abs/2201.01184)
- **Automated violation-symptom classifiers.** Li, Liang & Avgeriou, "Towards Automated Identification of Violation Symptoms of Architecture Erosion" (TOSEM 2024). They built 15 ML and 4 DL classifiers with 3 pre-trained word embeddings, trained on review comments from OpenStack Nova/Neutron and Qt Base/Qt Creator, and validated the results with 21 practitioners who took part in those discussions. — [arXiv 2306.08616](https://arxiv.org/abs/2306.08616) (I did not verify the classifier F1 values.)
- Dhaouadi et al. 2025 also detect potential design erosion by checking extracted rationale for conflicts with past decisions. — [arXiv 2506.11005](https://arxiv.org/abs/2506.11005)

### Inferences
- Untangle should treat ADR "accepted" status as a claim and not a fact. An ADR accepted at creation, with no later code or config evidence, deserves a lower confidence score. A related **drift** signal: an ADR says X, but the config or lockfile history later shows not-X without a superseding ADR.
- The "1-5 ADRs then abandonment" pattern is a staleness detector: if the last ADR is old while decision-bearing commits continue, the gap is undocumented decisions.
- Li et al.'s symptom taxonomy (violation, duplicate functionality, cyclic dependency) could become extra labels on review-comment evidence, and their dataset could bootstrap an "erosion mentioned in review" detector.

### Gaps
- I did not find a public, labelled dataset that links ADRs to the code or config changes implementing them. That would be the ideal ground truth for Untangle's SUPERSEDES chains.
- I did not retrieve classifier accuracy numbers for the erosion-symptom models.

## 3. Self-admitted technical debt (SATD), workarounds and links to upstream bugs

### Takeaway
SATD detection is mature: fine-tuned small LLMs beat CNN baselines by about 4-7 F1 points. The most useful sub-genre for Untangle is "on-hold" SATD, meaning comments waiting on an external event or issue, often an upstream fix. These become removable once the referenced issue closes, which gives a concrete, verifiable staleness signal. Build-system studies show dependency workarounds are the single most common rationale in build-file SATD.

### Cited Findings
- **LLM SATD detection.** Sheikhaei, Tian, Wang & Xu, "An Empirical Study on the Effectiveness of Large Language Models for SATD Identification and Classification" (arXiv May 2024, submitted to EMSE). Fine-tuned Flan-T5 variants beat the best non-LLM baseline (a CNN) by **4.4%-7.2% F1** on identification. Zero-shot Flan-T5-XXL is 6.4-9.2% worse than fine-tuned models but competitive with traditional methods. On classification, Flan-T5-XL is best, but the CNN beats 4 of the 6 LLMs. Few-shot in-context learning (with category descriptions) beats zero-shot and the smaller fine-tuned models, and adding surrounding code context helps the larger fine-tuned models. — [arXiv 2405.06806](https://arxiv.org/abs/2405.06806)
- SATD in test code (2025): keyword-based (MAT) prompting achieved the best F1 of 0.68. — [arXiv 2510.22409](https://arxiv.org/abs/2510.22409)
- A survey of ML for TD/SATD detection covers the classic baselines (e.g., da Silva Maldonado et al.'s max-entropy NLP classifier on 10 OSS projects). — [arXiv 2409.04662](https://arxiv.org/abs/2409.04662)
- **On-hold SATD.** Maipradit, Treude, Hata & Matsumoto, "Wait For It: Identifying 'On-Hold' Self-Admitted Technical Debt", EMSE 25(5):3770-3798, 2020. They define on-hold SATD as a developer "waiting for a certain event or an updated functionality having been implemented elsewhere". One Apache Camel example waits on an external bug being resolved. — [arXiv 1901.09511](https://arxiv.org/abs/1901.09511)
- Maipradit, Lin, Nagy, Bavota, Lanza, Hata & Matsumoto, "Automated Identification of On-hold Self-admitted Technical Debt", SCAM 2020. The paper focuses on on-hold comments that reference issue-tracker entries, and checks whether they are **superfluous**, i.e. the referenced issue is closed but the comment is still in the code. — [arXiv 2009.13113](https://arxiv.org/abs/2009.13113)
- **SATD in issue trackers.** Xavier et al., "Beyond the Code: Mining Self-Admitted Technical Debt in Issue Tracker Systems" (MSR 2020). Includes examples such as "HACK: This can be removed once this is fixed upstream". — [arXiv 2003.09418](https://arxiv.org/abs/2003.09418)
- **Build-system SATD.** Xiao et al., "Characterizing and Mitigating Self-Admitted Technical Debt in Build Systems", TSE 2022. Across 500 comments from 300 Maven projects, limitations in tools and libraries (49%) and dependency-management complexity (23%) are the top causes. **Workarounds are the most common rationale (22%)**, for example commenting out a dependency. — [TSE'22 PDF](https://rebels.cs.uwaterloo.ca/papers/tse2022_xiao.pdf)
- **API workarounds.** Lamothe & Shang, "When APIs are Intentionally Bypassed: An Exploratory Study of API Workarounds", ICSE 2020 (DOI 10.1145/3377811.3380433). From Stack Overflow they derive 8 reasons for workaround requests and 8 general solutions, validated in OSS projects. Workarounds "take the API developer out of the conversation", leaving API bugs unreported. — [ICSE'20 PDF](https://ece.uwaterloo.ca/~wshang/pubs/mlamothe_icse_2020.pdf). A later paper by Song, Zhong & Jia summarizes Lamothe & Shang as giving "four patterns" from 40 SO posts. That conflicts with the "8 reasons / 8 solutions" in the ICSE abstract, and I did not resolve which is right. — [Song et al. PDF](https://www.cs.sjtu.edu.cn/~zhonghao/paper/workaround.pdf)
- SATD in LLM-based software (2026) adds a "Model Dependency Debt" category: deferred updates that wait for upstream library evolution, with external-dependency debt treated as tracking upstream changes and compatibility layers. — [arXiv 2601.06266](https://arxiv.org/abs/2601.06266)

### Inferences
- **New Untangle feature: "upstream-blocked workaround" tracker.** Detect on-hold SATD comments and commit or PR text referencing an upstream issue or PR URL, a "until X is fixed upstream" pattern, or a pinned version with a comment. Link each to the upstream issue and raise a staleness risk when the upstream issue closes or a fixed release appears, using the SCAM 2020 "superfluous" definition. The finding is checkable, and the supporting quote is the comment itself.
- Xiao et al.'s finding that 22% of build-file SATD is workarounds and 23% is dependency complexity says Untangle's lockfile and config diff extraction should give special weight to comments in pom.xml, package.json, pyproject and similar files.
- For classification on a budget, few-shot prompting with category descriptions is reported to beat zero-shot. That fits a lower-cost model setup.

### Gaps
- I found no large study that specifically measures how often downstream workarounds cite upstream bug IDs across ecosystems ("cross-project correlated bugs" work, e.g., Ma et al. ICSE 2017 on the scientific Python ecosystem, did not come up in my searches and is unverified).
- I did not retrieve absolute F1 values or dataset names for the Sheikhaei et al. study.

## 4. Knowledge loss and ownership: truck/bus factor, degree of authorship, expertise recommenders, turnover

### Takeaway
The Avelino degree-of-authorship (DOA) truck-factor algorithm is the standard, open-source baseline and is reported as the most accurate or near-most-accurate in comparisons. For "who to ask", the strongest research designs (WhoDo, Sofia) combine expertise with workload and deliberately spread knowledge to reduce Files-at-Risk, not just to pick the top author.

### Cited Findings
- **Truck factor algorithm (AVL).** Avelino, Passos, Hora & Valente, "A Novel Approach for Estimating Truck Factors", ICPC 2016. It uses a degree-of-authorship (DOA) metric plus a greedy heuristic over key developers, and the implementation is public (aserg-ufmg/truck-factor). — [arXiv 1604.06766](https://arxiv.org/abs/1604.06766)
- Ferreira, Valente & Ferreira, "A Comparison of Three Algorithms for Computing Truck Factors", ICPC 2017. It evaluates 3 algorithms against an oracle on both the truck-factor value and identification of key developers. — [ICPC'17 PDF](https://homepages.dcc.ufmg.br/~mtov/pub/2017-icpc.pdf). The Software Quality Journal 2019 extension uses 133 popular GitHub systems. — [DOI 10.1007/s11219-019-09457-2](https://doi.org/10.1007/s11219-019-09457-2)
- Secondary comparisons report that the Avelino et al. and Cosentino et al. algorithms are the most accurate, with Avelino slightly better. Another cited comparison gives 0.84 accuracy for Avelino vs. 0.97 for csDetector, but on different datasets, so the two are not comparable. I saw these in search snippets and not in primary tables. — [Bus Factor in Practice, arXiv 2202.01523](https://arxiv.org/abs/2202.01523); [Bus-factor effort allocation, arXiv 2401.03303](https://arxiv.org/abs/2401.03303)
- **Degree-of-Knowledge.** Fritz, Murphy, Murphy-Hill, Ou & Hill, TOSEM 23(2), 2014. It computes a per-element (class, method) knowledge value that combines degree-of-authorship with degree-of-interest (interaction data). — [UBC tech report](https://www.cs.ubc.ca/sites/default/files/tr/2009/TR-2009-13_0.pdf)
- **WhoDo.** Asthana et al., "WhoDo: Automating Reviewer Suggestions at Scale", ESEC/FSE 2019 (Microsoft). Deployed on 5 Microsoft repositories, it weights expertise by current review workload so that experts are not overwhelmed. — [Microsoft Research](https://www.microsoft.com/en-us/research/?p=597184)
- **Turnover-aware recommendation.** Mirsaeedi & Rigby, "Mitigating Turnover with Code Review Recommendation: Balancing Expertise, Workload, and Knowledge Distribution", ICSE 2020, pp. 1183-1195. Ownership-based reviewer recommendation concentrates knowledge and **raises turnover knowledge-loss risk by up to 65%**. Their Sofia recommender picks experts when no files are hoarded, and spreads knowledge when files are at risk. Evaluated on expertise, core-team workload and **Files at Risk (FaR)**. — [researchr](https://researchr.org/publication/MirsaeediR20); [CORE](https://core.ac.uk/works/77729055)
- Hajari, Malmir, Mirsaeedi & Rigby, "Factoring Expertise, Workload, and Turnover into Code Review Recommendation" (arXiv Dec 2023). It reimplements WhoDo and reports +3% expertise in reviews, 12% less workload concentration and **28% fewer files at risk**. — [arXiv 2312.17236](https://arxiv.org/abs/2312.17236)

### Inferences
- Untangle's "ownership gap" risk can be formalized as DOA-based truck factor per feature or decision subject (feature-scoped TF rather than repository-wide). A file or decision is "at risk" when all of its DOA-authors are inactive, which matches Mirsaeedi & Rigby's FaR metric.
- For the person-to-ask suggestion, rank by expertise (DOA + review participation, as in Degree-of-Knowledge) discounted by recency and activity. Then optionally surface a second "learner" candidate to spread knowledge, as Sofia does. The ask can then double as knowledge transfer.
- Evaluation recipe: replay history, hide the actual reviewer or answerer, and measure top-k hit rate and FaR reduction, as in Mirsaeedi & Rigby and Hajari et al.

### Gaps
- I did not retrieve exact per-algorithm truck-factor accuracy tables from the 2017 and 2019 papers.
- I did not search Rigby et al. ICSE 2016 (Chrome/Avaya turnover knowledge loss) or other expertise-recommender benchmarks beyond those above.

## 5. Change impact analysis, co-change mining, SZZ and incident-to-change linking

### Takeaway
Co-change association rules (ROSE) remain a cheap, explainable baseline for "what else changes with this decision". SZZ variants plateau around 0.5 F1 on Linux ground truth; LLM4SZZ reaches 0.588 F1. Production incident-to-change ranking at Meta places the true root-cause diff in the top 5 in 42% of investigations. All of these support Untangle evidence edges, but they need confidence scores and not hard assertions.

### Cited Findings
- **ROSE.** Zimmermann, Weißgerber, Diehl & Zeller, "Mining Version Histories to Guide Software Changes", ICSE 2004. It mines association rules ("programmers who changed this also changed...") and can predict **26% of further files** to be changed and 15% of precise functions or variables after an initial change. The same evaluation reports that 30% of suggested files are correct, which is a precision-style figure; don't conflate it with the 26% recall-style figure. — [Project page](https://www.st.cs.uni-saarland.de/papers/icse2004/); [PDF](https://www.st.uni-trier.de/diehl/pubs/icse04.pdf)
- **Developer-informed SZZ oracle.** Rosa et al., "Evaluating SZZ Implementations Through a Developer-informed Oracle", ICSE 2021. The oracle is built from fix commits where developers name the bug-inducing commit, found with NLP and then manually filtered, and is used to benchmark existing SZZ variants. — [arXiv 2102.03300](https://arxiv.org/abs/2102.03300). A search snippet attributes to a journal extension a 2,304-instance dataset in which R-SZZ is best of 9 variants. I could not confirm which paper reports this (possibly the 2023 JSS extension). — [JSS PDF](https://susi.usi.ch/documents/329460/files/Lanza_2023_Elsevier_JSS.pdf)
- **Linux "Fixes:" tag ground truth.** A large-scale evaluation of SZZ on the Linux kernel uses developer "Fixes:" tags and finds all algorithms between 0.40 and 0.60 in precision and recall, with F1 around 0.50. — [arXiv 2308.05060](https://arxiv.org/abs/2308.05060)
- **LLM4SZZ** (arXiv April 2025): on Linux, **P 0.628, R 0.552, F1 0.588**, an F1 improvement of 6.9%-16.0% over baselines across 3 datasets. — [arXiv 2504.01404](https://arxiv.org/abs/2504.01404). AgentSZZ (2026) notes that this recall still misses about half of bug-inducing commits and proposes an agent-based approach. — [arXiv 2604.02665](https://arxiv.org/abs/2604.02665)
- **Incident-to-change (Meta, 2024).** The system narrows thousands of changes to a few hundred with heuristics, then a fine-tuned Llama 2 7B ranker picks 5. The true root-cause change is in the **top 5 for 42%** of web-monorepo investigations at creation time (backtest). — [Meta Engineering](https://engineering.fb.com/2024/06/24/data-infrastructure/leveraging-ai-for-efficient-incident-response/)
- **Microsoft cloud incidents.** Ahmed et al. (ICSE 2023) study about 40,000 incidents across 1,000+ services and find that fine-tuned LLMs substantially beat zero-shot for root-cause and mitigation text. This measures text quality, not change attribution. — [arXiv 2301.03797](https://arxiv.org/abs/2301.03797). The X-lifecycle follow-up adds service lifecycle and dependency context. — [arXiv 2404.03662](https://arxiv.org/abs/2404.03662)
- Meta also reports on using LLMs to score diff risk in release deployment. — [arXiv 2410.06351](https://arxiv.org/abs/2410.06351)

### Inferences
- **Co-change for impact of a decision change.** When a Decision (e.g., a config value) changes, Untangle could list files that historically co-change with that config key as ROSE-style "also-likely-affected" items, with support and confidence from the association rule as the explanation.
- **SZZ for "this decision caused bugs".** Linking a Decision's introducing commit to later fixes (via SZZ or Fixes:/revert trailers) yields a "decision later reverted or patched" signal, which is useful for contradiction and drift ranking. Prefer explicit developer links (Fixes:, revert, "regressed by") as high-confidence edges, and treat raw SZZ (about 0.5 F1) as low-confidence.
- The Meta two-stage pattern (cheap heuristic narrowing, then LLM ranking to top-k) fits Untangle's cost constraint for "which decision or change explains this incident" features.

### Gaps
- I did not search for public incident-to-commit linking datasets. None surfaced, and Meta's and Microsoft's datasets are internal.
- I did not retrieve ROSE's top-3 suggestion accuracy or the TSE 2005 extended numbers.

## 6. Temporal knowledge graphs, bi-temporal modelling and GraphRAG for code

### Takeaway
Zep/Graphiti is the most-cited open design for bi-temporal facts with validity intervals for LLM memory: valid time vs. ingestion/transaction time, with invalidation instead of deletion. It maps almost one-to-one to Untangle's valid_from/valid_to plus SUPERSEDES. Code-graph RAG (RepoGraph, CodexGraph) shows measurable gains on SWE-bench from structure-aware retrieval, but those graphs are static snapshots, not histories.

### Cited Findings
- **Zep / Graphiti.** Rasmussen et al., "Zep: A Temporal Knowledge Graph Architecture for Agent Memory" (arXiv Jan 2025). Graphiti is a temporally aware KG engine that keeps facts with validity periods while maintaining historical relationships. On Deep Memory Retrieval, Zep scores **94.8% vs. 93.4% for MemGPT**. On LongMemEval it reports accuracy improvements of **up to 18.5%** and **90% lower response latency** than baselines. It uses two timelines: one for event chronology and one for ingestion order. It is open source as `graphiti-core`. — [arXiv 2501.13956](https://arxiv.org/abs/2501.13956)
- A 2026 survey of graph-based agent memory describes the same split as valid time vs. transaction time. — [arXiv 2602.05665](https://arxiv.org/abs/2602.05665)
- **RepoGraph** (Ouyang et al., ICLR 2025): a line-level repository graph used as a plug-in. It boosted all four SWE-bench methods it was added to, a new open-source state of the art at the time, and was also tested on CrossCodeEval. — [arXiv 2410.14684](https://arxiv.org/abs/2410.14684); [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/4a4a3c197deac042461c677219efd36c-Abstract-Conference.html)
- **CodexGraph** (arXiv Aug 2024): LLM agents query a graph database built from static analysis with a task-agnostic node/edge schema. Evaluated on CrossCodeEval, SWE-bench and EvoCodeBench (venue not confirmed). — [arXiv 2408.03910](https://arxiv.org/abs/2408.03910)
- Kantara models rationale as a KG for conflict analysis. — [arXiv 2311.03358](https://arxiv.org/abs/2311.03358)

### Inferences
- Untangle's Decision model is already a valid-time model (valid_from/valid_to). Adding **transaction time** (when Untangle learned the fact: ingest run ID, extractor version) would let it answer "what did we believe on date D" and audit extractor regressions. It would also let it invalidate, not delete, facts when a newer extraction contradicts an older one, as Graphiti does.
- Contradiction detection can follow Graphiti's pattern. When a new fact on the same (subject, predicate) overlaps in valid time with a different value and has no SUPERSEDES edge, flag a contradiction; if a later commit or ADR explains it, add SUPERSEDES and close the interval.
- RepoGraph and CodexGraph suggest pairing temporal decision edges with a static code graph (functions/files to config keys) so that Ask can do multi-hop "which code reads this setting, and who decided its value" queries.

### Gaps
- I found no peer-reviewed benchmark that evaluates **temporal** (as-of-date) question answering over software history specifically. Zep's benchmarks are conversational memory, not code.
- I did not check Graphiti's exact edge fields (e.g., t_valid / t_invalid / expired_at) against the full paper.

## 7. Evaluation: benchmarks and datasets for code QA over history, and measuring citation faithfulness

### Takeaway
Repository-QA benchmarks (SWE-QA, CoReQA, CodeRepoQA, Long Code Arena) cover code understanding and issue conversations but **not "why/when did this decision change" questions over commit history**, so Untangle would need its own gold set. Small, purpose-built labelled datasets do exist for components: OOM-Killer rationale, ARGUS's 63 commits, the SZZ oracles and BUMP. On citations, "correct" (the source supports the claim) is not the same as "faithful" (the model actually relied on it): up to 57% of correct citations were unfaithful in controlled tests.

### Cited Findings
- **SWE-QA** (Sept 2025): v1 has 576 QA pairs over 12 Python repositories; v2 expands to 720 pairs over 15 repositories. Categories include cross-file and multi-hop reasoning, and it ships with SWE-QA-Agent (ReAct) plus RAG and agent baselines. — [arXiv 2509.14635](https://arxiv.org/abs/2509.14635). SWE-QA-Pro (Mar 2026) targets long-tail repositories with executable environments. — [arXiv 2603.16124](https://arxiv.org/abs/2603.16124)
- **CodeRepoQA** (Dec 2024): 585,687 multi-turn entries (average 6.62 turns) derived from GitHub issue conversations. — [arXiv 2412.14764](https://arxiv.org/abs/2412.14764)
- **CoReQA** (Jan 2025): built from GitHub issues and comments in 176 repositories across 4 languages, judged by an LLM. — [arXiv 2501.03447](https://arxiv.org/abs/2501.03447)
- **Long Code Arena** (JetBrains, June 2024): 6 tasks, namely library-based code generation, CI build repair, project-level completion, **commit message generation** (a curated subset of CommitChronicle), **bug localization** and module summarization. — [arXiv 2406.11612](https://arxiv.org/abs/2406.11612); [JetBrains blog](https://blog.jetbrains.com/ai/2024/08/long-code-arena-how-well-can-ai-models-understand-your-entire-project/)
- Component-level gold sets usable by Untangle: OOM-Killer rationale labels ([Zenodo](https://zenodo.org/records/10063089)); the ARGUS 63-commit cross-artifact rationale set ([arXiv 2604.10345](https://arxiv.org/abs/2604.10345)); 100 architecture problems with expert rationale ([arXiv 2504.20781](https://arxiv.org/abs/2504.20781)); 30 developer-written ADDs ([arXiv 2609.03721](https://arxiv.org/abs/2609.03721)); SZZ developer-informed oracle ([arXiv 2102.03300](https://arxiv.org/abs/2102.03300)); BUMP breaking updates ([arXiv 2401.09906](https://arxiv.org/abs/2401.09906)).
- **Citation faithfulness.** Wallat, Heuss, de Rijke & Anand, "Correctness is not Faithfulness in RAG Attributions", ICTIR 2025. It separates citation correctness (the document supports the statement) from faithfulness (the model actually relied on it rather than post-rationalizing), and finds **up to 57% of citations unfaithful even when correct**. Test principle: adding irrelevant documents should not change attributions when the answer is unchanged. — [arXiv 2412.18004](https://arxiv.org/abs/2412.18004)
- A 2026 reproduction reports about 1 in 7 citations unfaithful on Wikipedia QA and finds RL from verifiable rewards does not fix it (a single preprint, not independently verified). — [arXiv 2609.23053](https://arxiv.org/abs/2609.23053). Another 2026 audit questions whether attribution metrics transfer across datasets. — [arXiv 2606.23915](https://arxiv.org/abs/2606.23915)

### Inferences
- **Proposed Untangle eval suite:**
  - (a) Decision extraction: span-level P/R against OOM-Killer and ARGUS labels.
  - (b) Rationale completeness: per-component coverage (GOAL/NEED/ALTERNATIVE).
  - (c) Temporal QA: an in-house gold set of "what was X on date D / why did X change / who decided" questions, built from repositories with ADRs and Fixes:/revert trailers.
  - (d) Citation **correctness**: an entailment check that the quoted span supports the answer sentence.
  - (e) Citation **faithfulness**: a Wallat-style perturbation test that injects irrelevant or contradicting evidence and checks whether citations change appropriately.
  - (f) Ask-the-person: top-k hit rate replayed on history.
- Because the required supporting quote is verbatim, Untangle can measure correctness deterministically (quote exists in source at the cited commit) plus semantically (NLI). Faithfulness still needs perturbation tests.

### Gaps
- CodeQueries and RepoQA (both named in the brief) did not come up in my searches; I did not verify their details.
- I found no benchmark whose questions are explicitly about **commit-history rationale or decision evolution**. This appears to be an open gap and a publishable contribution.

## 8. Upstream dependency research: pinning, technical lag, breaking changes, vulnerable-dependency reachability

### Takeaway
Technical lag has standard, simple time and version formulas and is driven mostly by version constraints and minor/patch releases. Pinning only direct dependencies is futile, even counterproductive, compared with whole-graph lockfiles. BUMP gives reproducible breaking updates for evaluation. Reachability (Eclipse Steady) is the main academic method for whether a vulnerable dependency matters, built from fix-commit method signatures plus static and dynamic call graphs.

### Cited Findings
- **Technical lag.** Decan, Mens & Constantinou, "On the Evolution of Technical Lag in the npm Package Dependency Network", ICSME 2018. The data covers 1.4M+ releases of 120K packages and 8M dependencies. Technical lag increases over most packages' lifespans, mainly from **minor and patch** releases of dependencies. Time lag = date(latest) - date(used), and version lag counts the major/minor/patch gap. — [arXiv 1806.01545](https://arxiv.org/abs/1806.01545)
- Zerouali et al. introduced technical lag for npm dependencies (ICSR 2018) and later extended it to package, time, version, **vulnerability** and **bug** lag, applied to Docker images. Version constraints are a major cause, reflecting reluctance to update for fear of breaking changes. These details come from slide decks, not the papers. — [ICSR 2018 slides](https://de.slideshare.net/neglectos/icsr2018); [PhD defense slides](https://www.slideshare.net/neglectos/phd-public-defense-a-measurement-framework-for-analyzing-technical-lag-in-opensource-software-ecosystems)
- **Pinning.** He, Vasilescu & Kästner, "Pinning Is Futile: You Need More Than Local Dependency Versioning to Defend against Supply Chain Attacks", FSE 2025. Simulating resolution over historical npm snapshots, they find that pinning direct dependencies is futile and **can be counterproductive** when floating is mainstream, and is counterproductive in large graphs (≥498 nodes in their model). They recommend freezing the whole graph with a shared lockfile and ecosystem-level changes such as transitive pinning. — [arXiv 2502.06662](https://arxiv.org/abs/2502.06662)
- "The Design Space of Lockfiles Across Package Managers" (2025) compares lockfile semantics. — [arXiv 2505.04834](https://arxiv.org/abs/2505.04834)
- **Breaking updates.** Reyes et al., "BUMP: A Benchmark of Reproducible Breaking Dependency Updates", SANER 2024. It contains **571 breaking updates from 153 Java/Maven projects**, each a one-line pom change where the pre-update build passes and the post-update build fails, stored in Docker images. Released under MIT on Zenodo. — [arXiv 2401.09906](https://arxiv.org/abs/2401.09906); [GitHub](https://github.com/chains-project/bump); [Zenodo](https://zenodo.org/records/10041883). Byam uses LLMs to repair BUMP cases. — [arXiv 2505.07522](https://arxiv.org/abs/2505.07522)
- **Reachability.** Ponta, Plate & Sabetta, "Detection, assessment and mitigation of vulnerabilities in open source dependencies", EMSE 2020 (Eclipse Steady). It takes vulnerable method signatures from fix commits, then runs static call-graph reachability (WALA/Soot) plus dynamic traces from JUnit and integration tests. The study scanned 300 enterprise applications with 78,165 dependencies and compared against OWASP Dependency-Check. — [EMSE 2020](https://link.springer.com/article/10.1007/s10664-020-09830-x); [Steady analysis docs](https://eclipse-steady.github.io/steady/user/manuals/analysis). Steady's reachability does not support Java 9+, due to its analysis frameworks. — [Steady docs](https://eclipse-steady.github.io/steady/user/manuals/analysis)
- VAScanner (2024) compares vulnerable-API detection against Steady on 1,045 Maven projects. — [arXiv 2409.02753](https://arxiv.org/abs/2409.02753)

### Inferences
- Untangle's lockfile-diff Decisions can carry computed **time lag and version lag** at each valid_from, which gives a quantitative staleness risk. Vulnerability lag (time from fix-release to adoption) could be added when advisories are joined.
- Untangle could detect "pin with a reason" decisions (pinned version plus a comment, PR text or issue link). It could flag "direct-only pin" patterns as weak protection, citing He et al., but that is advisory content and should be worded carefully.
- BUMP could serve as a test set for a "this upgrade broke the build, was reverted, and became a pin decision" chain extractor (revert → SUPERSEDES).
- Reachability is a heavy feature. A lightweight version is to link a vulnerable package to the files that import it and to the Decisions that pinned it, without claiming call-graph reachability.

### Gaps
- I found no peer-reviewed precision/recall numbers for Eclipse Steady or for commercial reachability (Endor Labs, Semgrep) in these searches. Vendor claims were not researched.
- I did not verify the exact headline numbers of Zerouali et al.'s papers or of Ochoa et al. / Raemaekers on semantic-versioning breaking changes in Maven Central.
