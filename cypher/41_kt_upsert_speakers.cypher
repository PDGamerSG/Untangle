// 41_kt_upsert_speakers: one Person per speaker label of a meeting, resolved to an existing contributor when the
// transcript names a GitHub login or an e-mail that the code history already knows (Person.login / Person.email, or
// an Identity of kind login/email). Otherwise a Person of kind `speaker` is created with the fallback id. Every label
// also gets an Identity of kind `speaker` (value `<meeting_id>/<label>`) pointing at the Person, so the voice on the
// call and the commit author become one node.
// Params: $rows = [{label, name, login, login_lc, email, email_lc, fallback_id, identity_id, identity_value, tokens}].
UNWIND $rows AS r
OPTIONAL MATCH (byLogin:Person {login: r.login})
OPTIONAL MATCH (:Identity {kind: 'login', value: r.login_lc})-[:IDENTITY_OF]->(byLoginId:Person)
OPTIONAL MATCH (:Identity {kind: 'email', value: r.email_lc})-[:IDENTITY_OF]->(byEmailId:Person)
OPTIONAL MATCH (byEmail:Person {email: r.email})
WITH r, coalesce(byLogin, byLoginId, byEmailId, byEmail) AS existing
MERGE (p:Person {id: coalesce(existing.id, r.fallback_id)})
ON CREATE SET p.kind = 'speaker', p.name = r.name, p.login = r.login, p.email = r.email, p.tokens = r.tokens
SET p.name = coalesce(p.name, r.name), p.login = coalesce(p.login, r.login), p.email = coalesce(p.email, r.email),
    p.tokens = coalesce(p.tokens, r.tokens), p.kind = coalesce(p.kind, 'speaker')
MERGE (i:Identity {id: r.identity_id})
SET i.kind = 'speaker', i.value = r.identity_value
MERGE (i)-[:IDENTITY_OF]->(p)
RETURN r.label AS label, p.id AS person_id, existing IS NOT NULL AS matched_existing
