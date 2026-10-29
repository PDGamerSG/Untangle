// 21_record_decision: record decisions idempotently and apply key-based supersession in ONE statement
// (Helium's 11_ingest_fact + 12_supersede_fact folded together, so two writers cannot leave two active values).
// Params: $rows = [{id, repo, kind, key, subject, predicate, object, text, rationale, valid_from, confidence, signal,
//                   created_at}], $now (epoch ms).
// For each row: MERGE the decision by id (re-ingest keeps the original created_at and status), then every OTHER
// decision in the same repo with the same key that is still active and became valid no later than this one is
// expired (valid_to = new.valid_from, expired_at = now, status superseded) and linked with SUPERSEDES.
// A row whose object equals the currently active object for its key is a confirmation: nothing is superseded.
// Returns the new/updated decision ids with the ids they superseded.
// One row per key per call: rows sharing a key inside one $rows batch would see each other's half-written state,
// so callers record same-key rows in chronological rounds (untangle.ingest.loader does; use its helper).
UNWIND $rows AS r
MERGE (d:Decision {id: r.id})
ON CREATE SET d.created_at = coalesce(r.created_at, $now), d.status = 'active'
SET d.repo = r.repo, d.kind = r.kind, d.key = r.key, d.subject = r.subject, d.predicate = r.predicate,
    d.object = r.object, d.text = r.text, d.rationale = r.rationale, d.valid_from = r.valid_from,
    d.confidence = coalesce(r.confidence, 0.8), d.signal = r.signal, d.title = r.text
WITH d, r
OPTIONAL MATCH (old:Decision {repo: r.repo, key: r.key})
WHERE old.id <> d.id AND old.status = 'active' AND old.valid_from <= d.valid_from
  AND coalesce(old.object, '') <> coalesce(d.object, '')
  AND d.status = 'active'
WITH d, r, collect(old) AS olds
FOREACH (old IN olds |
  SET old.valid_to = d.valid_from, old.expired_at = $now, old.status = 'superseded'
  MERGE (d)-[s:SUPERSEDES]->(old)
  SET s.at = $now, s.signal = r.signal
)
WITH d, [o IN olds | o.id] AS superseded
// Late import: a decision older than one already recorded slots in before its immediate successor. Only for a
// decision that is not yet part of a chain; re-recording an existing link must not re-link it to the newest value.
OPTIONAL MATCH (newer:Decision {repo: d.repo, key: d.key})
WHERE newer.id <> d.id AND newer.valid_from > d.valid_from
  AND coalesce(newer.object, '') <> coalesce(d.object, '')
  AND NOT EXISTS { (:Decision)-[:SUPERSEDES]->(d) }
WITH d, superseded, newer
ORDER BY newer.valid_from ASC
WITH d, superseded, collect(newer)[0] AS newer
FOREACH (n IN CASE WHEN newer IS NULL THEN [] ELSE [newer] END |
  SET d.valid_to = n.valid_from, d.expired_at = $now, d.status = 'superseded'
  MERGE (n)-[s2:SUPERSEDES]->(d)
  SET s2.at = $now, s2.signal = 'late_import'
)
RETURN d.id AS id, superseded, d.status AS status
