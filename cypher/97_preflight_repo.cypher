// 97_preflight_repo: whether a repository is ingested and whether its source import graph is indexed.
// Params: $repo.
MATCH (r:Repo {full_name: $repo})
RETURN r.full_name AS repo, r.head_sha AS head_sha, r.ingested_at AS ingested_at,
       r.map_head_sha IS NOT NULL AS imports_indexed
