// 10_upsert_identities: Identity nodes (email / login / speaker) pointing at their Person. When a later run learns
// that an email belongs to a login, the identity is re-pointed: the old IDENTITY_OF edge is deleted first.
// Params: $rows = [{id, kind, value, person_id}].
UNWIND $rows AS r
MATCH (p:Person {id: r.person_id})
MERGE (i:Identity {id: r.id})
SET i.kind = r.kind, i.value = r.value
WITH i, p
OPTIONAL MATCH (i)-[old:IDENTITY_OF]->(other:Person) WHERE other.id <> p.id
DELETE old
MERGE (i)-[:IDENTITY_OF]->(p)
RETURN count(*) AS n
