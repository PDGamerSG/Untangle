// Counts and snapshot identity only. Fetch page collections independently: carrying
// collected arrays through later expansions can exhaust the transaction memory pool.
MATCH (repo:Repo {full_name: $repo})
RETURN repo.map_head_sha AS head_sha, repo.map_indexed_at AS indexed_at, repo.map_coverage AS coverage,
       repo.head_sha AS repository_head_sha, repo.ingested_at AS repository_ingested_at,
       repo.map_warnings AS warnings,
       COUNT { MATCH (:File {repo: $repo}) } AS total_files,
       COUNT { MATCH (:Feature {repo: $repo}) } AS total_features,
       COUNT { MATCH (:File {repo: $repo})-[r:IMPORTS]->(:File {repo: $repo})
               WHERE r.indexer = 'repository-map-v1' } AS total_imports,
       COUNT { MATCH (:Commit {repo: $repo}) } AS total_commits
