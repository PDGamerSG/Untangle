// 44_kt_link_mentions: (Utterance)-[:MENTIONS {term}]->(File|Symbol|ConfigKey|Dependency). Targets must exist (a typo
// in a transcript cannot invent an entity); rows whose target is missing or of another label are skipped.
// Params: $rows = [{utterance_id, entity_id, term}].
UNWIND $rows AS r
MATCH (u:Utterance {id: r.utterance_id})
MATCH (e {id: r.entity_id})
WHERE e:File OR e:Symbol OR e:ConfigKey OR e:Dependency
MERGE (u)-[m:MENTIONS]->(e)
SET m.term = r.term
RETURN count(m) AS linked
