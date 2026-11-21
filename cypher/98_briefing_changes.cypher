// 98_briefing_changes: the most recent supersessions in a repository: which decision replaced which, and when.
// `at` is when the newer value took effect in the repository. Agent notes are left out. Params: $repo, $limit.
MATCH (n:Decision {repo: $repo})-[s:SUPERSEDES]->(o:Decision)
WHERE n.kind <> 'agent'
WITH n, o, s, coalesce(n.valid_from, s.at) AS at
ORDER BY at DESC, n.id
LIMIT $limit
RETURN n {.id, .kind, .subject, .object, .text, .status, .valid_from} AS newer,
       o {.id, .kind, .subject, .object, .text, .status, .valid_from} AS older, at, s.signal AS signal,
       [(n)-[:DECIDED_IN]->(x) | {id: x.id, labels: labels(x), title: coalesce(x.title, x.path), url: x.url, number: x.number, sha: x.sha}][0] AS source
