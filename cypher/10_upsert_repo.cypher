// 10_upsert_repo: the Repo node, written last by the ingestion pipeline so a half-finished run is visible as such.
// Params: $row = {id, full_name, url, default_branch, head_sha, ingested_at, commit_count, languages}.
MERGE (r:Repo {id: $row.id})
SET r.full_name = $row.full_name, r.repo = $row.full_name, r.url = $row.url, r.default_branch = $row.default_branch,
    r.head_sha = $row.head_sha, r.ingested_at = $row.ingested_at, r.commit_count = $row.commit_count,
    r.languages = $row.languages
RETURN r.id AS id
