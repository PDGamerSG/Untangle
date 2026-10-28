// 45_kt_meetings: the handover calls of one repository, newest first, with utterance / speaker / decision counts.
// Params: $repo.
MATCH (m:Meeting {repo: $repo})
OPTIONAL MATCH (m)-[:HAS]->(u:Utterance)
WITH m, count(u) AS utterances, count(DISTINCT u.speaker_label) AS speakers
OPTIONAL MATCH (d:Decision)-[:DECIDED_IN]->(m)
WITH m, utterances, speakers, count(DISTINCT d) AS decisions
RETURN m.id AS id, m.repo AS repo, m.title AS title, m.started_at AS started_at, m.duration_ms AS duration_ms,
       m.language AS language, m.source AS source, m.audio_uri AS audio_uri, m.summary AS summary,
       utterances, speakers, decisions
ORDER BY coalesce(m.started_at, 0) DESC, m.title
