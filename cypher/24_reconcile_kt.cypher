// 24_reconcile_kt: compare what was said in a handover call with what the repository records. Spoken statements live
// on their own keys (`kt|<subject>|<predicate>`) and never supersede code history; instead each spoken config value is
// linked to the repository's active decisions on the same dotted key, in whichever file defines it (a setting can move
// from config.toml.sample into schema.sql): CONFIRMS every live record with the same value; when none agrees,
// CONTRADICTS the live records (or, when the key was only ever removed, the removal).
// Params: $repo, $rows = [{kt_id, code_key, dotted_key, object}], $now. Returns one row per link written.
UNWIND $rows AS r
MATCH (k:Decision {id: r.kt_id})
MATCH (c:Decision {repo: $repo, status: 'active'})
WHERE c.kind <> 'kt' AND c.predicate = 'config_value'
  AND (c.key = r.code_key OR (r.dotted_key IS NOT NULL AND c.subject ENDS WITH ('::' + r.dotted_key)))
WITH k, r, collect(c) AS cs
WITH k, cs,
     [c IN cs WHERE toLower(trim(coalesce(c.object, ''))) = toLower(trim(coalesce(r.object, '')))] AS same,
     [c IN cs WHERE toLower(coalesce(c.object, '')) <> 'removed'] AS live
WITH k, same, CASE WHEN size(same) > 0 THEN [] WHEN size(live) > 0 THEN live ELSE cs END AS differ
FOREACH (c IN same | MERGE (k)-[x:CONFIRMS]->(c) SET x.at = $now)
FOREACH (c IN differ | MERGE (k)-[x:CONTRADICTS]->(c) SET x.at = $now)
WITH k, [c IN same | {id: c.id, relation: 'confirms'}] + [c IN differ | {id: c.id, relation: 'contradicts'}] AS links
UNWIND links AS link
RETURN k.id AS kt_id, link.id AS code_id, link.relation AS relation
