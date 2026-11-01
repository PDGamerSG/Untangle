// Atomically replace only repository-map-owned relationships and feature definitions.
MERGE (repo:Repo {id: $repo_id})
SET repo.full_name = $repo, repo.map_head_sha = $head_sha, repo.map_indexed_at = $indexed_at,
    repo.map_coverage = $coverage, repo.map_warnings = $warnings
WITH repo
CALL (repo) {
  MATCH (f:File {repo: $repo})-[r:IMPORTS]->(:File)
  WHERE r.indexer = 'repository-map-v1'
  DELETE r
}
CALL (repo) {
  MATCH (f:Feature {repo: $repo})
  DETACH DELETE f
}
CALL (repo) {
  UNWIND $features AS row
  CREATE (f:Feature {id: row.id, repo: $repo, name: row.name, description: row.description, source: row.source})
  WITH f, row
  UNWIND row.entrypoints AS path
  MATCH (file:File {repo: $repo, path: path})
  MERGE (f)-[:ENTRYPOINT]->(file)
}
CALL (repo) {
  UNWIND $imports AS row
  MATCH (a:File {repo: $repo, path: row.source}), (b:File {repo: $repo, path: row.target})
  MERGE (a)-[r:IMPORTS {indexer: 'repository-map-v1'}]->(b)
  SET r.line = row.line, r.specifier = row.specifier, r.head_sha = $head_sha
}
RETURN repo.map_head_sha AS head_sha
