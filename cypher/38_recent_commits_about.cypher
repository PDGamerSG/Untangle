// 38_recent_commits_about: the most recent commits that touched the entity's file(s), with author and PR.
// Params: $ids (entity ids), $limit. Newest first.
UNWIND $ids AS eid
MATCH (e:File|Module|Symbol|ConfigKey|Dependency {id: eid})
OPTIONAL MATCH (e)-[:DEFINED_IN|SET_IN|DECLARED_IN]->(f1:File)
OPTIONAL MATCH (f2:File)-[:IN]->(e)
WITH collect(DISTINCT f1) + collect(DISTINCT f2) + collect(DISTINCT CASE WHEN e:File THEN e END) AS files
UNWIND files AS f
MATCH (c:Commit)-[t:TOUCHED]->(f)
WITH DISTINCT c, collect(DISTINCT f.path) AS paths, collect(DISTINCT t.change) AS changes
ORDER BY c.authored_at DESC
LIMIT $limit
RETURN c.id AS id, c.sha AS sha, c.title AS title, left(coalesce(c.message, ''), 320) AS excerpt,
       c.authored_at AS authored_at, c.url AS url, c.is_revert AS is_revert, c.is_merge AS is_merge, paths, changes,
       [(p:Person)-[:AUTHORED]->(c) | {id: p.id, name: p.name, login: p.login}][0] AS author,
       [(c)-[:PART_OF]->(pr:PullRequest) | {id: pr.id, number: pr.number, title: pr.title, url: pr.url}][0] AS pr
