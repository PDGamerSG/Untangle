// 11_upsert_commits: Commit nodes with AUTHORED / COMMITTED from their people (people are loaded first).
// Params: $rows = [{id, repo, sha, title, message, authored_at, committed_at, is_merge, is_revert, reverts_sha, url,
//                   additions, deletions, files_changed, author_id, committer_id}].
UNWIND $rows AS r
MERGE (c:Commit {id: r.id})
SET c.repo = r.repo, c.sha = r.sha, c.title = r.title, c.message = r.message, c.authored_at = r.authored_at,
    c.committed_at = r.committed_at, c.is_merge = r.is_merge, c.is_revert = r.is_revert, c.reverts_sha = r.reverts_sha,
    c.url = r.url, c.additions = r.additions, c.deletions = r.deletions, c.files_changed = r.files_changed
WITH c, r
OPTIONAL MATCH (a:Person {id: r.author_id})
OPTIONAL MATCH (k:Person {id: r.committer_id})
FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (a)-[:AUTHORED]->(c))
FOREACH (_ IN CASE WHEN k IS NULL THEN [] ELSE [1] END | MERGE (k)-[:COMMITTED]->(c))
RETURN count(*) AS n
