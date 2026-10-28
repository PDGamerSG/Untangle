// 40_kt_upsert_meeting: MERGE one Meeting and attach it to its Repo. The Repo is created minimally when the repository
// has not been ingested yet, so a handover call can be loaded before (or without) the code history; `kyun ingest`
// MERGEs on the same id and fills in the rest.
// Params: $m = {id, repo, title, started_at, duration_ms, language, source, audio_uri, summary}, $now (epoch ms).
MERGE (repo:Repo {id: 'repo:' + $m.repo})
ON CREATE SET repo.full_name = $m.repo, repo.url = 'https://github.com/' + $m.repo
MERGE (m:Meeting {id: $m.id})
ON CREATE SET m.created_at = $now
SET m.repo = $m.repo, m.title = $m.title, m.started_at = $m.started_at, m.duration_ms = $m.duration_ms,
    m.language = $m.language, m.source = $m.source, m.audio_uri = $m.audio_uri, m.summary = $m.summary,
    m.ingested_at = $now
MERGE (m)-[:ABOUT_REPO]->(repo)
RETURN m.id AS id
