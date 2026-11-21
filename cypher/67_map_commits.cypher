MATCH (c:Commit {repo: $repo})
WITH c ORDER BY coalesce(c.committed_at, c.authored_at) DESC, c.sha SKIP $offset LIMIT $limit
OPTIONAL MATCH (p:Person)-[:AUTHORED]->(c)
WITH c, head(collect(p.name)) AS author
OPTIONAL MATCH (c)-[t:TOUCHED]->(f:File {repo: $repo})
WITH c, author, collect(f {.path, change: t.change, additions: t.additions, deletions: t.deletions}) AS files
ORDER BY coalesce(c.committed_at, c.authored_at) DESC, c.sha
RETURN c {.sha, .title, .authored_at, .is_merge, .parent_shas, .url, author: author, files: files} AS commit
