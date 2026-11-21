# Web search APIs and deep-research agent techniques for a cited "Investigate" mode in Untangle (as of 21 November 2026)

Scope note: Untangle's configured Anthropic default model is `claude-haiku-5-5` (source: `src/untangle/llm.py`, line 23, `DEFAULT_MODELS = {"anthropic": "claude-haiku-5-5", ...}`). Prices and capabilities below are checked against that model first. All vendor prices are list prices read on 21 Nov 2026 unless marked otherwise.

## 1. Claude API server tools (web search, web fetch), Citations and search_result blocks

### Takeaway
Claude's web search tool costs $10 per 1,000 searches plus tokens. Web fetch has no per-call fee. Both tools support Claude Haiku 5.5, including dynamic filtering, which Haiku 4.5 does not get. Web search citations always point at Anthropic-encrypted results with at most 150 characters of `cited_text`, so Untangle cannot check them in full. The best fit for Untangle's rule that answers cite only evidence the service retrieved has two parts: web fetch with citations on, which returns plain text and `char_location` offsets, and passing self-retrieved web content as `search_result` blocks with citations on. In the second case the API guarantees each citation points at content Untangle supplied.

### Cited Findings

**Web search tool: versions, models, pricing**
- Three versions exist: `web_search_20250305` (basic), `web_search_20260209` (adds dynamic filtering) and `web_search_20260318` (adds `response_inclusion` control). The feature status is "stable", and the docs examples send `anthropic-version: 2026-10-21`. — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- The supported-models list includes `claude-haiku-5-5` and `claude-haiku-4-5-20251001`, plus Sonnet, Opus, Fable and Mythos models. — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- Price: "$10 USD per 1,000 searches, plus standard token costs for search-generated content. Search results count as input tokens, both while Claude keeps searching within a turn and in later conversation turns." Each search counts as one use however many results it returns. Failed searches are not billed. — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool); [Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- Batch API: web search costs the same as in regular requests. The Batches API throttles web search per organization, so large batches can take longer. — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- An admin can disable web search or restrict its domains in the Console. If it is disabled, the request fails with a 400 `invalid_request_error`. — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)

**max_uses and turn accounting**
- `max_uses` caps the searches in a single turn. "Single-fact queries typically use 1–3 searches; comparative or multientity research can use 10 or more." Failed searches count against the limit. Exceeding it returns a `max_uses_exceeded` error block, still inside an HTTP 200. Searches from earlier requests in the same turn (after a `pause_turn` resume) count too, unless they ran from code execution through dynamic filtering. — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- Error codes: `too_many_requests`, `invalid_tool_input`, `max_uses_exceeded`, `query_too_long`, `request_too_large` (often a long domain list) and `unavailable`. A search with no hits returns an empty list, not an error. — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)

**Domain allow and block lists (both tools)**
- Use `allowed_domains` or `blocked_domains`, not both; sending both returns a 400. Subdomains are included automatically: `example.com` covers `docs.example.com`. Naming a specific subdomain restricts results to that subdomain. Web search accepts paths (`example.com/blog`), but web fetch "matches on the domain only: an entry that includes a path never matches a web fetch URL." Wildcards are allowed only in the path (`example.com/*`), never in the domain (`*.example.com` is invalid). — [Server tools docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)
- A request-level `allowed_domains` list must be a subset of the organization-level list. The docs warn that Unicode homograph domains can bypass filters and recommend ASCII-only lists. — [Server tools docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)
- `user_location` (`type: approximate`, plus city, region, ISO country and IANA timezone) localizes search results. — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)

**Web search citation format**
- "Citations are always enabled for web search." Each `web_search_result_location` carries `url`, `title`, `encrypted_index` and `cited_text` ("Up to 150 characters of the cited content"). The `cited_text`, `title` and `url` fields "do not count toward input or output token usage." — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- A search result carries `url`, `title`, `page_age` and `encrypted_content`. The encrypted content must be sent back unchanged in multi-turn conversations; if it is missing or modified, the request fails with a 400. — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- Display requirement: "When displaying API outputs directly to end users, citations must be included to the original source." — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)

**Dynamic filtering**
- With `_20260209` and later, Claude writes and runs code that filters results before they enter the context window. The API provisions code execution automatically, and `allowed_callers` defaults to `["code_execution_20260120"]`. "There are no additional charges for code execution calls made this way beyond the standard token costs." — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool); [Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- Dynamic filtering needs programmatic tool calling. That feature's supported-models list includes `claude-haiku-5-5` but not Haiku 4.5: "Claude Haiku 4.5 accepts the `code_execution_20260120` and later tool versions but doesn't support programmatic tool calling." Models without it must set `allowed_callers: ["direct"]`, or the API returns a 400. — [Programmatic tool calling docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling); [Server tools docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)
- Measured effect, from an Anthropic blog post of 17 Feb 2026, tested on Sonnet 4.6 and Opus 4.6 only:
  - BrowseComp accuracy: Sonnet 4.6 went from 33.3% to 46.6%, Opus 4.6 from 45.3% to 61.6%.
  - DeepSearchQA F1: Sonnet 4.6 went from 52.6% to 59.4%, Opus 4.6 from 69.8% to 77.3%.
  - Averages: 11% higher accuracy and 24% fewer input tokens.
  - Cost: price-weighted tokens fell for Sonnet 4.6 but rose for Opus 4.6, so the post advises testing on representative queries.
  — [Claude blog: Improved web search with dynamic filtering](https://claude.com/blog/improved-web-search-with-dynamic-filtering)
- `response_inclusion: "excluded"` (version `_20260318` and later) drops nested raw search or fetch blocks that a completed code-execution call consumed, which shrinks the response. Token usage does not change. — [Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- Data handling: the basic tools (`web_search_20250305`, `web_fetch_20250910`) are ZDR-eligible. Dynamic filtering is "not eligible for ZDR or HIPAA". To use a `_20260209`+ tool under ZDR, set `allowed_callers: ["direct"]`. — [Server tools docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)

**Web fetch tool**
- Versions:
  - `web_fetch_20250910`: basic fetch.
  - `web_fetch_20260209`: dynamic filtering.
  - `web_fetch_20260309`: dynamic filtering plus `use_cache` for cache bypass.
  - `web_fetch_20260318`: adds `response_inclusion`.
  The feature status is stable, and the supported models include `claude-haiku-5-5`. — [Web fetch tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- Price: "no additional charges beyond standard token costs." The docs give typical sizes: an average 10 kB webpage is about 2,500 tokens, a 100 kB docs page about 25,000 tokens, and a 500 kB PDF about 125,000 tokens. `max_content_tokens` truncates text content but does not apply to PDFs. `max_uses` has no default limit. — [Web fetch tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- Citations are optional for web fetch and off by default (`"citations": {"enabled": true}`). With citations on, results use `char_location` citations with `document_index`, `start_char_index`, `end_char_index` and `cited_text`. The fetch result contains the full plain text (`source.type: text`) and a `retrieved_at` timestamp. — [Web fetch tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- Limits:
  - No JavaScript-rendered pages.
  - Only text, HTML and PDF (otherwise `unsupported_content_type`).
  - URLs of at most 250 characters (`url_too_long`).
  - Results are cached and may be stale. `use_cache: false` bypasses the cache at the cost of added latency.
  — [Web fetch tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- URL validation: Claude can fetch only URLs that appeared in user messages, client tool results or earlier search and fetch results. URLs that appear only in Claude's own output or only in the system prompt are refused (`url_not_in_prior_context`). The `url_sources` setting can narrow this further, for example excluding client tool results. URLs that seem to contain a credential are refused. — [Web fetch tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- ZDR: eligible, except dynamic filtering. HIPAA: not eligible. "Website publishers might retain request data (such as fetched URLs and request metadata)." — [Web fetch tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)

**Server-side loop mechanics**
- Long server-tool turns can stop with `stop_reason: "pause_turn"`. To continue, send the paused assistant content back unchanged with the same `tools` (and container ID, if one was returned). Continuations can pause again, so cap them like any retry loop. — [Server tools docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)
- If Claude calls a server tool and a client tool in the same parallel group, the API returns `stop_reason: "tool_use"` without running the server tool. The follow-up user message must contain only `tool_result` blocks, or the request fails with a 400. — [Server tools docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)
- Streaming: search and fetch events arrive in the SSE stream. The stream pauses while the tool runs, and each result arrives as one complete `content_block_start` event. — [Server tools docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)

**Prompt caching interaction**
- "Toggling web search or citations" invalidates the system and messages caches. Modifying tool definitions invalidates the whole cache. — [Tool use with prompt caching](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-use-with-prompt-caching)
- "Server tool results are cached automatically": when a request already has at least one `cache_control` marker, the API places a 5-minute cache breakpoint on each server tool result before the next loop iteration. Without prompt caching, there is no automatic breakpoint. — [Tool use with prompt caching](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-use-with-prompt-caching)
- Citation blocks themselves cannot be cached, but the source documents they reference can be (`cache_control` on the document block). — [Citations docs](https://platform.claude.com/docs/en/build-with-claude/citations)

**Citations feature (documents) and search_result blocks**
- All active models support Citations. Plain text and PDFs are chunked into sentences. "Custom content" documents use the caller's own blocks as citable chunks with no further chunking, and their citations point to block indices. — [Citations docs](https://platform.claude.com/docs/en/build-with-claude/citations)
- The docs list three advantages over prompt-based citing:
  - Citations "are guaranteed to contain valid pointers to the provided documents".
  - `cited_text` does not count toward output tokens, nor toward input tokens when sent back.
  - "In Anthropic's evaluations, the citations feature is significantly more likely to cite the most relevant quotes from documents than purely prompt-based approaches."
  — [Citations docs](https://platform.claude.com/docs/en/build-with-claude/citations)
- "Citations and structured outputs are incompatible": enabling citations together with `output_config.format` returns a 400. — [Citations docs](https://platform.claude.com/docs/en/build-with-claude/citations)
- `search_result` blocks (fields: `type`, `source`, `title`, `content` (text blocks), `citations`, `cache_control`) can be returned from custom tools or placed directly in user messages. They yield `search_result_location` citations with `source`, `title`, `cited_text`, `search_result_index` and start/end block indices. Citations are off by default, and every search result in a request must use the same setting. If any block in a `tool_result` is a `search_result`, all of its blocks must be. — [Search results docs](https://platform.claude.com/docs/en/build-with-claude/search-results)

**Model prices relevant to cost (Claude API, per million tokens)**
- Claude Haiku 5.5:
  - Prompts up to 100,000 tokens: $0.10 input, $0.125 for 5-minute cache writes, $0.01 for cache hits, $0.50 output.
  - Prompts over 100,000 tokens: $0.50 input, $0.05 for cache hits, $2.50 output.
  - "a request over the threshold pays the higher prices even when part of its prompt is a cache hit".
  — [Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- Other models: Haiku 4.5 is $1 input / $5 output; Sonnet 5.5 is $2 / $10; Opus 5.5 is $4 / $20. The Batch API takes 50% off; Haiku 5.5 batch is $0.05 / $0.25 at 100k tokens or less. — [Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- Claude 4.7 and later models use a newer tokenizer that "produces approximately 30% more tokens for the same text." — [Pricing](https://platform.claude.com/docs/en/about-claude/pricing)

### Inferences
- With Haiku 5.5, search fees outweigh token costs. One search costs $0.01. A 2,500-token page at Haiku 5.5's sub-100k rate costs about $0.00025. A 5-search, 10-fetch investigation therefore costs about $0.05 in search fees and well under one cent in tokens. That holds only while each request stays under 100k prompt tokens (calculation from the pricing pages above).
- The 100k-token price step is the main cost risk. The server-side loop adds every search result to the prompt for later iterations, so one long agentic turn can cross 100k and pay five times the rate on that request. To stay under it, combine a small `max_uses` (for example 3–5), dynamic filtering (which Haiku 5.5 supports), `max_content_tokens` on fetch, and a client-side loop that compresses findings between requests.
- Web search citations are hard to validate in full. Untangle sees only the URL, the title and up to 150 characters of cited text; the page body is encrypted. A validator could fetch the URL itself and confirm that `cited_text` appears in it, but it cannot inspect the snippet the model actually read.
- Web fetch with citations, or self-retrieved pages passed as `search_result` blocks, gives Untangle the exact text and the offsets or block indices. That keeps the current invariant (cite only retrieved evidence) checkable by machine and lets repo evidence and web evidence share one citation mechanism. For example, both can be `search_result` blocks, with `source` set to an internal evidence URI or a web URL.
- Because citations and structured outputs are incompatible, the answer step cannot use a JSON schema with citations on. Untangle would need to parse citation blocks from text output, or run a separate structured step without citations.

### Gaps
- I found no documented per-search token count for web search results (that is, how many input tokens one search adds), so the token cost per search must be measured.
- I did not confirm whether Haiku 5.5 uses the newer tokenizer (+~30%). The docs say "Claude 4.7 and later", which presumably includes Haiku 5.5, but no page states it explicitly.
- No page documents a search-result recency filter (date range) for Claude's web search; only `page_age` is returned.

## 2. Third-party search, fetch and extraction APIs

### Takeaway
Raw search costs about $1–$15 per 1,000 queries. The cheapest list prices are Parallel Search (from $1), Perplexity Fast Search ($1), Exa Lite ($4) and Brave, Perplexity standard and You.com (all $5). Tavily costs $5–$8 per 1,000 basic searches depending on plan, and SerpApi about $9–$15. Bing's API is retired (11 Aug 2025), and Google's Custom Search JSON API is closed to new customers and ends on 1 Jan 2027. Terms on storing results are mostly unpublished; Brave says storage rights need a custom plan.

### Cited Findings

**Retired or closing services**
- Microsoft retired the Bing Search APIs (all tiers, including Bing Custom Search) on 11 August 2025 and pointed developers to "Grounding with Bing Search" in Azure AI Agents. Developers raised concerns that the replacement does not expose raw content. — [Microsoft lifecycle notice](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement); [The Register](https://www.theregister.com/2025/05/15/bing_search_apis_retired/); [Microsoft Q&A thread](https://learn.microsoft.com/en-us/answers/questions/2284828/grounding-with-bing-in-azure-ai-agents-has-constan)
- Google's Custom Search JSON API "is not available for new customers". Existing customers keep access until "the service discontinuation on January 1, 2027". New projects get 403 PERMISSION_DENIED. — [Google Custom Search JSON API overview](https://developers.google.com/custom-search/v1/overview?hl=en); [Brave summary](https://brave.com/learn/google-api-shutdown/) (a vendor with a commercial interest)

**Exa**
- Free tier: $10 in credits that resets monthly, "up to 2,500 Lite searches".
- Search, per 1,000 requests with up to 10 results: `lite` and `instant` $4, `auto` and `fast` $7. Each result above 10 costs $1 per 1,000.
- Deep search: `deep-lite` $12 (about 4 s), `deep` $12 (4–15 s), `deep-reasoning` $15 (12–40 s).
- Contents: $1 per 1,000 pages for each content type (text, highlights, summary). Answer: $5 per 1,000.
- Agent: $0.012–$1.00 per request by effort level.
- Zero Data Retention and 25 QPS come with the Enterprise plan ($12,000 per year).
- The pricing page does not mention date filters.
— [Exa pricing](https://exa.ai/pricing)

**Tavily**
- Plans: 1,000 free credits per month. Pay-as-you-go is $0.008 per credit. Monthly plans run from Project ($30 for 4,000 credits) to Growth ($500 for 100,000 credits, $0.005 per credit).
- Credit costs:
  - Basic search: 1 credit. Advanced search: 2 credits.
  - Extract: 1 credit per 5 URLs (basic) or 2 credits (advanced). Failed extractions are free.
  - Research endpoint: 4–110 credits (mini) or 15–250 credits (pro).
  — [Tavily credits](https://docs.tavily.com/documentation/api-credits)
- Recency and content controls:
  - `topic`: `general`, `news` or `finance`.
  - `time_range`: day, week, month or year. `start_date` and `end_date` take YYYY-MM-DD.
  - `max_age_hours` (1–720) sets the maximum age of Tavily's cached copy.
  - `include_published_date` and `filter_by_published_date` control publish dates.
  - `include_raw_content` returns markdown or text. `chunks_per_source` is 1–3 and `max_results` is 0–20.
  - `include_domains` takes up to 300 domains and `exclude_domains` up to 150.
  — [Tavily search API reference](https://docs.tavily.com/documentation/api-reference/endpoint/search)

**Brave Search API**
- Search: $5 per 1,000 requests, $5 in free credits each month, 50 QPS. Answers: $4 per 1,000 plus $5 per million tokens, 2 QPS.
- The page header says "Up to $20 in free calls every month", which conflicts with the $5 shown on the plan cards.
- Storing results or using them for training is possible only "with a custom plan".
- The LLM Context endpoint returns ranked page content within a token budget of about 1k–33k tokens and can filter to the last 24 hours.
— [Brave Search API](https://brave.com/search/api/)

**Serper and SerpApi (Google SERP resellers)**
- Serper.dev: "Get 2,500 free queries", no card required. I could not retrieve its paid tiers. — [Serper.dev](https://serper.dev/)
- SerpApi plans:
  - Free: 250 searches per month.
  - Developer: $75 for 5,000 (about $15 per 1,000).
  - Production: $150 for 15,000 ($10 per 1,000).
  - Big Data: $275 for 30,000 (about $9.17 per 1,000).
  - "Only successful searches are counted."
  - Production and above include a "U.S. Legal Shield" with "up to $2 million in coverage".
  — [SerpApi pricing](https://serpapi.com/pricing)

**Perplexity**
- Search API: $5.00 per 1,000 requests, or $1.00 per 1,000 with Fast Search (`search_type: "fast"`). A request can hold up to five queries and is billed as one unit, with no token charges.
- Agent API tools: `web_search` costs $0.0025 per call (Fast $0.001) and `fetch_url` $0.0005 per call.
— [Perplexity pricing docs](https://docs.perplexity.ai/docs/getting-started/pricing)
- Sonar Pro: $3 input / $15 output per million tokens plus request fees of $6, $10 or $14 per 1,000 for low, medium or high search context. These figures come from third parties; I could not see the official table. One source says Sonar Chat Completions is deprecated and supported until 27 Sep 2026. — [Puter pricing breakdown](https://developer.puter.com/tutorials/perplexity-api-pricing/); [Amnic](https://amnic.com/blogs/perplexity-api-pricing)

**Kagi**
- $12 per 1,000 search requests, read from a regional mirror of Kagi's pricing page. Third-party aggregators give conflicting figures ($2.50–$25 per 1,000) and report no free plan. — [Kagi API pricing (mirror)](https://asia-east.kagi.com/api/pricing); [CostBench](https://www.costbench.com/software/ai-search-apis/kagi-search-api/)

**You.com**
- Web Search API: $5.00 per 1,000 calls, up to 100 results per call, news included. Contents API: $1 per 1,000 pages. New accounts get $100 in credits.
- A possible free tier of 100 calls per day from late July 2026 is reported by third parties only.
- The Research API is priced by effort tier (lite $12, standard $50, deep $100, exhaustive $450). The unit, which is presumably per 1,000 calls, was not confirmed.
— [You.com billing docs](https://docs.you.com/administration/billing); [UsagePricing](https://www.usagepricing.com/blueprint/activity/you-com-2026-07-29-web-search-free-tier)

**Jina Reader and Search**
- Billing is by tokens: each new key gets 10M free tokens. Reader bills output tokens. Search bills a fixed amount per request, "starting from 10,000 tokens". Failed requests are free.
- Rate limits: Reader is 20 RPM without a key and 500 RPM with one. Search needs a key (100 RPM; premium 1,000 RPM).
- Reader renders JavaScript in a headless browser by default, reads PDFs and outputs Markdown.
- ReaderLM-v2 is CC-BY-NC.
- The page carries Elastic branding ("Elastic © 2026") and says commercial ReaderLM licenses are sold by Elastic from 10 Aug 2026. The nature of the ownership change is not stated.
— [Jina Reader](https://jina.ai/reader/)

**Firecrawl**
- Plans: Free (1,000 credits), Hobby ($19 for 5,000), Standard ($99 for 100,000), Growth ($399 for 500,000).
- Credit costs: scrape and crawl 1 credit per page (JSON format adds 4). Search costs 2 credits per 10 results.
- Concurrent browsers: 2 on Free, 25 on Standard.
— [Firecrawl pricing](https://firecrawl.dev/pricing)

**Parallel.ai**
- Search API: "From $1 per 1k requests" with 10 results included. Extract: $1 per 1,000 URLs (the FAQ calls the unit "results", so it is unclear). Task API: "From $5 per 1k successful runs".
- Search and Extract rate limit: 600 per minute on Build.
- The pricing page has no benchmark figures.
— [Parallel pricing](https://parallel.ai/pricing)

### Inferences
- For a client-side pipeline (search API, then self-fetch, then `search_result` blocks), Parallel at $1, Perplexity Fast at $1, Exa Lite at $4 and Brave at $5 per 1,000 are 2–10 times cheaper than Claude's $10 per 1,000 server search. Untangle would then pay for its own fetching (Exa or You.com contents at $1 per 1,000, or Jina tokens), and those calls are harder to fit inside one Vercel invocation.
- Tavily is the only provider whose docs I confirmed have explicit published-date filters. That matters for freshness weighting, for example preferring upstream issues from around a commit date.
- Storage terms matter for an evidence graph. Persisting web snippets as Neo4j evidence nodes for later citation checks may need explicit storage rights. Brave says this needs a custom plan; the other vendors' terms were not checked.

### Gaps
- I did not obtain Serper's paid per-query tiers, or Exa's date-filter parameters (not on the pricing page).
- I did not review most vendors' terms of service on storing or caching results (Exa, Tavily, Parallel, Perplexity, You.com, Serper).
- Kagi's price is unverified against the main kagi.com page. Official Sonar request-fee tables were not visible.
- I found no independent, current, like-for-like quality benchmark of these search APIs; vendor-published comparisons are biased.

## 3. Deep-research agent architectures (2025–2026)

### Takeaway
The proven pattern is plan, search in parallel, read, reflect and compress, then synthesize, then run a separate citation pass, with explicit effort budgets matched to query complexity. Anthropic's orchestrator-worker system beat a single agent by 90.2%, but used about 15 times the tokens of chat. A cost-sensitive product should run a single agent for most questions and fan out only for complex ones.

### Cited Findings

**Anthropic's multi-agent research system**
- Structure: a lead agent (Claude Opus 4) plans, spawns parallel subagents (Claude Sonnet 4) and synthesizes their findings. A separate CitationAgent attributes claims to sources after research ends. The lead saves its plan to memory because context beyond 200k tokens is truncated. — [Anthropic engineering: How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Results and costs:
  - The multi-agent system "outperformed single-agent Claude Opus 4 by 90.2%" on an internal research eval.
  - On BrowseComp, "token usage by itself explains 80% of the variance".
  - Agents use about 4 times the tokens of chat; multi-agent systems use about 15 times.
  — [Anthropic engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- Effort-scaling rules:
  - Simple fact-finding: 1 agent with 3–10 tool calls.
  - Comparisons: 2–4 subagents with 10–15 calls each.
  - Complex research: more than 10 subagents.
  - Early versions spawned 50 subagents for simple queries, which is why the rules were added.
  — [Anthropic engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- Other techniques:
  - Start with short, broad queries, then narrow.
  - Use extended thinking for planning and interleaved thinking after tool results.
  - Run 3–5 subagents in parallel, each making 3+ parallel tool calls; this cut research time by up to 90%.
  - A tool-testing agent that rewrote tool descriptions cut task time by 40%.
  — [Anthropic engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- Weaknesses noted:
  - Agents favored SEO content farms over authoritative sources until source-quality heuristics were added.
  - Synchronous subagents are a bottleneck.
  - The system needed checkpoint-and-resume and rainbow deployments.
  — [Anthropic engineering](https://www.anthropic.com/engineering/multi-agent-research-system)

**OpenAI deep research and web search**
- OpenAI recommends running deep research in background mode with webhooks that notify when a long request finishes. — [OpenAI community announcement](https://community.openai.com/t/deep-research-in-the-api-webhooks-and-web-search-with-o3/1299919)
- Background mode reportedly keeps response data for about 10 minutes so polling works, which makes it incompatible with ZDR. This comes from a search-result summary of OpenAI's guide; verify before relying on it. — [OpenAI deep research guide](https://developers.openai.com/api/docs/guides/deep-research)
- o3-deep-research costs $10 input / $40 output per million tokens ($2.50 cached), as read from localized OpenAI model pages via search. The dated snapshot `o3-deep-research-2025-06-26` appears discontinued. — [OpenAI o3-deep-research model page](https://developers.openai.com/api/docs/models/o3-deep-research)
- The current guide page now centres on the hosted `web_search` tool with `gpt-6.2-astra` for multi-step research and recommends `background: true` for long multi-search tasks. Citations come back as `url_citation` annotations with `start_index`, `end_index`, `url` and `title`, and inline citations must be shown as clickable links. — [OpenAI deep research / web search guide](https://developers.openai.com/api/docs/guides/deep-research)

**Gemini Deep Research agent**
- The agent is in preview and available "exclusively using the Interactions API". The pattern is to start with `background=true`, then poll. Vertex docs say background execution plus streaming is required, which differs from the Gemini API example. — [Gemini Deep Research docs](https://ai.google.dev/gemini-api/docs/interactions/deep-research.md.txt); [Vertex Deep Research docs](https://docs.cloud.google.com/gemini-enterprise-agent-platform/agents/use-deep-research?authuser=2)
- Billing reportedly follows Gemini 3 Pro token rates. Stored interactions reportedly last 1 day on the free tier and 55 days on paid. Both details come from forum posts, not official pages. — [Google AI forum](https://discuss.ai.google.dev/t/deep-research-agent-api-questions-for-rate-limitsand-costs/111904)

**Stanford STORM and Co-STORM**
- STORM (Synthesis of Topic Outlines through Retrieval and Multi-perspective Question Asking) works in three steps:
  - It discovers perspectives from articles on similar topics.
  - It simulates conversations in which writers with those perspectives question a topic expert grounded in internet sources.
  - It curates the results into an outline before writing.
  Against an outline-driven RAG baseline, STORM gained 25% (absolute) on organization and 10% on coverage, measured on the FreshWiki dataset. — [STORM paper, arXiv 2402.14207](https://arxiv.org/html/2402.14207v1); [STORM project page](https://storm-project.stanford.edu/research/storm/)
- Co-STORM (EMNLP 2024) adds human-AI collaboration through a dynamic hierarchical "mind map". The README says outputs are not publication-ready. — [stanford-oval/storm GitHub](https://github.com/stanford-oval/storm)

**Open-source agents**
- GPT Researcher:
  - Planner agents generate research questions, execution agents gather information and a publisher aggregates the report.
  - It aggregates "over 20 sources".
  - Deep Research mode explores a tree with configurable breadth and depth, takes "~5 minutes" and costs "~$0.4 per research" with o3-mini on high effort.
  - Tavily is the default retriever, and MCP is supported.
  - The repo gives no measured citation accuracy.
  — [GPT Researcher GitHub](https://github.com/assafelovic/gpt-researcher)
- LangChain open_deep_research:
  - Separate model roles: summarization (gpt-4.1-mini), research, compression and final report.
  - Search uses Tavily by default, or native Anthropic or OpenAI web search, plus MCP.
  - Deep Research Bench RACE scores: defaults 0.4309 ($45.98 for the 100-task run), Claude Sonnet 4 research 0.4401 ($187.09), GPT-5 0.4943.
  - The repo "was archived by the owner on Aug 21, 2026."
  — [open_deep_research GitHub](https://github.com/langchain-ai/open_deep_research)
- Hugging Face Open Deep Research (Feb 2025) used a smolagents CodeAgent that writes actions as code. It scored about 55% on the GAIA validation set, against 67.36% for OpenAI Deep Research. — [Hugging Face blog](https://huggingface.co/blog/open-deep-research); [TechCrunch](https://techcrunch.com/2025/02/04/hugging-face-researchers-aim-to-build-an-open-version-of-openais-deep-research-tool)
- Programmatic tool calling, where code calls tools and filters their output, is Anthropic's 2026 version of the same "code as action" idea. On BrowseComp and DeepSearchQA it averaged 11% better performance with 24% fewer input tokens. — [Programmatic tool calling docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling)

### Inferences
- Recommended shape for Untangle:
  1. Scope the question against the repository graph first.
  2. Plan 2–4 targeted web queries, seeded with exact identifiers from repo evidence: package names and versions, error strings, issue and PR numbers, linked URLs in commits.
  3. Search with tight `max_uses` and fetch the top results.
  4. Compress each source into quote-anchored notes.
  5. Synthesize with citations on.
  6. Run a separate verification pass.
  This is the single-agent tier of Anthropic's effort rules (3–10 tool calls), which suits the Haiku-tier cost limit.
- The most useful idea from STORM for code archaeology is questioning from several perspectives (maintainer, dependency upstream, security advisory, user bug report). Its long-article generation is not needed.
- A full lead-plus-subagents setup (about 15 times chat tokens) should be reserved for an explicit "deep investigate" mode, ideally run in the GitHub Actions worker rather than a request path.

### Gaps
- I did not verify official current OpenAI deep-research model pricing (o4-mini-deep-research) on a primary page, or official per-run Gemini Deep Research costs.
- I did not find published 2026 versions of GPT Researcher or STORM benchmark numbers, or citation-accuracy numbers for these open-source agents.

## 4. Techniques that keep citations accurate, and published failure rates

### Takeaway
Citation errors in research agents are common and well documented:
- Generative search engines fully support only 51.5% of sentences (2023 study).
- AI search tools gave wrong answers on more than 60% of news-citation queries (2025 study).
- Deep-research agents reach only 40–80% citation accuracy (DeepTRACE, Sept 2025).

The defences that work are API-guaranteed quote pointers (Citations or `search_result` blocks), a separate post-hoc check that each claim is entailed by its cited passage (small NLI or MiniCheck-style models are about 400 times cheaper than GPT-4), deduplication and source-quality rules, and explicit handling of disagreement between sources.

### Cited Findings

**Published failure rates**
- Liu, Zhang and Liang (Findings of EMNLP 2023) tested Bing Chat, NeevaAI, perplexity.ai and YouChat. Only 51.5% of generated sentences were fully supported by citations (citation recall), and 74.5% of citations supported their sentence (citation precision). — [arXiv 2304.09848](https://arxiv.org/abs/2304.09848)
- Tow Center / Columbia Journalism Review (March 2025), eight AI search engines:
  - "the chatbots provided incorrect answers to more than 60% of queries".
  - Perplexity was wrong 37% of the time; Grok-3 Search 94–96%, depending on the outlet reporting.
  - More than half of Gemini's and Grok 3's responses cited fabricated or broken URLs.
  — [CJR Tow Center study](https://www.cjr.org/tow_center/we-compared-eight-ai-search-engines-theyre-all-bad-at-citing-news.php); [Nieman Lab](https://www.niemanlab.org/2025/03/ai-search-engines-fail-to-produce-accurate-citations-in-over-60-of-tests/)
- DeepTRACE (Microsoft Research and others, arXiv 2509.04499, ICLR 2026 poster) audits generative search engines and deep-research agents on eight measures using statement-level decomposition and citation and factual-support matrices. Deep-research modes "still exhibit large fractions of unsupported statements, with citation accuracy ranging from 40–80% across systems", and stay one-sided on debate questions. — [DeepTRACE arXiv](https://arxiv.org/abs/2509.04499v1); [Microsoft Research page](https://microsoft.com/en-us/research/publication/deeptrace-auditing-deep-research-ai-systems-for-tracking-reliability-across-citations-and-evidence)
- Per-system DeepTRACE figures are unverified. A search summary reported unsupported-statement rates of YouChat(DR) 74.6% and PPLX(DR) 97.5%, and a third-party benchmark page lists GPT-5 Deep Research at 12.5% unsupported and 79.1% citation accuracy. — [alphaXiv DeepTRACE benchmark page](https://www.alphaxiv.org/benchmarks/microsoft/deeptrace)

**Techniques**
- Quote-anchored citations through the API: Claude Citations guarantee valid pointers to provided documents and cite more relevant quotes than prompt-based citing. `search_result` blocks extend this to self-supplied search results. — [Citations docs](https://platform.claude.com/docs/en/build-with-claude/citations); [Search results docs](https://platform.claude.com/docs/en/build-with-claude/search-results)
- Claim extraction plus support checking (DeepResearch Bench FACT): extract statement-URL pairs from the report, deduplicate them, then scrape each URL and have an LLM judge whether it supports the statement. This yields "Citation Accuracy" (the percentage of supported citations) and "Effective Citations" (supported citations per task). — [DeepResearch Bench GitHub](https://github.com/Ayanami0730/deep_research_bench)
- Cheap entailment checking: MiniCheck-FT5, a 770M-parameter Flan-T5, matches GPT-4 on grounding-document fact-checking "at ~400x lower cost". The LLM-AggreFact benchmark and leaderboard track such checkers. — [MiniCheck, arXiv 2404.10774](https://arxiv.org/abs/2404.10774); [ACL Anthology](https://aclanthology.org/2024.emnlp-main.499)
- A dedicated citation pass: Anthropic runs a CitationAgent after research to attribute claims. Its LLM judge scores "citation accuracy" and "source quality" separately. — [Anthropic engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- Source-credibility heuristics: Anthropic had to add source-quality rules after agents preferred SEO content farms. — [Anthropic engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- Freshness signals: Claude's web search returns `page_age`, web fetch returns `retrieved_at`, and Tavily returns `published_date` and can filter by it. — [Web search docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool); [Web fetch docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool); [Tavily search API](https://docs.tavily.com/documentation/api-reference/endpoint/search)
- Contradiction and one-sidedness: DeepTRACE found deep-research agents "highly one-sided on debate queries", which suggests checking for counter-evidence explicitly. — [DeepTRACE arXiv](https://arxiv.org/abs/2509.04499v1)

### Inferences
Concrete validation pipeline for Untangle, extending the existing strict-citation validator:
- **Evidence IDs.** Every web source the service fetched becomes an evidence record: a hash of URL plus `retrieved_at`, a stored text snapshot or hash, and the domain. Only IDs from this run's retrieval set are citable, as is already done for repo evidence.
- **Quote anchoring.** Require each web citation to carry `cited_text` that matches the stored snapshot exactly (`char_location` from web fetch, or block indices from `search_result`). Reject citations whose quote is not a substring.
- **Entailment.** Run a cheap checker on each claim and its cited passage: a Haiku 5.5 call with a yes/no rubric, or a MiniCheck-class model. If support is missing, drop the claim or downgrade it to "unverified".
- **Separate internal and external.** Show repo evidence and web evidence in separate UI groups. When the web contradicts repo evidence (for example an upstream changelog against a commit message), show both rather than merging them.
- **Dedupe.** Normalize URLs (strip tracking parameters, resolve canonical links) and collapse mirrors such as GitHub issue pages versus API URLs.
- **Credibility tiers.** Rank the project's own repo first, then upstream repos and official docs, then standards, CVE and advisory databases, then Q&A sites, then blogs. Ban content farms. Claude's `allowed_domains` can enforce a tier-1 allowlist on the first pass.
- **Refusal.** If no web claim survives verification, the research answer should refuse or fall back to repo-only evidence, matching current behaviour.

### Gaps
- I found no published citation-hallucination rate specific to Claude's server web search, or to Haiku-tier models acting as research agents.
- I did not verify DeepTRACE's per-system numbers against the paper body.
- I found no peer-reviewed study of credibility-scoring methods that gives numeric gains for research agents.

## 5. Evaluation: benchmarks and building a small gold set

### Takeaway
Public benchmarks measure either hard-to-find answers (BrowseComp, BrowseComp-Plus, GAIA, FRAMES) or report and citation quality (DeepResearch Bench RACE/FACT, DeepTRACE). None measures code archaeology. Anthropic started its research-agent eval with about 20 real queries and a single-call LLM judge, which is a practical template for Untangle's gold set.

### Cited Findings
- **BrowseComp** (OpenAI, April 2025, arXiv 2504.12516): 1,266 short-answer, hard-to-find questions, trimmed from 1,287 after 21 bad labels were removed. It is modelled on SimpleQA and published in simple-evals. — [arXiv 2504.12516](https://arxiv.org/abs/2504.12516); [OpenAI announcement](https://openai.com/index/browsecomp/)
- Third-party trackers report top 2026 scores around 90% (GPT-5.5 Pro 90.1%); this is unverified. — [llm-stats BrowseComp](https://llm-stats.com/benchmarks/browsecomp)
- **BrowseComp-Plus** (arXiv 2508.06600; ACL 2026) replaces live web search with a fixed, curated corpus with human-verified supporting documents and hard negatives, so the retriever's contribution can be isolated. GPT-5 scored 55.9% with BM25 and 70.1% with Qwen3-Embedding-8B; Search-R1 with BM25 scored 3.86%. — [arXiv 2508.06600](https://arxiv.org/abs/2508.06600v1); [ACL Anthology](https://aclanthology.org/2026.acl-long.1023/)
- **FRAMES** (Google DeepMind and Harvard, arXiv 2409.12941): 824 multi-hop questions, each needing 2–15 Wikipedia articles. Gemini-Pro-1.5 scored 40.8% naive, 47.4% with BM25, 66% with multi-step retrieval and 72.9% with oracle retrieval. — [arXiv 2409.12941](https://arxiv.org/html/2409.12941v1); [HF dataset](https://huggingface.co/datasets/google/frames-benchmark)
- **GAIA**: OpenAI Deep Research scored 67.36% and HF Open Deep Research about 55%, both on the validation set in early 2025. — [Hugging Face blog](https://huggingface.co/blog/open-deep-research)
- **DeepResearch Bench** (arXiv 2506.11763) has "100 PhD-level research tasks… across 22 distinct fields". It uses RACE (reference-based, adaptive criteria) and FACT (citation accuracy and effective citations). The RACE evaluator was switched to GPT-5.5, which agrees with humans 71.82% of the time against a 68.78% human inter-annotator baseline. — [arXiv 2506.11763](https://arxiv.org/abs/2506.11763); [GitHub](https://github.com/Ayanami0730/deep_research_bench)
- **DeepSearchQA** (Google DeepMind) is used by Anthropic alongside BrowseComp for agentic search evaluation. — [Programmatic tool calling docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling)
- **DeepTRACE** dataset, reported by a secondary source: 303 queries (168 debate questions from ProCon.org and 135 expertise questions) across 9 systems. — [alphaXiv DeepTRACE page](https://www.alphaxiv.org/benchmarks/microsoft/deeptrace)
- **Building a small eval**: Anthropic began with "about 20 queries representing real usage" because early changes had large effects. A single LLM-judge call that outputs 0.0–1.0 scores plus pass/fail on factual accuracy, citation accuracy, completeness, source quality and tool efficiency matched human judgment best. Human testers caught source-quality failures that the judge missed. — [Anthropic engineering](https://www.anthropic.com/engineering/multi-agent-research-system)

### Inferences
A gold set for Untangle research mode of about 20–40 items could combine four kinds of question:
- Questions whose answer needs both repo and web evidence, for example "why is dependency X pinned below v3?", where the commit links an upstream issue.
- Questions answerable from the repo alone, to check the agent does not search needlessly.
- Questions with no evidence, where the expected behaviour is refusal.
- Adversarial pages containing prompt injections.

Each item should record the expected cited sources (URLs and repo evidence IDs), required facts and forbidden claims. Score each run on:
- FACT-style citation accuracy, checked against stored snapshots.
- Refusal correctness.
- Searches and dollars per answer.
- Latency against the Vercel limit.

Using a fixed snapshot of fetched pages (the BrowseComp-Plus idea) makes the gold set reproducible despite web drift. It also keeps the opt-in production tests in AGENTS.md cheaper, since they make real billed calls.

### Gaps
- I found no existing benchmark for answering "why is the code like this?" with external web evidence.
- I did not retrieve the current DeepResearch Bench leaderboard numbers per system (the leaderboard was migrating in 2026).
- I did not confirm GAIA's current question count or leaderboard.

## 6. Running long research jobs on serverless (Vercel) and the GitHub Actions worker

### Takeaway
A Python function on Vercel can run up to 300 s on Hobby, 800 s on Pro and Enterprise, or 1,800 s in an extended beta, so a short investigation fits in a streamed request. Anything longer needs a durable job pattern. Options are Vercel Workflows (GA April 2026, supports Python, retries each step, resumes from an event log), Vercel Queues (beta, at-least-once delivery), or Untangle's existing GitHub Actions worker (6 h per job). Claude's `pause_turn` and the vendors' background-and-poll APIs fit a persisted, resumable state machine.

### Cited Findings
- **Vercel duration limits** with Fluid compute (the default):
  - Hobby: 300 s default and maximum.
  - Pro and Enterprise: 300 s default, 800 s maximum, 1,800 s extended maximum in beta.
  - Extended durations support `python3.12`, `python3.13` and `python3.14`, and must be set per function (above 800 s), for example in `vercel.json` keyed on the FastAPI entrypoint such as `app/main.py`.
  - "If a function runs for longer than its set maximum duration, Vercel will terminate it."
  — [Vercel max duration docs](https://vercel.com/docs/functions/configuring-functions/duration)
- **Keeping streams alive**: Vercel sends HTTP/2 PING frames on idle long-running responses. HTTP/1.1 clients and intermediaries may still close idle connections, so the docs advise streaming progress or heartbeat data while work runs. — [Vercel max duration docs](https://vercel.com/docs/functions/configuring-functions/duration)
- **Background options on Vercel**:
  - `waitUntil`: no durability; a task is lost if the function hits its maximum duration.
  - Cron: no retries; Hobby allows one run per day.
  - Queues (push, public beta): at-least-once delivery, retries, 24 h retention by default (up to 7 days). Python consumers use `@subscribe` with `max_concurrency` and `max_attempts`.
  - Workflows (GA since April 2026, Python supported): no overall duration limit, but each step is bounded by the function maximum. Steps retry up to 3 times by default, and state lives in an event log so runs resume after crashes or deployments. Each step costs 3 events; Hobby includes 50,000 events per month.
  - Daemons: always-on workers, in beta.
  — [Vercel KB: Background workers](https://vercel.com/kb/guide/background-workers-on-vercel)
- **GitHub Actions limits**: 6 hours per job on GitHub-hosted runners and 35 days per workflow run. Free plans allow 20 concurrent jobs. `GITHUB_TOKEN` is limited to 1,000 API requests per hour per repository. — [GitHub Actions limits](https://docs.github.com/en/actions/reference/limits)
- **Claude API**: long server-tool turns return `pause_turn`. To continue, resend the content and keep every paused response in order; dropping one loses work and can return a 400. Search and fetch events stream over SSE. — [Server tools docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)
- **Other vendors' background APIs**: OpenAI deep research recommends background mode with webhooks or polling. Gemini Deep Research uses `background=true`, then polling. — [OpenAI community announcement](https://community.openai.com/t/deep-research-in-the-api-webhooks-and-web-search-with-o3/1299919); [Gemini Deep Research docs](https://ai.google.dev/gemini-api/docs/interactions/deep-research.md.txt)
- **Resumability in production**: Anthropic's research system resumes from checkpoints rather than restarting, because agents are stateful and errors compound. — [Anthropic engineering](https://www.anthropic.com/engineering/multi-agent-research-system)

### Inferences
Suggested two-tier design:

**Quick Investigate** (inline, under about 120–250 s)
- Runs inside the existing FastAPI function and streams progress events over SSE.
- One Haiku 5.5 request with `web_search` (`max_uses` 3–5) and `web_fetch` (`max_content_tokens` around 8–15k, citations on), with a bounded `pause_turn` loop.
- Each step (plan, search, fetch, verify) is persisted to Neo4j or the existing job store, so a client reconnect can resume the display.

**Deep Investigate** (asynchronous)
- Enqueued as a research job record (status, plan, completed steps, evidence IDs, spend so far).
- Run either in Vercel Workflows, one step per search, fetch or verification under 300 s, or by extending the existing GitHub Actions repository worker, which already processes jobs.
- The UI polls the job status, as it already does for repository imports.
- Every step is idempotent and keyed by an evidence hash, so at-least-once retries never duplicate evidence or double-bill searches.
- A hard budget (maximum searches, tokens and dollars) is stored on the job and checked before each step.

The Batches API halves token cost and charges the same for web search, but it is throttled and has no fixed latency, so it suits scheduled background enrichment, not interactive questions.

### Gaps
- I did not verify Vercel Workflows' Python SDK API details or per-event pricing beyond the Hobby allowance.
- I did not check GitHub `schedule` trigger delays or the minimum interval (not on the limits page).
- I found no documented maximum number of server-loop iterations before `pause_turn` for synchronous Claude requests.

## 7. Safety: prompt injection from fetched pages, and vendor mitigations

### Takeaway
Treat every fetched page as hostile. Even with Anthropic's improved safeguards, adaptive prompt-injection attacks succeed 1.4%–2.4% of the time against browser agents. The vendor and research consensus is architectural rather than prompt-only. Keep web reading separate from private data and from tools with side effects, restrict which URLs and domains can be fetched, and let untrusted content shape results only as data, never as control flow.

### Cited Findings
- Anthropic (24 Nov 2025) uses RL training to refuse injections and classifiers that scan all untrusted content entering context, backed by red teaming. Attack success against an adaptive Best-of-N attacker (100 attempts per environment):

  | Model | Model only | Old safeguards | Improved safeguards |
  |---|---|---|---|
  | Sonnet 4.5 | 13.8% | 10.8% | 1.9% |
  | Haiku 4.5 | 12.0% | 11.1% | 2.4% |
  | Opus 4.5 | 8.0% | 7.6% | 1.4% |

  "A 1% attack success rate—while a significant improvement—still represents meaningful risk." — [Anthropic: prompt injection defenses](https://www.anthropic.com/research/prompt-injection-defenses)
- Web fetch exfiltration warning: "Enabling the web fetch tool in environments where Claude processes untrusted input alongside sensitive data poses data exfiltration risks." Suggested mitigations: disable fetch, cap `max_uses`, use `allowed_domains`, and use `url_sources` to stop client tool results from counting as URL sources. Built-in guards: Claude cannot fetch URLs that appear only in its own output, and URLs that appear to contain credentials are refused. — [Web fetch tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- Domain-filter homograph risk: use ASCII-only domain lists. — [Server tools docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)
- OpenAI: "If your research also uses private records, run public web search and private MCP lookups in separate requests." — [OpenAI deep research / web search guide](https://developers.openai.com/api/docs/guides/deep-research)
- Beurer-Kellner, Tramèr et al. (arXiv 2506.08837, June 2025) propose six design patterns, including plan-then-execute (fix the plan before reading untrusted data) and dual LLM (a quarantined model processes untrusted text and returns symbolic variables to a privileged model). Limits: untrusted data can still shape parameters, and the quarantined model can still be injected. — [arXiv 2506.08837](https://arxiv.org/abs/2506.08837v3); [Simon Willison summary](https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/)
- Dynamic filtering runs model-written code in a container, and that path is not ZDR or HIPAA eligible. — [Server tools docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)

### Inferences
Mitigations mapped to Untangle:
1. **Stage separation, following OpenAI's advice.** Run the web-research step without private repository content in context. Send only the user's question and minimal public identifiers (package names, public issue URLs).
2. **A synthesis step with no web tools.** It joins repo evidence with already-fetched, verified web snippets. Because it has no fetch tool, an injected instruction has no exfiltration channel.
3. **Private repositories.** For private repo imports, either disable research mode or show a clear warning, since search queries themselves can leak identifiers to third-party providers.
4. **Restrict what can be fetched.** Use web fetch `url_sources` and `allowed_domains`, with a tier-1 allowlist for the first pass.
5. **Mark web text as untrusted.** Wrap fetched text in clearly delimited untrusted-data blocks or `search_result` blocks, and tell the model that instructions inside them are data.
6. **Validate after generation.** Strip or flag answer text that shows injection effects: instructions to the user, unexpected links, or URLs outside the retrieval set. This fits naturally into the existing post-generation citation validator.
7. **Log carefully.** Record fetched URLs and domains for audit, but never secrets. AGENTS.md already forbids credentials in logs or browser code.

### Gaps
- I found no attack-success numbers specific to plain web search or fetch use (as opposed to browser agents), and no numbers for Haiku 5.5.
- I did not check whether Anthropic's classifier-based injection scanning applies to API server-tool results or only to Claude for Chrome.
- I did not verify OpenAI's full prompt-injection guidance page, which the guide links but which was not fetched.
