// 46_kt_meeting_detail: one meeting with its utterances (in order, with speaker and mentioned entities), its speakers and
// the decisions decided in it (with the entities they are about, who stated them and the utterances that evidence
// them). Params: $id.
MATCH (m:Meeting {id: $id})
OPTIONAL MATCH (m)-[:HAS]->(u:Utterance)
OPTIONAL MATCH (u)-[:SPOKEN_BY]->(sp:Person)
OPTIONAL MATCH (u)-[:MENTIONS]->(e)
WITH m, u, sp, collect(DISTINCT {id: e.id, label: head(labels(e)), name: coalesce(e.key, e.name, e.path)}) AS mentions
ORDER BY u.seq
WITH m, collect(CASE WHEN u IS NULL THEN null ELSE {
    id: u.id, seq: u.seq, speaker_label: u.speaker_label, speaker_name: coalesce(sp.name, u.speaker_name),
    person_id: sp.id, start_ms: u.start_ms, end_ms: u.end_ms, text: u.text, text_en: u.text_en, language: u.language,
    mentions: [x IN mentions WHERE x.id IS NOT NULL]
} END) AS utterances
WITH m, [x IN utterances WHERE x IS NOT NULL] AS utterances
OPTIONAL MATCH (m)-[:HAS]->(:Utterance)-[:SPOKEN_BY]->(p:Person)
WITH m, utterances, collect(DISTINCT {id: p.id, name: p.name, login: p.login, kind: p.kind}) AS speakers
OPTIONAL MATCH (d:Decision)-[:DECIDED_IN]->(m)
OPTIONAL MATCH (d)-[:ABOUT]->(a)
OPTIONAL MATCH (d)-[:STATED_BY]->(who:Person)
OPTIONAL MATCH (d)-[:EVIDENCED_BY]->(ev:Utterance)
OPTIONAL MATCH (d)-[:SUPERSEDES]->(older:Decision)
WITH m, utterances, speakers, d, who,
     collect(DISTINCT {id: a.id, label: head(labels(a)), name: coalesce(a.key, a.name, a.path)}) AS about,
     collect(DISTINCT ev.id) AS evidence, collect(DISTINCT older.id) AS supersedes
ORDER BY d.valid_from
WITH m, utterances, speakers, collect(CASE WHEN d IS NULL THEN null ELSE {
    id: d.id, kind: d.kind, key: d.key, subject: d.subject, predicate: d.predicate, object: d.object, text: d.text,
    rationale: d.rationale, status: d.status, valid_from: d.valid_from, valid_to: d.valid_to, confidence: d.confidence,
    signal: d.signal, stated_by: CASE WHEN who IS NULL THEN null ELSE {id: who.id, name: who.name, login: who.login} END,
    about: [x IN about WHERE x.id IS NOT NULL], evidence: [x IN evidence WHERE x IS NOT NULL],
    supersedes: [x IN supersedes WHERE x IS NOT NULL]
} END) AS decisions
RETURN m.id AS id, m.repo AS repo, m.title AS title, m.started_at AS started_at, m.duration_ms AS duration_ms,
       m.language AS language, m.source AS source, m.audio_uri AS audio_uri, m.summary AS summary,
       [x IN speakers WHERE x.id IS NOT NULL] AS speakers, utterances,
       [x IN decisions WHERE x IS NOT NULL] AS decisions
