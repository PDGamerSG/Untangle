# External data sources and APIs for code-archaeology evidence (as of November 2026)

Scope: public internet sources Untangle could query to attach external evidence to Decision nodes about dependencies (npm, PyPI, Go, Cargo, Maven), config keys, runtimes and workarounds. Deployment context: FastAPI on Vercel serverless, a scheduled GitHub Actions worker, Neo4j Aura Free (no APOC/GDS), and a preference for free sources that need no key.

Method note: besides reading documentation, I sent live, unauthenticated requests to most endpoints on 2026-11-20 at about 23:20 UTC (the "live probe" citations below). Each probe citation links the exact endpoint that was called. Probe results show what one anonymous client saw from one IP. They are not documented guarantees.

## Vulnerability data: OSV.dev, GitHub Advisory Database, NVD API 2.0, CISA KEV, EPSS. Which should be primary?

### Takeaway
Use OSV.dev as the primary source. It needs no key, states no rate limit, covers all five Untangle ecosystems, offers a batch endpoint plus GCS bulk dumps, and its records carry machine-readable `introduced`/`fixed` version events, which are exactly what a "this pin can now be removed" claim needs. Add CISA KEV (one daily JSON file) and FIRST EPSS (API or daily CSV) as prioritization signals. Use the GitHub Advisory REST API only when a single call should return `first_patched_version` plus EPSS. Keep NVD as a key-gated fallback for CVSS and CPE detail, called only from the worker.

### Cited Findings

**OSV.dev (primary)**
- Endpoints: `POST https://api.osv.dev/v1/query`, `POST /v1/querybatch`, `GET /v1/vulns/{id}`. The experimental endpoints are `GET /v1experimental/importfindings`, `POST /v1experimental/determineversion` (C/C++) and `POST /v1experimental/ubuntu/binary-to-source`. The OpenAPI spec is at https://osv.dev/docs/osv_service_v1.swagger.json — [OSV API docs](https://google.github.io/osv.dev/api/)
- Rate limits: the docs say "Currently there are no limits on the API." Responses are capped at 32 MiB over HTTP/1.1, with no cap over HTTP/2. HTTP/2 is recommended for large responses — [OSV API docs](https://google.github.io/osv.dev/api/)
- `querybatch` returns only `{id, modified}` per vulnerability, so full records need follow-up `GET /v1/vulns/{id}` calls. It paginates per query, with a separate `next_page_token` for each query that needs one, when one query returns more than 1,000 vulns or the whole batch returns more than 3,000 ("these numbers can vary slightly") — [OSV querybatch docs](https://google.github.io/osv.dev/post-v1-querybatch/); confirmed by live probe of [api.osv.dev/v1/querybatch](https://api.osv.dev/v1/querybatch). The probe accepted both `{"package":{"name","ecosystem"},"version"}` and `{"package":{"purl":"pkg:pypi/django@3.2.0"}}` query shapes.
- A full record (`GET /v1/vulns/GHSA-p6mc-m468-83gw`) carries `aliases`, `affected[].ranges[].events` (for example `{"introduced":"3.7.0"},{"fixed":"4.17.19"}`), `references`, `severity`, and `database_specific.cwe_ids` (for example `CWE-1321`). Records sourced from GHSA also carry `github_reviewed` and `nvd_published_at` — live probe of [api.osv.dev/v1/vulns/GHSA-p6mc-m468-83gw](https://api.osv.dev/v1/vulns/GHSA-p6mc-m468-83gw)
- Bulk data: `gs://osv-vulnerabilities/{ECOSYSTEM}/all.zip`. `gs://osv-vulnerabilities/modified_id.csv` (global) and per-ecosystem `modified_id.csv` files are sorted newest first, so an incremental sync can stop reading once it reaches a timestamp it has already processed. An ecosystem list is at `gs://osv-vulnerabilities/ecosystems.txt` — [OSV data sources](https://google.github.io/osv.dev/data/); [OSV FAQ](https://google.github.io/osv.dev/faq/)
- On 2026-11-20 the ecosystem list included npm, PyPI, Go, crates.io, Maven, NuGet, RubyGems, Packagist, Hex, Pub, GitHub Actions, VSCode, CRAN, Hackage, Julia, opam, SwiftURL, Bitnami, plus many Linux distributions (Debian, Ubuntu, Alpine, Red Hat, SUSE, Wolfi, Chainguard and others) — live fetch of [ecosystems.txt](https://osv-vulnerabilities.storage.googleapis.com/ecosystems.txt)
- The Go vulnerability database (https://vuln.go.dev) serves OSV-format data with a module index, per-ID reports and a full zip. Its index reported `modified: 2026-11-11T02:51:11Z` on the probe date — [Go Vulnerability Database](https://go.dev/security/vuln/database); live probe of [vuln.go.dev/index/db.json](https://vuln.go.dev/index/db.json)

**GitHub Advisory Database (GHSA)**
- REST: `GET https://api.github.com/advisories?ecosystem=npm&affects=lodash@4.17.15`. It works without authentication (60 requests/hour per IP) and returns `ghsa_id`, `cve_id`, `vulnerabilities[].vulnerable_version_range`, `first_patched_version` (for example `"4.18.0"`), `vulnerable_functions`, `cvss_severities`, `cwes`, `epss`, `withdrawn_at`, `source_code_location` and `references`. The response carried `cache-control: public, max-age=60` — live probe of [api.github.com/advisories](https://api.github.com/advisories?ecosystem=npm&affects=lodash@4.17.15&per_page=1)
- Changed API: REST API version **2026-03-10**, released 10 March 2026, "Deprecate[s] cvss property in favor of cvss_severities for advisory APIs". It also removes the deprecated `rate` property from `/rate_limit` and the singular `assignee` field from issues and pulls. The previous version stays supported for at least 24 months after a new version ships — [GitHub REST breaking changes](https://docs.github.com/en/rest/about-the-rest-api/breaking-changes)
- GraphQL (`securityVulnerabilities`, `securityAdvisories`) needs a token. Unauthenticated `POST /graphql` returned HTTP 403, and `/rate_limit` shows `graphql.limit: 0` for anonymous clients — live probe of [api.github.com/graphql](https://api.github.com/graphql) and [api.github.com/rate_limit](https://api.github.com/rate_limit). Renovate's docs say "GitHub blocks unauthenticated GraphQL API use" — [Renovate changelogs](https://docs.renovatebot.com/key-concepts/changelogs/)
- Rate limits: 60 requests/hour unauthenticated (per IP), 5,000/hour for an authenticated user, and 1,000/hour per repository for `GITHUB_TOKEN` in Actions. Secondary limits: at most 100 concurrent requests and 900 points/minute for REST (most GETs cost 1 point), and they "may change without notice" — [GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)

**NVD API 2.0**
- Endpoint: `https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=...`. It answered without a key, returned no rate-limit headers, and was served via Cloudflare. A CVE record carries `vulnStatus`, `metrics`, `weaknesses`, `configurations` (CPE), `references`, and KEV cross-fields `cisaExploitAdd`, `cisaActionDue` and `cisaRequiredAction`. It also carried an `affected` key that I did not find documented — live probe of [NVD CVE API](https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2021-44228)
- Rate limit: 5 requests per rolling 30-second window without a key, 50 with a key. The key is sent in a request header in 2.0 (in 1.0 it was a URL parameter) — [NVD Start Here (via search result)](https://nvd.nist.gov/developers/start-here); [NVD API key announcement](https://nvd.nist.gov/general/news/API-Key-Announcement). NVD's pages would not render through my fetch tools, so these figures come from search snippets of the official pages.
- Dated changes: NVD's news page lists a deployment on **20 August 2025** that removed the legacy 1.1 vulnerability feeds and the 1.0 CPE Match feed, and a deployment on **16 September 2025** that changed API key provisioning — [NVD changes to feeds and APIs](https://nvd.nist.gov/general/news/changes-to-feeds-and-apis) (via search summary); [NVD news group: Legacy Data Feed File Retirement Update](https://groups.google.com/a/list.nist.gov/g/nvd-news/c/aofnAd3HP2g). An older NVD timeline page says legacy feed retirement was "extended until further notice", which conflicts with the August 2025 notice. That page probably predates it — [NVD change timeline](https://nvd.nist.gov/full_listing.cfm)
- Commercial alternative: VulnCheck's "NVD++" community tier has been limited to 1,000 requests/minute since 2026-02-25 (it needs an account) — [VulnCheck changelog 2026-02-25](https://docs.vulncheck.com/changelog/2026-02-25)

**CVE program context**
- In April 2025, CISA exercised an option on its $57.8M MITRE contract, which kept CVE running to **16 March 2026** — [The Record](https://therecord.media/cisa-extends-cve-program-contract-with-mitre); [The Register](https://www.theregister.com/2025/04/16/cve_program_funding_save/). Reports that funding was renegotiated in early 2026 come only from a secondary aggregator — [daily.dev summary](https://app.daily.dev/posts/cve-program-funding-secured-easing-fears-of-repeat-crisis-msccalk7v). The CVE Foundation was formed during the 2025 scare — [Computer Weekly](https://www.computerweekly.com/news/366622835/CVE-Foundation-pledges-continuity-after-MITRE-funding-cut)

**CISA KEV**
- Feed: `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` (about 1.87 MB). On the probe date it showed `catalogVersion "2026.11.20"` and `count 1790`, and returned `Last-Modified`, `ETag` and `cache-control: max-age=1524`, so conditional GETs work. Per-entry fields: `cveID, vendorProject, product, vulnerabilityName, dateAdded, shortDescription, requiredAction, dueDate, knownRansomwareCampaignUse, forensicTriage, notes, cwes` — live probe of [KEV JSON](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json)
- The KEV page offers CSV and JSON plus a CISA GitHub mirror. Its 2026 entries cite "BOD 26-04: Prioritizing Security Updates Based on Risk" and "Forensics Triage Requirements", which looks like the source of the new `forensicTriage` field — [CISA KEV catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)

**EPSS (FIRST)**
- Endpoint: `https://api.first.org/data/v1/epss` (labelled BETA). Parameters: `cve` (comma-separated, at most 2,000 characters), `date` (available since 2021-04-14), `days`, `epss-gt/lt`, `percentile-gt/lt`, `q`, `scope=public|time-series` (last 30 days). The default page size is 100 — [FIRST EPSS API](https://api.first.org/epss)
- The probe needed no key and returned `cache-control: public, max-age=86400` and `{"cve":"CVE-2021-44228","epss":"0.999990000","percentile":"1.000000000","date":"2026-11-20"}` — live probe of [api.first.org/data/v1/epss](https://api.first.org/data/v1/epss?cve=CVE-2021-44228)
- Daily bulk CSV: `https://epss.empiricalsecurity.com/epss_scores-current.csv.gz` redirects (302) to the dated file, `epss_scores-2026-11-20.csv.gz` on the probe date — live probe of [EPSS bulk CSV](https://epss.empiricalsecurity.com/epss_scores-current.csv.gz)
- GHSA REST advisory objects already embed an `epss` field — live probe of [api.github.com/advisories](https://api.github.com/advisories?ecosystem=npm&affects=lodash@4.17.15&per_page=1)

### Inferences
- OSV is the best primary source. It covers all five Untangle ecosystems under the ecosystem names the API expects (npm, PyPI, Go, crates.io, Maven), accepts purls (which Untangle can build from manifests), states no rate limit, and its `fixed` events answer the key question directly: is the pinned version affected, and which version fixes it? GHSA, PYSEC, RustSec and the Go vulndb all feed OSV, so calling GHSA separately mostly duplicates data.
- Suggested flow: in the GitHub Actions worker, send one `querybatch` with every (package, version) node, diff the returned `modified` timestamps against what is stored on the Neo4j `Advisory` nodes, and fetch full records only for new or changed IDs. As the corpus grows, switch to per-ecosystem `all.zip` plus `modified_id.csv` incremental sync.
- KEV is a single, small, conditionally fetchable file. Fetch it once a day in the worker and join on CVE alias. EPSS fits the same pattern, using the bulk CSV, or the API batched by about 100 CVEs within the 2,000-character `cve` parameter.
- NVD's 5 requests/30 seconds without a key rules it out for Vercel request paths. Use it only from the worker with a key, and only for CVEs that need CPE/CVSS detail OSV lacks.
- GHSA's REST change (`cvss` → `cvss_severities`) means a parser should read `cvss_severities` and pin the `X-GitHub-Api-Version` header.
- The CVE funding uncertainty argues for an OSV-first design: OSV IDs (GHSA-*, PYSEC-*, GO-*, RUSTSEC-*) do not depend on CVE assignment.

### Gaps
- I did not verify the OSV and GHSA data licenses this session. My belief is that GHSA data is CC-BY 4.0 per the github/advisory-database repo, and that OSV passes through each source's license, but neither was confirmed.
- I did not confirm the current EPSS model version, any EPSS API rate limit (the docs page links a rate-limit section I could not read), or the EPSS terms of use. The API page shows only "All Rights Reserved".
- I could not read NVD's start-here page directly because the fetch tools returned only the title, so the NVD figures rest on search snippets of official pages. I also could not find what the 16 September 2025 key-provisioning change actually involved.
- I could not confirm the license of the CISA KEV data, nor the meaning and schema of `forensicTriage` and of the NVD `affected` key.
- I could not confirm CVE program funding after March 2026 from a primary source.

## Package metadata: deps.dev, ecosyste.ms, Libraries.io, npm, PyPI, crates.io, Go proxy/pkg.go.dev, Maven Central. Deprecation and yank signals.

### Takeaway
deps.dev should be the cross-ecosystem backbone. It needs no key, its responses say `cache-control: public, max-age=3600`, it expressly permits caching, and its generated data is CC-BY 4.0. One GetVersion call returns `isDeprecated`/`deprecatedReason`, licenses, advisory keys, SLSA and attestation data, and the source repo; batch endpoints take up to 5,000 items. Go to the native registries for signals deps.dev normalizes away: PyPI `yanked_reason` and PEP 792 project status, crates.io `yank_message`, Go `retract`/`Deprecated`, and npm `deprecated` text. ecosyste.ms and Libraries.io are useful extras, but both now have tight or paid tiers. Maven Central applies consumption limits that tightened during 2026.

### Cited Findings

**deps.dev (Google Open Source Insights)**
- v3 (stable) GET endpoints on `https://api.deps.dev`: `/v3/systems/{system}/packages/{name}`, `.../versions/{version}`, `...:requirements`, `...:dependencies`, `/v3/projects/{projectKey}`, `/v3/projects/{projectKey}:packageversions`, `/v3/advisories/{id}`, `/v3/query`. Systems: GO, RUBYGEMS, NPM, CARGO, MAVEN, PYPI, NUGET. Dependency graphs are available for npm, Cargo, Maven and PyPI only. `Query` returns at most 1,000 results, and `GetProjectPackageVersions` at most 1,500 — [deps.dev API v3](https://docs.deps.dev/api/v3/)
- Terms: "Use of the deps.dev API is subject to the Google API Terms of Service." "Clients are expressly permitted to cache data served by the API." Generated data (resolved dependencies, advisory statistics, associations) is CC-BY 4.0 — [deps.dev API v3](https://docs.deps.dev/api/v3/)
- v3alpha adds `POST /v3alpha/versionbatch`, `/projectbatch`, `/findingsbatch`, `PurlLookup` / `PurlLookupBatch`, `GET ...:dependents`, `...:capabilities`, `:findings`, and `GetSimilarlyNamedPackages`. "Batch methods are limited to a maximum of 5000 requests in a batch," and more than that returns HTTP 400 — [deps.dev API v3alpha](https://docs.deps.dev/api/v3alpha/)
- Freshness: commonly used packages are "usually fresh, up to date to within an hour or so". Quiescent packages are refreshed by a constant-rate background scan, and "there is no mechanism for users to trigger an update". npm and PyPI licenses come from package metadata, Go licenses from `licensecheck`, and the value is shown as SPDX, `non-standard` or `unknown` — [deps.dev FAQ](https://docs.deps.dev/faq/)
- GetVersion for npm lodash 4.17.15 returned `isDeprecated`, `deprecatedReason`, `licenses`, `advisoryKeys` (GHSA IDs), `links`, `slsaProvenances`, `attestations`, `registries`, and `relatedProjects` (SOURCE_REPO and ISSUE_TRACKER with `relationProvenance: UNVERIFIED_METADATA`). There was no auth, `access-control-allow-origin: *` and `cache-control: public, max-age=3600` — live probe of [deps.dev GetVersion](https://api.deps.dev/v3/systems/npm/packages/lodash/versions/4.17.15)
- GetPackage lists every version with `publishedAt`, `isDefault`, `isDeprecated` and `deprecatedReason` — live probe of [deps.dev GetPackage](https://api.deps.dev/v3/systems/npm/packages/lodash)
- GetProject (`github.com/lodash/lodash`) returned stars, forks, open issues, license, an embedded OpenSSF `scorecard` (with check names) and `ossFuzz` — live probe of [deps.dev GetProject](https://api.deps.dev/v3/projects/github.com%2Flodash%2Flodash)
- `:dependents` returned `{"dependentCount":22636,"directDependentCount":7061,"indirectDependentCount":16209}` for lodash 4.17.21. It counts public dependents only — live probe of [deps.dev dependents](https://api.deps.dev/v3alpha/systems/npm/packages/lodash/versions/4.17.21:dependents); [deps.dev v3alpha](https://docs.deps.dev/api/v3alpha/)

**ecosyste.ms**
- `GET https://packages.ecosyste.ms/api/v1/registries/npmjs.org/packages/lodash` returned a rich record including `status`, `advisories`, `repo_metadata`, `issue_metadata`, `dependent_packages_count`, `rankings`, `maintainers` and `purl`. Headers: `x-ratelimit-limit: 15000`, `x-ratelimit-remaining: 4808`, `x-ratelimit-tier: parlay`, `x-ratelimit-consumer: anonymous`, `cache-control: public, max-age=86400` — live probe of [packages.ecosyste.ms](https://packages.ecosyste.ms/api/v1/registries/npmjs.org/packages/lodash)
- The pricing page lists three levels: 300, 1,000 and 5,000 requests/hour. The free level uses the "common" or "polite" pool, and the polite pool requires a contact email. The 1,000/hour tier uses an API key, and 5,000/hour is the commercial SLA tier — [ecosyste.ms pricing](https://ecosyste.ms/pricing) (via search summary); [ecosyste.ms rate limits](https://docs.ecosyste.ms/docs/usage/rate-limits/); [blog: rate limiting the right way (2025-09-01)](https://blog.ecosyste.ms/2025/09/01/rate-limiting-the-right-way.html); [nesbitt.io (2025-12-11)](https://nesbitt.io/2025/12/11/building-ecosytems-polite-api-rate-limits.html). The 15,000 limit seen in the probe conflicts with the published tiers, and `https://ecosyste.ms/api` returned HTTP 402 to curl.

**Libraries.io**
- The docs say "All API requests must include api_key parameter" and impose "a 60 request/minute rate limit based on your API key" (HTTP 429 beyond that). Endpoints include `/api/:platform/:name`, `/:version/dependencies` and `/dependents` — [Libraries.io API](https://libraries.io/api)
- The probe did answer without a key, with `x-ratelimit-limit: 10`, and returned `deprecation_reason`, `repository_status`, `status`, `dependents_count` and `latest_stable_release_number` — live probe of [libraries.io/api/npm/lodash](https://libraries.io/api/npm/lodash)

**npm registry**
- `GET https://registry.npmjs.org/{pkg}` with `Accept: application/vnd.npm.install-v1+json` (the abbreviated "corgi" document) still includes the per-version `deprecated` string. For example, request 2.88.2 says "request has been deprecated, see https://github.com/request/request/issues/3142". Headers: `cache-control: public, max-age=300`, ETag, Cloudflare — live probe of [registry.npmjs.org/request](https://registry.npmjs.org/request)
- Registry API docs list `GET /{package}`, `GET /-/v1/search` and others — [npm REGISTRY-API.md](https://raw.githubusercontent.com/npm/registry/main/docs/REGISTRY-API.md)

**PyPI**
- JSON API: `/pypi/{project}/json` and `/pypi/{project}/{version}/json`. `info.yanked` and `info.yanked_reason` sit at the release level, and per-file `yanked`/`yanked_reason` appear under `urls[]`. There is a `vulnerabilities` array (OSV-backed, with links like osv.dev/vulnerability/PYSEC-…, and a `withdrawn` timestamp so consumers can retract invalid reports) and an `ownership` key. The `releases` key is **deprecated**: "projects should shift to using the Index API" — [PyPI JSON API docs](https://docs.pypi.org/api/json/)
- "Due to the heavy caching and CDN use, there is currently no rate limiting of PyPI APIs at the edge." Clients should set a unique User-Agent. XML-RPC is deprecated and may be rate limited. BigQuery datasets exist — [PyPI API docs](https://docs.pypi.org/api/)
- Simple API JSON (`/simple/{project}/` with `Accept: application/vnd.pypi.simple.v1+json`) reported `meta.api-version: 1.4` and a top-level `project-status: {"status":"active"}` (PEP 792 status markers). Per-file entries carry `yanked`, `provenance`, `requires-python` and `upload-time`. Cache max-age is 600 (Simple) and 900 (JSON) — live probes of [pypi.org/simple/requests](https://pypi.org/simple/requests/) and [pypi.org/pypi/requests/json](https://pypi.org/pypi/requests/json)

**crates.io**
- `GET https://crates.io/api/v1/crates/{name}` returns crate-level `yanked`, `max_stable_version`, `repository` and `trustpub_only`, and per-version `yanked`, `yank_message`, `rust_version`, `license`, `published_by`, `audit_actions` and `trustpub_data`. A request with an empty User-Agent got **HTTP 403** — live probes of [crates.io/api/v1/crates/serde](https://crates.io/api/v1/crates/serde)
- Crawler policy: "limit API consumers to a rate of one call per second, and identification in a user-agent header is mandatory" — [Rust RFC 3463: crates.io policy update](https://rust-lang.github.io/rfcs/3463-crates-io-policy-update.html); the `crates_io_api` client docs give examples like `my_bot (help@my_bot.com)` — [crates_io_api docs](https://docs.rs/crates_io_api)

**Go: module proxy, index, pkg.go.dev API**
- Proxy: `https://proxy.golang.org/{module}/@v/list`, `/@v/{version}.info`, `.mod`, `.zip`, and `/@latest`. `@latest` for gin returned `{"Version":"v1.12.0","Time":"2026-02-28T10:10:09Z","Origin":{"VCS":"git","URL":"https://github.com/gin-gonic/gin","Hash":"73726dc…","Ref":"refs/tags/v1.12.0"}}` with `cache-control: public, max-age=60` — live probe of [proxy.golang.org](https://proxy.golang.org/github.com/gin-gonic/gin/@latest)
- `index.golang.org/index?since=…&limit=…&include=all` is a feed of new module versions. `/cached-only` avoids slow fetches. New tags become available "within one minute" of an explicit request, or up to 30 minutes if a stale entry was cached. Authors withdraw versions with `retract` directives, and the proxy does not remove cached modules on request — [proxy.golang.org](https://proxy.golang.org/)
- **New in 2026:** the official pkg.go.dev API launched on **21 May 2026** at `https://pkg.go.dev/v1beta/...`. Endpoints: `package/{path}`, `module/{path}`, `versions/{path}`, `packages/{path}`, `search?q=`, `symbols/{path}`, `imported-by/{path}` and `vulns/{path}`. It is stateless, GET-only, "built for caching", and the team is "committed to maintaining backward compatibility", with a v1 planned later. No auth or rate limits are stated — [Go Blog: pkgsite API](https://go.dev/blog/pkgsite-api); [Google Open Source Blog](https://opensource.googleblog.com/2026/06/a-new-pkggodev-api-for-go.html)

**Maven Central**
- `https://search.maven.org/solrsearch/select?q=g:...+AND+a:...&wt=json` still answers, with `latestVersion` and `versionCount` fields. `https://repo1.maven.org/maven2/{group}/{artifact}/maven-metadata.xml` gives `<latest>`, `<release>` and the full `<versions>` list via Cloudflare with `Last-Modified`/ETag — live probes of [search.maven.org](https://search.maven.org/solrsearch/select?q=g:com.google.guava+AND+a:guava&rows=1&wt=json) and [repo1 maven-metadata.xml](https://repo1.maven.org/maven2/com/google/guava/guava/maven-metadata.xml)
- **Consumption limits (2026):** Sonatype targets "the top few percent of traffic patterns". Limits apply to aggregate traffic per organization, network or infrastructure provider, including shared NAT egress. Blocks start short and can last up to "a maximum of 30 days". Thresholds "will move downward" over time, and "the right answer is not to retry harder." Clients should cache or use a repository manager — [Sonatype 429 FAQ](https://central.sonatype.org/faq/429-error/)
- Sonatype's Terms let it set "Consumption Tiers" at its discretion. In **June 2026**, Harness reported an incident after Sonatype "tightened IP-based rate limits for unauthenticated access". Sonatype asks direct-calling tools to send a "clear, tool-specific User-Agent". Separately, publishing limits took effect **1 October 2026** — [Central Terms](https://central.sonatype.org/terms.html); [Harness status](https://status.harness.io/incidents/mq6ptvcp9wbm); [Sonatype tooling-provider FAQ](https://central.sonatype.org/faq/429-tooling-provider/); [Sonatype news 2026-07-16](https://central.sonatype.org/news/20260716_publisher_pro_update/) (all via search summary except the 429 FAQ)
- Renovate users have reported hitting Maven Central rate limits even with conservative settings — [Renovate discussion #34778](https://github.com/renovatebot/renovate/discussions/34778)

### Inferences
- Deprecation and yank signals per ecosystem:
  - npm: per-version `deprecated` text.
  - PyPI: `yanked` + `yanked_reason`, plus PEP 792 `project-status`.
  - crates.io: `yanked` + `yank_message`.
  - Go: `retract` directives and `// Deprecated:` comments in go.mod, read from the `.mod` file; deps.dev's normalized flag may also cover these.
  - Maven: no native deprecation or yank concept was found.
  - Cross-ecosystem: deps.dev `isDeprecated`/`deprecatedReason`, ecosyste.ms `status`, Libraries.io `deprecation_reason`/`repository_status`.
- These signals support Decision evidence such as "pinned to X; X has since been yanked with reason R" or "package deprecated with pointer to issue URL", and the issue URL in a deprecation message can be linked to the upstream-issue checker.
- Mapping a version to a source commit or tag: the Go proxy's `Origin.Hash`/`Origin.Ref` is authoritative for Go, and deps.dev `relatedProjects` (SOURCE_REPO) gives the repo for every ecosystem, though it is flagged `UNVERIFIED_METADATA`. For npm, PyPI, Cargo and Maven, a tag must be guessed from the repo URL plus naming conventions (see the next section).
- Because Maven Central limits by organization or network and treats shared egress as one consumer, calling it from Vercel (shared cloud egress) carries more risk than calling it from the Actions worker. Prefer deps.dev for Maven metadata and fall back to `maven-metadata.xml` with conditional GETs only.
- ecosyste.ms numbers are uncertain: the observed 15,000 "parlay" tier conflicts with the published 300/1,000/5,000 tiers. Treat it as optional and identify the client politely.

### Gaps
- I did not verify npm registry rate limits, which I could not find documented, or the npm `gitHead` field and provenance/attestation endpoints this session.
- I could not confirm the licenses of the ecosyste.ms and Libraries.io data (both have historically been CC BY-SA 4.0).
- I did not verify the crates.io database-dump URL and frequency or the sparse index URL. The crates.io data-access page is a single-page app the tools could not render.
- I could not find any rate limits or terms for the pkg.go.dev v1beta API, and I did not check whether it exposes deprecated or retracted flags.
- The Maven Central consumption thresholds are not published numerically.
- Whether search.maven.org counts against the same consumption limits was not covered.

## Release notes and changelogs: GitHub Releases API, Keep a Changelog, compare API between tags, mapping package versions to repo tags

### Takeaway
Release notes come from the GitHub Releases API (`/releases/tags/{tag}`), with CHANGELOG files as the fallback. This is the same two-step approach Renovate uses. To confirm that an upstream fix shipped in a release, use the compare API as a containment test: compare `{fixCommit}...{tag}` and check that `status` is `ahead` or `identical`. Keep a Changelog headings (Added, Changed, Deprecated, Removed, Fixed, Security) give a cheap structured parse for claims like "config default changed upstream".

### Cited Findings
- `GET /repos/psf/requests/releases/tags/v2.32.3` returned `tag_name`, `name`, `published_at`, `prerelease`, `draft` and a Markdown `body` (the changelog text, for example "**Bugfixes** - Fixed bug breaking…") without auth — live probe of [api.github.com releases/tags](https://api.github.com/repos/psf/requests/releases/tags/v2.32.3). Published releases are visible to everyone, while drafts are visible only to users with push access — [GitHub Releases REST docs](https://docs.github.com/en/rest/releases/releases)
- Compare: `GET /repos/lodash/lodash/compare/4.17.20...4.17.21` returned `status: "ahead"`, `ahead_by: 3`, `behind_by: 0`, `total_commits: 3`, plus `commits[]`, `files[]`, `merge_base_commit` and `permalink_url`. The reverse (`4.17.21...4.17.20`) returned `status: "behind"`, `ahead_by: 0`, `behind_by: 3` — live probes of [compare 4.17.20...4.17.21](https://api.github.com/repos/lodash/lodash/compare/4.17.20...4.17.21) and [compare 4.17.21...4.17.20](https://api.github.com/repos/lodash/lodash/compare/4.17.21...4.17.20)
- Renovate looks up a package's `sourceUrl` from the datasource, then checks "both 'Releases' metadata in the repository and any commonly known 'changelog' file names", and filters to the versions in the update range. Fetching from github.com "requires a GitHub token because GitHub blocks unauthenticated GraphQL API use" — [Renovate: changelogs](https://docs.renovatebot.com/key-concepts/changelogs/)
- Keep a Changelog 1.1.0 uses an `## [Unreleased]` section and `### Added / Changed / Deprecated / Removed / Fixed / Security` groups, ISO 8601 dates, and footer compare links of the form `[unreleased]: https://github.com/.../compare/v1.1.2...HEAD` — [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
- Go proxy `.info`/`@latest` gives the exact tag ref and commit hash for a version (for example `refs/tags/v1.12.0` → `73726dc…`) — live probe of [proxy.golang.org](https://proxy.golang.org/github.com/gin-gonic/gin/@latest)
- deps.dev `GetProjectPackageVersions` (`/v3/projects/{id}:packageversions`) maps a source repo to the package versions built from it, capped at 1,500 — [deps.dev API v3](https://docs.deps.dev/api/v3/)

### Inferences
- Algorithm for "upstream fixed it in 2.4.0, the pin can now be removed":
  1. Get the repo from deps.dev `relatedProjects`, or from npm `repository` / PyPI `project_urls` / crates.io `repository`.
  2. Resolve candidate tags `v{ver}`, `{ver}` and `{pkg}-{ver}` / `{pkg}@{ver}` (monorepos) with `GET /repos/{o}/{r}/git/ref/tags/{tag}` or the tags list.
  3. Find the fix commit, from the closing event of the issue Untangle cited or the PR merge commit.
  4. Walk the release tags in ascending version order and run `compare/{fixSha}...{tag}`. The first tag with `status` `ahead` or `identical` is the first release containing the fix. `diverged` means the fix may have been cherry-picked, so fall back to searching the release body or CHANGELOG for the issue or PR number.
- Compare responses are immutable for a fixed pair of SHAs, so cache them permanently in Neo4j (or object storage) keyed by `(repo, base_sha, head_sha)`.
- For "config default changed upstream", fetch the release `body` and CHANGELOG between the pinned and latest versions, and run keyword or LLM extraction over the `Changed`/`Deprecated`/`Removed` sections for the config key name Untangle already holds. The compare API's `files[].patch` can confirm a default value changed in a defaults file.
- A full ladder of compare calls costs one core request per tag checked. That is fine within the worker's 1,000/hour `GITHUB_TOKEN` budget for a modest number of open "workaround" Decisions, but too many for the unauthenticated 60/hour from Vercel.

### Gaps
- I did not capture exact compare API limits this session. My understanding is 250 commits per page, with pagination for more, and a cap on files returned, but the docs excerpt did not include the figures.
- I did not verify the `generate-notes` endpoint or the limits on the releases list.
- I could not find a reliable cross-ecosystem source mapping version to tag for npm, PyPI, Cargo or Maven. Only Go provides it authoritatively; the rest need heuristics.
- I did not research changelog file parsing in other tools (for example Dependabot's release-notes fetcher).

## Upstream issue trackers: GitHub search API, linking issue URLs from commits and comments, checking closed/fixed state

### Takeaway
Don't use search for this. Extract `github.com/{o}/{r}/issues|pull/{n}` URLs from commit messages, code comments and npm deprecation strings, then call `GET /repos/{o}/{r}/issues/{n}` for `state`, `state_reason` and `closed_at`, and the timeline endpoint for the closing commit or PR. These use the core quota, while search is limited to 30 requests/minute authenticated, 10 unauthenticated, 10 for semantic/hybrid search, and 1,000 results per query.

### Cited Findings
- Search limits: authenticated clients get 30 requests/minute on all search endpoints except code search, which needs auth and allows 10/minute. Unauthenticated clients get 10/minute. A search returns at most 1,000 results, and timeouts can return partial data with `incomplete_results: true` — [GitHub REST search docs](https://docs.github.com/en/rest/search/search)
- **New (2026-04-02):** semantic and hybrid issue search became generally available on the same `/search/issues` endpoint via `search_type=semantic|hybrid` (the default is lexical), and on GraphQL via `ISSUE_SEMANTIC` / `ISSUE_HYBRID`. Semantic and hybrid queries are capped at 10 requests/minute, and the GraphQL details were corrected on 2026-11-10 — [GitHub changelog 2026-04-02](https://github.blog/changelog/2026-04-02-improved-search-for-github-issues-is-now-generally-available/)
- **2025-03-06:** `/search/issues` gained an `advanced_search` parameter for AND/OR and nested queries. Without it, a space acts as OR — [GitHub changelog 2025-03-06](https://github.blog/changelog/2025-03-06-github-issues-projects-api-support-for-issues-advanced-search-and-more/). Results include both issues and PRs unless filtered with `is:`/`type:` — [GitHub docs: searching issues](https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests)
- `GET /repos/{o}/{r}/issues/{n}` returns `state`, `state_reason` and `closed_at`. The `pull_request` key marks PRs, and `state_reason` was `null` for a closed PR. The request/request deprecation issue #3142 is still open — live probes of [psf/requests#6655](https://api.github.com/repos/psf/requests/issues/6655) and [request/request#3142](https://api.github.com/repos/request/request/issues/3142); the docs show `"state_reason": "completed"` in examples — [GitHub Issues REST docs](https://docs.github.com/en/rest/issues/issues)
- The timeline endpoint (`/repos/{o}/{r}/issues/{n}/timeline`) lists events triggered by timeline activity, such as closed and cross-referenced events — [GitHub timeline REST docs](https://docs.github.com/en/rest/issues/timeline)
- Core budget: 60 requests/hour unauthenticated per IP, 5,000/hour for a PAT, and 1,000/hour per repository for `GITHUB_TOKEN` — [GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- npm deprecation strings often embed the issue URL, for example "request has been deprecated, see https://github.com/request/request/issues/3142" — live probe of [registry.npmjs.org/request](https://registry.npmjs.org/request)

### Inferences
- Regex targets: `https?://github\.com/([\w.-]+)/([\w.-]+)/(issues|pull)/(\d+)`, short refs `owner/repo#123` in commit messages, and GitLab or other hosts as non-GitHub links to verify with the Wayback check below.
- Evidence states for a `Workaround` Decision:
  - "upstream issue still open"
  - "closed as completed" (then find the fixing PR or commit via the timeline `closed.commit_id` or cross-referenced PRs, and run the compare containment test above)
  - "closed as not_planned" (the workaround stays necessary)
  - "repo archived or 404" (switch to Software Heritage or Wayback)
- Search is for discovery ("is there an upstream issue for this workaround nobody linked?"). Its 30/minute budget suits only the worker, and semantic search, at 10/minute, is expensive.
- Run issue-state refreshes in the scheduled worker with `GITHUB_TOKEN` (1,000/hour/repo) or a GitHub App installation token (minimum 5,000/hour). Store `etag` on the Issue node so refreshes can be conditional.

### Gaps
- I could not confirm the complete current `state_reason` enum, which I believe is `completed`, `not_planned`, `reopened` and possibly `duplicate`, because the docs excerpt showed only `completed`.
- I could not confirm whether conditional requests that return 304 count against the primary rate limit; the rate-limit page does not mention it.
- The probed lodash issue #4874 returned 404, so I could not demonstrate a timeline `closed` event with `commit_id`.
- I did not verify the GraphQL `closedByPullRequestsReferences` field.

## Lifecycle: endoflife.date API (products, cycles) and runtime EOL data

### Takeaway
endoflife.date API v1 (`/api/v1/...`) is free, needs no key, is MIT-licensed, and returns machine-friendly booleans and dates (`isEol`, `eolFrom`, `isEoas`, `eoasFrom`, `isMaintained`, `isLts`). It also exposes purl identifiers per product, so Untangle can map a dependency or runtime node to a lifecycle product without hand-made tables. The legacy `/api/{product}.json` still works.

### Cited Findings
- The OpenAPI spec for v1 is MIT-licensed, has base URL `https://endoflife.date/api/v1`, and promises to "keep using the same major API version (`/api/v1`)". Operations: API index, list products (summary), list products (full; "preferably, use the /products endpoint"), get a product, get a product release cycle, get a product's latest release cycle, list categories, products in a category, list tags, products with a tag, list identifier types, and identifiers for a type — [endoflife.date OpenAPI v1](https://endoflife.date/docs/api/v1/openapi.yml)
- The index `GET /api/v1/` returns links to `products`, `categories` and `tags`, with `schema_version: 1.2.1` — live probe of [endoflife.date/api/v1/](https://endoflife.date/api/v1/)
- `GET /api/v1/products/python` returned `generated_at`, `last_modified`, an `identifiers` list with purls (`pkg:generic/python`, `pkg:deb/ubuntu/python3.15`, …), and `releases[]` with `name`, `releaseDate`, `isLts`, `ltsFrom`, `isEoas`, `eoasFrom`, `isEol`, `eolFrom`, `isMaintained`, `latest{name,date,link}` and `custom` (for example `pep`). Sample: Python 3.15 released 2026-10-09, `eolFrom` 2031-10-31, latest 3.15.2. Headers: `access-control-allow-origin: *`, `cache-control: public,max-age=0,must-revalidate`, ETag, served by Netlify — live probe of [endoflife.date/api/v1/products/python](https://endoflife.date/api/v1/products/python)
- The legacy `GET /api/python.json` still returns the older shape (`cycle`, `releaseDate`, `eol`, `latest`, `support`, `lts`) — live probe of [endoflife.date/api/python.json](https://endoflife.date/api/python.json)

### Inferences
- Untangle question: "this runtime reaches end of life next month." Sources include `engines.node` in package.json, `requires-python` / `.python-version`, the `go` directive in go.mod, `rust-version`, Dockerfile `FROM` images, GitHub Actions `setup-*` versions, and Vercel or runtime config. Match each to a product (nodejs, python, go, rust, ubuntu, postgresql, django, react, spring-boot, …) and compute `eolFrom - now`.
- The whole product catalog is small. Fetch `/products/full` once a day in the worker with `If-None-Match`, store cycles as `(:Runtime)-[:HAS_CYCLE]->(:LifecycleCycle)` nodes, and compute "EOL within 30 days" in Cypher. No per-request network calls are needed on Vercel.
- The purl identifiers make endoflife.date joinable to dependency nodes. For example, frameworks such as django or spring-boot that are tracked as packages can be matched through the `identifiers` endpoint.

### Gaps
- No rate limit is documented. I did not check whether the legacy API has a formal deprecation date or when v1 was first released.
- I did not compare other runtime EOL sources (for example python.org devguide JSON or the Node.js release schedule JSON).

## Project health: OpenSSF Scorecard API, bus factor and maintenance signals, Software Heritage

### Takeaway
The OpenSSF Scorecard REST API (`api.scorecard.dev`) returns precomputed weekly check scores, including Maintained, Vulnerabilities and Contributors, under CDLA-Permissive-2.0, and it is also embedded in deps.dev GetProject. Software Heritage gives provenance and a dead-repo fallback, but its anonymous limit is 120 requests/hour, so it belongs in the worker.

### Cited Findings
- `GET https://api.scorecard.dev/projects/github.com/lodash/lodash` returned `date` 2026-11-17, `score` 6.6, Scorecard `v5.5.0`, and checks with scores: Dependency-Update-Tool 10, Security-Policy 10, Code-Review 7, Binary-Artifacts 10, Dangerous-Workflow 10, Token-Permissions 0, Pinned-Dependencies 4, Maintained 3, Packaging -1, CII-Best-Practices 0, SAST 9, License 9, Vulnerabilities 0, Signed-Releases -1, Fuzzing 10, Branch-Protection -1, CI-Tests 8, Contributors 10. Headers showed `cache-control: max-age=600` and a CDN hit, with no auth — live probe of [api.scorecard.dev](https://api.scorecard.dev/projects/github.com/lodash/lodash)
- "Data provided by the REST API is licensed under the CDLA Permissive 2.0." Scores come from a weekly scan that omits CI-Tests and some other checks, and a BigQuery public dataset is also available — [OpenSSF Scorecard README](https://raw.githubusercontent.com/ossf/scorecard/main/README.md)
- deps.dev GetProject embeds a Scorecard result; for lodash the run was dated 2026-08-24 and the version was v5.5.1-…. It also embeds `ossFuzz` and `openIssuesCount` — live probe of [deps.dev GetProject](https://api.deps.dev/v3/projects/github.com%2Flodash%2Flodash)
- ecosyste.ms package records include `repo_metadata`, `issue_metadata`, `maintainers` and `rankings`, which support maintenance and bus-factor heuristics — live probe of [packages.ecosyste.ms](https://packages.ecosyste.ms/api/v1/registries/npmjs.org/packages/lodash)
- Software Heritage: `GET https://archive.softwareheritage.org/api/1/origin/{url}/get/` returned `visit_types` and links to `origin_visits_url` and metadata authorities, with `X-Ratelimit-Limit: 120` and `X-Ratelimit-Remaining: 119` for an anonymous client — live probe of [SWH origin API](https://archive.softwareheritage.org/api/1/origin/https://github.com/lodash/lodash/get/). Authenticated clients reportedly get 1,200 requests/hour using a bearer token from the SWH auth service, but only one mirror of the API page gave that figure — [mirror of SWH API page](https://kelaenderkoe.pages.dev/Using-https-archive.softwareheritage.org/api); the throttling module is documented at [swh.web.api.throttling](https://docs.softwareheritage.org/devel/apidoc/swh.web.api.throttling.html)

### Inferences
- Untangle questions: "Is this dependency still maintained?" (Scorecard Maintained, latest release date from deps.dev or ecosyste.ms, archived flag); "Is this a single-maintainer risk?" (Scorecard Contributors, ecosyste.ms `maintainers` count, npm or PyPI maintainers or ownership); "Can we trust its releases?" (Signed-Releases, deps.dev `slsaProvenances`/`attestations`, PyPI `provenance`, crates.io `trustpub_data`).
- Prefer the Scorecard embedded in deps.dev, which comes with the same call already made for package metadata. Call `api.scorecard.dev` directly only when fresher data is needed, since the deps.dev copy was about three months older than the direct API copy.
- Software Heritage answers "the upstream repo the workaround pointed to has been deleted or moved". If the origin exists in SWH, link the archived snapshot (SWHID) as durable provenance.

### Gaps
- I did not verify the Software Heritage authenticated limit (1,200/hour) on an official page, nor the "Save Code Now" endpoint path and its limits.
- I could not confirm the update cadence of Scorecard API data beyond "weekly scan", nor the API's own rate limits.
- I found no standard bus-factor API. CHAOSS and Augur metrics were not researched this session.

## Community knowledge: Stack Exchange API v2.3, Hacker News Algolia API, Reddit API, dev.to

### Takeaway
Stack Exchange is usable (300 requests/day without a key, 10,000/day with a free key, CC BY-SA with attribution required) and is the most valuable community source for "why is this workaround here". HN Algolia is free and needs no key, with a limit of 10,000 requests/hour per IP. Reddit should be excluded: self-service API access closed in November 2025, and anonymous `.json` returned 403. dev.to is open but low-signal, and its limits are undocumented.

### Cited Findings
- **Stack Exchange quotas:** keyless or token-less apps share an IP-based quota. With a key the default daily limit is 10,000. A user/app pair with an `access_token` gets its own 10,000/day quota, and a user can hold up to 5 distinct quotas. More than 30 requests/second from one IP drops new requests, with bans "on the order of 30 seconds to a few minutes". The `backoff` field must be honored, and any method may return it — [Stack Exchange API throttle docs](https://api.stackexchange.com/docs/throttle)
- With no key, the probe of `GET https://api.stackexchange.com/2.3/info?site=stackoverflow` returned `quota_max: 300`, `quota_remaining: 299` and `api_revision 2026.11.17.47760` — live probe of [api.stackexchange.com/2.3/info](https://api.stackexchange.com/2.3/info?site=stackoverflow)
- **Stack Exchange licensing:** content before 2011-04-08 is CC BY-SA 2.5, content from 2011-04-08 up to 2018-05-02 is CC BY-SA 3.0, and content from 2018-05-02 on is CC BY-SA 4.0 — [Stack Overflow licensing help](https://stackoverflow.com/help/licensing)
- **Stack Exchange AI and data restrictions:** in 2024 Stack Exchange restricted data-dump access, and downloaders must agree the file is "for projects that do not include training a large language model". Stack Overflow sells a paid API or data licence for LLM training, and contributors dispute whether these terms conflict with CC BY-SA — [heise](https://heise.de/-9823083); [DevClass, 2024-07-30](https://www.devclass.com/development/2024/07/30/stack-exchange-restricts-access-to-dump-of-user-contributed-data-critics-complain-this-contradicts-license/1625192); [Stack Overflow blog 2024-09-30](https://stackoverflow.blog/2024/09/30/ongoing-community-data-protection/); [The Register 2024-03-01](https://www.theregister.com/2024/03/01/stack_overflow_launches_api_to/)
- **HN Algolia:** "We are limiting the number of API requests from a single IP to 10,000 per hour" — [HN Search API](https://hn.algolia.com/api) (via search snippet). `GET https://hn.algolia.com/api/v1/search?query=lodash&tags=story&hitsPerPage=1` returned hits with no auth and CORS `*` — live probe of [hn.algolia.com/api/v1/search](https://hn.algolia.com/api/v1/search?query=lodash&tags=story&hitsPerPage=1). A wrapper's docs say requests return at most 1,000 hits — [hacker-news-api README](https://app.unpkg.com/hacker-news-api@2.0.0/files/README.md)
- **Reddit:** the "Responsible Builder Policy", announced on r/redditdev on **11 November 2025**, closed self-service access to the public Data API. Developers, researchers and moderators must now request approval, existing access is unaffected, and users report repeated denials — [r/redditdev thread (mirror)](https://r.datuan.dev/r/redditdev/s/gquSJqMgrM). Third-party guides cite a free tier of 100 queries/minute per OAuth client ID, averaged over 10 minutes, and say non-OAuth traffic is blocked — [Activepieces guide](https://www.activepieces.com/blog/reddit-api-access-in-2026-how-to-get-started); [data365](https://data365.co/blog/reddit-api-limits). An unauthenticated `GET https://www.reddit.com/r/python/search.json` returned **HTTP 403** — live probe of [reddit search.json](https://www.reddit.com/r/python/search.json?q=lodash&limit=1). A Medium post claims `.json` endpoints began returning 403 on 30 May 2026, which I could not verify officially — [Medium](https://medium.com/@alex_79882/reddits-api-is-officially-dead-in-2026-here-s-what-i-use-instead-f88ee5b809c8)
- **dev.to (Forem):** `GET https://dev.to/api/articles?tag=python&per_page=1` answered without auth (CORS `*`) — live probe of [dev.to/api/articles](https://dev.to/api/articles?tag=python&per_page=1). The Forem v1 docs say endpoints are accessed with an `api-key` header and an `accept` header — [Forem API v1](https://developers.forem.com/api/v1)

### Inferences
- Stack Exchange use: look up `/2.3/search/advanced?site=stackoverflow&q=…&tagged=…` for error strings or config keys that appear next to workarounds, and `/2.3/questions/{ids}` when a code comment links a Stack Overflow URL. Store links, title, score, accepted state and author with attribution, not full post bodies. That keeps CC BY-SA attribution simple and avoids any appearance of building an LLM corpus. Send generated summaries to the model only transiently, at answer time.
- Because keyless Stack Exchange quota is shared per IP, and Vercel functions egress from shared cloud IPs, keyless calls from Vercel could hit a quota other tenants have used up. Register a free key and keep it server-side only. A Stack Exchange key is not a secret in their model, but it should still not ship in browser code, per Untangle's policy.
- HN gives cheap "was this library or breakage discussed publicly?" signals, for example `search?query="pkg 2.3.1"&tags=story,comment&numericFilters=created_at_i>…`. It is better suited to background enrichment than to request paths.
- Reddit: drop it from the plan. Access requires approval, the free tier is non-commercial, and unauthenticated access is blocked.

### Gaps
- I did not fetch Stack Exchange's exact attribution requirements (the format for linking the post and author) or the current API Terms of Use and Acceptable Use Policy text.
- I could not find the official Reddit Data API wiki text or the free-tier eligibility details, or confirm a reported 31 October 2026 cutoff.
- I could not find dev.to rate limits or a content license.
- I did not verify the official HN Firebase API (`hacker-news.firebaseio.com/v0`) this session.

## Standards and specs: IETF datatracker/RFC Editor, W3C API, MDN browser-compat-data, caniuse, Web Platform Status, CWE/CAPEC

### Takeaway
All of these are free and need no key, and most are best consumed as bulk data rather than per-request calls. Use RFC Editor JSON and datatracker for RFC status and obsolescence, the W3C API for spec maturity, webstatus.dev and web-features for Baseline status (better than raw BCD for "is this polyfill or workaround still needed"), BCD (CC0) and caniuse (CC BY 4.0) for detail, and the CWE REST API (royalty-free, with MITRE's copyright notice required) to label advisory weaknesses.

### Cited Findings
- **IETF datatracker:** an autogenerated, read-only Tastypie API at `https://datatracker.ietf.org/api/v1`, with JSON and XML output. Example: `/api/v1/doc/document/?name=draft-…`, filterable by state (for example `states__type__slug__in=draft-rfceditor`) — [Datatracker API docs](https://datatracker.ietf.org/api/). `GET /api/v1/doc/document/?name=rfc9110&format=json` returned the document with `cache-control: max-age=300` — live probe of [datatracker doc API](https://datatracker.ietf.org/api/v1/doc/document/?name=rfc9110&format=json)
- **RFC Editor:** `GET https://www.rfc-editor.org/rfc/rfc9110.json` returned `doc_id`, `title`, `authors`, `pub_status: "INTERNET STANDARD"`, `status`, `draft` and `abstract`, with CORS `*` — live probe of [rfc-editor.org/rfc/rfc9110.json](https://www.rfc-editor.org/rfc/rfc9110.json)
- **W3C API:** `GET https://api.w3.org/specifications?items=1` answered without a key (HAL+JSON, 1,721 specifications, `s-maxage=900`) — live probe of [api.w3.org/specifications](https://api.w3.org/specifications?items=1)
- **Web Platform Status:** `GET https://api.webstatus.dev/v1/features?q=name:grid` returned `baseline.status: "widely"`, `low_date: 2023-09-15`, `high_date: 2026-03-15` and per-browser `browser_implementations` with versions — live probe of [api.webstatus.dev](https://api.webstatus.dev/v1/features?q=name:grid&page_size=1). The `web-features` npm package bundles feature identifiers with Baseline statuses and cross-references to specs and caniuse — [web-features README](https://raw.githubusercontent.com/web-platform-dx/web-features/main/README.md)
- **MDN browser-compat-data** is licensed CC0 1.0 Universal — [BCD LICENSE](https://raw.githubusercontent.com/mdn/browser-compat-data/main/LICENSE). **caniuse** data is licensed CC BY 4.0 — [caniuse LICENSE](https://raw.githubusercontent.com/Fyrd/caniuse/main/LICENSE)
- **CWE:** `GET https://cwe-api.mitre.org/api/v1/cwe/weakness/79` returned the full weakness record (about 58 KB, 3.8 s) without a key — live probe of [cwe-api.mitre.org](https://cwe-api.mitre.org/api/v1/cwe/weakness/79). Terms: MITRE grants "a non-exclusive, royalty-free license to use CWE for research, development, and commercial purposes", on condition that copies "reproduce MITRE's copyright designation and this license". CWE is sponsored by CISA — [CWE Terms of Use](https://cwe.mitre.org/about/termsofuse.html). The REST API working group is at [CWE-CAPEC/REST-API-wg](https://raw.githubusercontent.com/CWE-CAPEC/REST-API-wg/main/README.md)
- OSV and GHSA records already carry CWE IDs (for example `CWE-1321`, `CWE-770`) — live probe of [api.osv.dev/v1/vulns/GHSA-p6mc-m468-83gw](https://api.osv.dev/v1/vulns/GHSA-p6mc-m468-83gw)

### Inferences
- Untangle questions:
  - "This polyfill or CSS fallback exists for browser X; is it still needed?" Answer with webstatus.dev Baseline `widely`/`newly` plus dates, or BCD per-browser versions compared against the repo's browserslist.
  - "This config follows RFC N; has it been obsoleted?" Answer with RFC Editor JSON and datatracker relationships.
  - "What class of weakness does this advisory represent?" Answer with CWE name and abstraction from the CWE API, cached forever per CWE ID.
- BCD and web-features ship as npm packages, so the worker can download them once per release instead of calling an API, which is cheaper and avoids rate limits. Caniuse's CC BY 4.0 requires attribution wherever its data is displayed.
- CWE records rarely change, so cache them indefinitely and display the MITRE notice wherever CWE descriptions appear.

### Gaps
- I did not verify RFC Editor JSON fields for obsoletion (I believe they are `obsoleted_by` / `updated_by`), nor the license (BCP 78/IETF Trust) obligations for showing RFC text.
- I did not check W3C API terms, or rate limits for webstatus.dev or the CWE API.
- I did not research a CAPEC API or downloads (I believe XML and CSV downloads exist on capec.mitre.org).

## Link rot: Wayback Machine availability API (plus CDX)

### Takeaway
For every external URL cited in commits or comments, `https://archive.org/wayback/available?url=…&timestamp=YYYYMMDD` gives the closest snapshot near the commit date, needs no key, and is cacheable for 6 hours. The CDX server supports richer queries. Neither documents a rate limit, so throttle politely and run these checks in the worker.

### Cited Findings
- Availability API: `http://archive.org/wayback/available?url=example.com[&timestamp=YYYYMMDDhhmmss][&callback=]`. It returns `archived_snapshots.closest{available,url,timestamp,status}` and an empty object when nothing is archived. The timestamp takes 1–14 digits, and the closest capture to it is returned — [Wayback API help](https://archive.org/help/wayback_api.php)
- The probe returned the closest snapshot `20261120225617`, with `Cache-Control: max-age=21600` and CORS `*` — live probe of [archive.org/wayback/available](https://archive.org/wayback/available?url=example.com)
- CDX: `https://web.archive.org/cdx/search/cdx?url=…&output=json&limit=…` returns `[urlkey, timestamp, original, mimetype, statuscode, digest, length]` rows. It sent no rate-limit headers, only internal `x-rl`/`x-na` diagnostics — live probe of [web.archive.org/cdx](https://web.archive.org/cdx/search/cdx?url=example.com&limit=2&output=json); CDX docs are referenced as "Wayback CDX Server @ GitHub" — [Wayback API help](https://archive.org/help/wayback_api.php)

### Inferences
- Use it to label a cited link as live (HEAD 200), dead with an archived snapshot (use the snapshot nearest the commit timestamp as evidence), or dead and unarchived. Combine with Software Heritage for repository URLs.
- Because the API documents no limits and the Internet Archive is a non-profit with a history of outages, run checks only in the worker, cache results on the `ExternalLink` node, and re-check rarely (for example monthly).

### Gaps
- I found no official Wayback or CDX rate limit, and I did not research the Save Page Now (SPN2) API, which I believe needs archive.org S3-style keys, or its limits.
- I did not research the reliability history (for example the October 2024 outage) this session.

## Cross-cutting: auth, rate limits, licensing, caching and serverless safety (catalog summary)

### Takeaway
Nearly every source that matters is free and keyless, but many limits are per IP. Shared Vercel egress makes those risky, and the Vercel request budget is short. The robust design: the GitHub Actions worker does all bulk and paged fetching, with a `GITHUB_TOKEN`, a Stack Exchange key, and optionally an NVD key held as Actions secrets. It writes normalized evidence nodes, ETags and fetch timestamps into Neo4j Aura. Vercel only reads the graph, plus at most one or two single-item calls to unthrottled, CDN-cached APIs (OSV `query`, deps.dev GetVersion, endoflife.date product) for on-demand freshness.

### Cited Findings (catalog; all figures from the sections above)

Serverless-safe means "OK to call synchronously from a Vercel function"; Untangle-specific notes are in parentheses.

| Source | Endpoint | Auth | Limits | License / terms | Caching | Serverless-safe? |
|---|---|---|---|---|---|---|
| OSV.dev ([docs](https://google.github.io/osv.dev/api/)) | `api.osv.dev/v1/query`, `/querybatch`, `/vulns/{id}`; GCS `gs://osv-vulnerabilities` | None | "No limits"; batch pages past 1,000 per query / 3,000 total | Not verified (gap) | Diff by `modified`; `modified_id.csv` | Yes (single query); batches in worker |
| GHSA REST ([limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)) | `api.github.com/advisories?ecosystem=&affects=` | Optional; GraphQL needs a token | 60/h anonymous per IP; 5,000/h PAT; 1,000/h/repo `GITHUB_TOKEN` | Not verified (gap) | `max-age=60`, ETag | Risky without a token (60/h per shared IP) |
| NVD 2.0 ([start here](https://nvd.nist.gov/developers/start-here)) | `services.nvd.nist.gov/rest/json/cves/2.0` | Key in header (optional) | 5 / 30 s without key; 50 / 30 s with key | NVD notice (not fetched) | Poll by `lastModStartDate` | No (worker only) |
| CISA KEV ([catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)) | `cisa.gov/.../known_exploited_vulnerabilities.json` | None | One file (~1.9 MB) | Not verified (gap) | `Last-Modified`/ETag, `max-age≈1500` | Worker daily |
| EPSS ([API](https://api.first.org/epss)) | `api.first.org/data/v1/epss`; daily CSV at epss.empiricalsecurity.com | None | Undocumented; `cve` param ≤ 2,000 chars | "All Rights Reserved" page (terms gap) | `max-age=86400` | Worker daily (bulk CSV) |
| deps.dev ([v3](https://docs.deps.dev/api/v3/), [v3alpha](https://docs.deps.dev/api/v3alpha/)) | `api.deps.dev/v3/...`, `/v3alpha/versionbatch` etc. | None | Undocumented; batch ≤ 5,000 | Google API ToS; CC-BY 4.0; caching permitted | `max-age=3600` | Yes |
| ecosyste.ms ([pricing](https://ecosyste.ms/pricing)) | `packages.ecosyste.ms/api/v1/registries/{reg}/packages/{name}` | Optional key / polite email | 300 / 1,000 / 5,000 per hour tiers (probe saw 15,000) | Not verified (gap) | `max-age=86400` | Worker preferred |
| Libraries.io ([API](https://libraries.io/api)) | `libraries.io/api/{platform}/{name}` | `api_key` per docs | 60/min with key (probe: 10 anonymous) | Not verified | — | Worker only |
| npm ([registry docs](https://raw.githubusercontent.com/npm/registry/main/docs/REGISTRY-API.md)) | `registry.npmjs.org/{pkg}` (corgi Accept header) | None | Undocumented | npm ToS (not fetched) | `max-age=300`, ETag | Yes, modestly |
| PyPI ([API](https://docs.pypi.org/api/)) | `/pypi/{p}/json`, `/simple/{p}/` (JSON) | None | "No rate limiting at the edge"; unique UA | PyPI terms (not fetched) | `max-age=900/600`, X-Cache | Yes |
| crates.io ([RFC 3463](https://rust-lang.github.io/rfcs/3463-crates-io-policy-update.html)) | `crates.io/api/v1/crates/{name}` | None; identifying UA mandatory (empty UA → 403) | 1 request/s | crates.io policies | Use sparse index / dumps | Worker only (1 rps) |
| Go proxy ([proxy.golang.org](https://proxy.golang.org/)) | `proxy.golang.org/{mod}/@v/list`, `@latest`, `.info`, `.mod`; `index.golang.org` | None | Undocumented | Google privacy policy | `max-age=60` | Yes |
| pkg.go.dev API ([blog](https://go.dev/blog/pkgsite-api)) | `pkg.go.dev/v1beta/{package,module,versions,vulns,imported-by,...}` | Not stated | Not stated | Not stated | "Built for caching" | Probably; beta |
| Maven Central ([429 FAQ](https://central.sonatype.org/faq/429-error/)) | `repo1.maven.org/maven2/.../maven-metadata.xml`; `search.maven.org/solrsearch/select` | None | Org/network consumption limits; blocks up to 30 days | Central Terms (consumption tiers) | ETag / Last-Modified | Avoid; prefer deps.dev |
| GitHub Releases / compare / issues ([search limits](https://docs.github.com/en/rest/search/search)) | `/repos/{o}/{r}/releases/tags/{t}`, `/compare/{a}...{b}`, `/issues/{n}`, `/issues/{n}/timeline` | Token recommended | Core as above; search 30/min (10 anonymous; 10 semantic) | GitHub ToS | ETag | Worker (token) |
| endoflife.date ([OpenAPI](https://endoflife.date/docs/api/v1/openapi.yml)) | `endoflife.date/api/v1/products/{p}` | None | Undocumented | MIT | ETag, must-revalidate | Yes |
| OpenSSF Scorecard ([README](https://raw.githubusercontent.com/ossf/scorecard/main/README.md)) | `api.scorecard.dev/projects/github.com/{o}/{r}` | None | Undocumented | CDLA-Permissive-2.0 | `max-age=600`, CDN | Yes |
| Software Heritage ([API](https://archive.softwareheritage.org/api/1/origin/https://github.com/lodash/lodash/get/)) | `archive.softwareheritage.org/api/1/origin/{url}/get/` | Optional bearer token | 120/h anonymous; ~1,200/h authenticated (unverified) | SWH terms (not fetched) | — | Worker only |
| Stack Exchange ([throttle](https://api.stackexchange.com/docs/throttle)) | `api.stackexchange.com/2.3/...` | Key recommended | 300/day keyless (shared per IP); 10,000/day with key; ≤30 req/s per IP; honor `backoff` | CC BY-SA 2.5/3.0/4.0 by date; AI-training restrictions | — | Worker only |
| HN Algolia ([API](https://hn.algolia.com/api)) | `hn.algolia.com/api/v1/search`, `/search_by_date` | None | 10,000/h per IP | Not verified | — | Worker preferred |
| Reddit | `oauth.reddit.com` | Approval required since 2025-11-11 | 100 QPM/client (third-party) | Responsible Builder Policy | — | Exclude |
| dev.to ([Forem v1](https://developers.forem.com/api/v1)) | `dev.to/api/articles?tag=` | Optional `api-key` | Undocumented | Not verified | — | Low value |
| IETF / RFC Editor ([datatracker](https://datatracker.ietf.org/api/)) | `datatracker.ietf.org/api/v1/doc/document/`; `rfc-editor.org/rfc/rfcN.json` | None | Undocumented | IETF Trust (not fetched) | `max-age=300` | Yes |
| W3C / webstatus.dev / BCD / caniuse | `api.w3.org/specifications`; `api.webstatus.dev/v1/features`; npm `@mdn/browser-compat-data`, `web-features` | None | Undocumented | BCD CC0; caniuse CC BY 4.0 | `s-maxage=900` (W3C) | Use bulk packages in worker |
| CWE ([ToU](https://cwe.mitre.org/about/termsofuse.html)) | `cwe-api.mitre.org/api/v1/cwe/weakness/{id}` | None | Undocumented | Royalty-free; reproduce MITRE notice | Cache forever | Worker (slow: 3.8 s) |
| Wayback ([help](https://archive.org/help/wayback_api.php)) | `archive.org/wayback/available?url=&timestamp=`; `web.archive.org/cdx/search/cdx` | None | Undocumented | Internet Archive terms (not fetched) | `max-age=21600` | Worker only |

Untangle question answered by each source:
- OSV: "this version has CVE-Y; fixed in Z".
- GHSA: "first patched version; EPSS".
- NVD: CVSS/CPE detail.
- CISA KEV: "exploited in the wild; federal due date".
- EPSS: "probability of exploitation".
- deps.dev: "deprecated? license? source repo? advisories? Scorecard? dependents?".
- ecosyste.ms: "status, maintainers, dependents".
- Libraries.io: deprecation and repository status (fallback).
- npm: the deprecation message, often with an issue URL.
- PyPI: "yanked + reason; project status (PEP 792); vulns".
- crates.io: "yanked + yank_message; MSRV".
- Go proxy: "version → exact tag and commit"; "new versions since the pin".
- pkg.go.dev API: "importers; vulns; versions".
- Maven Central: "latest release; versions".
- GitHub Releases, compare and issues: "upstream issue closed? fix commit included in tag? release notes".
- endoflife.date: "runtime/framework EOL date; LTS; latest patch".
- OpenSSF Scorecard: "maintained? signed releases? contributors?".
- Software Heritage: "archived copy of a deleted repo (provenance)".
- Stack Exchange: "known problem/workaround discussions".
- HN Algolia: "public discussion of breakage or releases".
- Reddit: no longer usable for Untangle.
- dev.to: tutorials and posts (low value).
- IETF / RFC Editor: "RFC status, obsoleted?".
- W3C, webstatus.dev, BCD, caniuse: "polyfill still needed? Baseline status".
- CWE: "weakness class names for advisories".
- Wayback: "dead link → archived snapshot near the commit date".

Further findings:
- `GITHUB_TOKEN` in Actions gets 1,000 requests/hour per repository, and GitHub App installation tokens start at 5,000/hour, rising to a maximum of 12,500 — [GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- PyPI asks consumers to "Set your consumer's User-Agent header to uniquely identify your requests" — [PyPI API docs](https://docs.pypi.org/api/). crates.io requires an identifying UA — [RFC 3463](https://rust-lang.github.io/rfcs/3463-crates-io-policy-update.html). Sonatype asks for a clear tool-specific UA — [Sonatype tooling-provider FAQ](https://central.sonatype.org/faq/429-tooling-provider/). ecosyste.ms's polite pool requires a contact email — [ecosyste.ms pricing](https://ecosyste.ms/pricing)

### Inferences
- **Per-IP limits on shared egress:** many sources key limits on IP: GitHub anonymous (60/h), Stack Exchange keyless (shared quota), HN (10,000/h), Software Heritage anonymous (120/h), and Maven Central (network-level). Vercel functions egress from shared cloud ranges, so other tenants may already have used the budget. Treat any per-IP-limited source as worker-only, or call it with a credential that carries its own quota. The Vercel shared-egress claim is my inference; I did not research Vercel's egress model this session.
- **Neo4j Aura Free without APOC:** there is no `apoc.load.json` or `apoc.periodic.iterate`, so all HTTP fetching and normalization must happen in Python (worker or FastAPI). Writes should use plain Cypher `UNWIND $rows AS row MERGE …` batches. Suggested node and relationship types: `(:Advisory {id, modified, fixed_versions})`, `(:Dependency)-[:AFFECTED_BY]->(:Advisory)`, `(:Advisory)-[:HAS_CWE]->(:Weakness)`, `(:Runtime)-[:HAS_CYCLE]->(:LifecycleCycle)`, `(:Decision)-[:CITES]->(:ExternalIssue {state, state_reason, etag, checked_at})`, `(:ExternalLink {url, archived_url})`. Store `source`, `fetched_at`, `license` and `etag` on each evidence node so the UI can show attribution (CC BY-SA, CC BY 4.0, CDLA, MITRE notice) and refresh conditionally.
- **Suggested freshness cadence for the worker:**
  - OSV, KEV and EPSS: daily, plus an on-demand OSV `query` when a user opens a dependency.
  - deps.dev: daily for direct dependencies.
  - Issue state: daily for open workaround Decisions.
  - endoflife.date: daily via ETag.
  - Scorecard: weekly, matching its scan cadence.
  - Stack Exchange and HN: on Decision creation, then monthly.
  - Wayback and SWH: monthly.
- **Primary-source choices, cost-first:** for vulnerabilities, OSV, then KEV, then EPSS, with NVD only as an exception. For package metadata, deps.dev, then the native registry for yank or deprecation text. For lifecycle, endoflife.date. For health, Scorecard via deps.dev. For community, Stack Exchange with a key, then HN. Everything here can run without paid services. The only credentials needed are the Actions `GITHUB_TOKEN` (already present), a free Stack Exchange key, and optionally an NVD key.

### Gaps
- I did not research Vercel function duration limits or egress IP behavior, and did not fetch Vercel docs.
- I did not fetch terms of service for npm, PyPI, GitHub (for API data reuse), Software Heritage, Internet Archive, the IETF Trust or HN Algolia, so their attribution and reuse obligations are not verified.
- Several APIs publish no rate limits: deps.dev, the npm registry, the Go proxy, endoflife.date, Scorecard, CWE, webstatus.dev, Wayback, dev.to and EPSS. Their numbers are unknown, not unlimited, except OSV, which states "no limits".
- I did not collect engineering write-ups from Socket, Snyk or Dependabot on how they combine these sources; only Renovate's changelog docs were reviewed.
