// 39_repos: every ingested repository with its counts. No params.
// The range predicates on the second property of each composite index (authored_at, number, status) let the
// planner count through the index instead of scanning the label.
MATCH (r:Repo)
RETURN r.id AS id, r.full_name AS full_name, r.url AS url, r.default_branch AS default_branch, r.head_sha AS head_sha,
       r.ingested_at AS ingested_at, r.commit_count AS commit_count, r.languages AS languages,
       COUNT { MATCH (c:Commit) WHERE c.repo = r.full_name AND c.authored_at >= 0 } AS commits,
       COUNT { MATCH (p:PullRequest) WHERE p.repo = r.full_name AND p.number >= 0 } AS prs,
       COUNT { MATCH (i:Issue) WHERE i.repo = r.full_name AND i.number >= 0 } AS issues,
       COUNT { MATCH (d:Decision) WHERE d.repo = r.full_name AND d.status IS NOT NULL } AS decisions,
       COUNT { MATCH (m:Meeting) WHERE m.repo = r.full_name } AS meetings
ORDER BY r.ingested_at DESC
