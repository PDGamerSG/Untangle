// 43_kt_link_utterance_next: chain the utterances of one meeting in seq order with NEXT (re-runnable; MERGE).
// Params: $meeting_id.
MATCH (:Meeting {id: $meeting_id})-[:HAS]->(u:Utterance)
WITH u ORDER BY u.seq
WITH collect(u) AS us
UNWIND range(0, size(us) - 2) AS i
WITH us[i] AS a, us[i + 1] AS b
MERGE (a)-[:NEXT]->(b)
RETURN count(*) AS linked
