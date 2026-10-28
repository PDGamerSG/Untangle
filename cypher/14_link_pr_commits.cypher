// 14_link_pr_commits: (Commit)-[:PART_OF]->(PullRequest) and the derived (PullRequest)-[:TOUCHED]->(File) edges
// from the commit's TOUCHED files. Params: $rows = [{commit_id, pr_id}].
UNWIND $rows AS r
MATCH (c:Commit {id: r.commit_id})
MATCH (p:PullRequest {id: r.pr_id})
MERGE (c)-[:PART_OF]->(p)
WITH c, p
OPTIONAL MATCH (c)-[:TOUCHED]->(f:File)
FOREACH (_ IN CASE WHEN f IS NULL THEN [] ELSE [1] END | MERGE (p)-[:TOUCHED]->(f))
RETURN count(*) AS n
