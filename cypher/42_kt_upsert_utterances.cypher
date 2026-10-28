// 42_kt_upsert_utterances: Utterance rows of one meeting with HAS from the Meeting and SPOKEN_BY to the speaker's Person.
// Params: $rows = [{id, repo, meeting_id, seq, text, text_en, start_ms, end_ms, speaker_label, speaker_name, language,
//                   person_id}].
UNWIND $rows AS r
MATCH (m:Meeting {id: r.meeting_id})
MERGE (u:Utterance {id: r.id})
SET u.repo = r.repo, u.meeting_id = r.meeting_id, u.seq = r.seq, u.text = r.text, u.text_en = r.text_en,
    u.start_ms = r.start_ms, u.end_ms = r.end_ms, u.speaker_label = r.speaker_label, u.speaker_name = r.speaker_name,
    u.language = r.language
MERGE (m)-[:HAS]->(u)
WITH u, r
OPTIONAL MATCH (p:Person {id: r.person_id})
FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (u)-[:SPOKEN_BY]->(p))
RETURN count(u) AS utterances
