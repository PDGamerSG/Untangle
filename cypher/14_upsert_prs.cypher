// 14_upsert_prs: PullRequest nodes and (Person)-[:OPENED]->(PullRequest).
// Params: $rows = [{id, repo, number, title, body, state, merged, created_at, merged_at, closed_at, url, author_login,
//                   labels, additions, deletions, changed_files, author_id}].
UNWIND $rows AS r
MERGE (p:PullRequest {id: r.id})
SET p.repo = r.repo, p.number = r.number, p.title = r.title, p.body = r.body, p.state = r.state, p.merged = r.merged,
    p.created_at = r.created_at, p.merged_at = r.merged_at, p.closed_at = r.closed_at, p.url = r.url,
    p.author_login = r.author_login, p.labels = r.labels, p.additions = r.additions, p.deletions = r.deletions,
    p.changed_files = r.changed_files
WITH p, r
OPTIONAL MATCH (a:Person {id: r.author_id})
FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (a)-[:OPENED]->(p))
RETURN count(*) AS n
