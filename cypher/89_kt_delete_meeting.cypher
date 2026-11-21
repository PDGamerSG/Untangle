// 89_kt_delete_meeting: remove one handover call with its utterances, their search chunks and the spoken decisions
// it produced. Repository code history and people are kept. Params: $meeting_id.
MATCH (m:Meeting {id: $meeting_id})
CALL (m) {
  OPTIONAL MATCH (d:Decision {kind: 'kt'})-[:DECIDED_IN]->(m)
  DETACH DELETE d
  RETURN count(d) AS decisions
}
CALL (m) {
  OPTIONAL MATCH (m)-[:HAS]->(u:Utterance)
  OPTIONAL MATCH (c:Chunk)-[:FROM]->(u)
  DETACH DELETE c, u
  RETURN count(DISTINCT u) AS utterances
}
DETACH DELETE m
RETURN decisions, utterances
