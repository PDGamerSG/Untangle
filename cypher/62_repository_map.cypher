MATCH (repo:Repo {full_name: $repo})
CALL (repo) {
  MATCH (f:File {repo: $repo})
  RETURN count(f) AS total_files
}
CALL (repo) {
  MATCH (f:File {repo: $repo})
  WITH f ORDER BY coalesce(f.alive, false) DESC, f.path LIMIT 2000
  RETURN collect(f {.path, .alive}) AS files
}
CALL (repo) {
  MATCH (f:Feature {repo: $repo})
  OPTIONAL MATCH (f)-[:ENTRYPOINT]->(e:File {repo: $repo})
  WITH f, collect(e.path) AS entrypoints ORDER BY f.name
  RETURN collect(f {.id, .name, .description, .source, entrypoints: entrypoints}) AS features
}
CALL (repo) {
  MATCH (a:File {repo: $repo})-[r:IMPORTS]->(b:File {repo: $repo})
  WHERE r.indexer = 'repository-map-v1'
  WITH a, b, r ORDER BY a.path, b.path LIMIT 12000
  RETURN collect({source: a.path, target: b.path, line: r.line, specifier: r.specifier}) AS imports
}
CALL (repo) {
  MATCH (c:Commit {repo: $repo})
  RETURN count(c) AS total_commits
}
CALL (repo) {
  MATCH (c:Commit {repo: $repo})
  WITH c ORDER BY coalesce(c.committed_at, c.authored_at) DESC, c.sha SKIP $offset LIMIT $limit
  OPTIONAL MATCH (p:Person)-[:AUTHORED]->(c)
  WITH c, head(collect(p.name)) AS author
  OPTIONAL MATCH (c)-[t:TOUCHED]->(f:File {repo: $repo})
  WITH c, author, collect(f { .path, change: t.change, additions: t.additions, deletions: t.deletions }) AS files
  ORDER BY coalesce(c.committed_at, c.authored_at) DESC, c.sha
  RETURN collect(c {.sha, .title, .authored_at, .is_merge, .parent_shas, .url, author: author, files: files}) AS commits
}
RETURN repo.map_head_sha AS head_sha, repo.map_indexed_at AS indexed_at, repo.map_coverage AS coverage,
       repo.head_sha AS repository_head_sha, repo.ingested_at AS repository_ingested_at,
       repo.map_warnings AS warnings, files, features, imports, commits, total_commits, total_files
