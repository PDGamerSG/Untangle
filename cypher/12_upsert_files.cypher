// 12_upsert_files: File nodes (every path ever touched plus everything at HEAD) in their Module.
// Params: $rows = [{id, repo, path, name, ext, tokens, is_config, is_doc, alive, first_seen_at, last_touched_at,
//                   touch_count, module_id}].
UNWIND $rows AS r
MERGE (f:File {id: r.id})
SET f.repo = r.repo, f.path = r.path, f.name = r.name, f.ext = r.ext, f.tokens = r.tokens, f.is_config = r.is_config,
    f.is_doc = r.is_doc, f.alive = r.alive, f.first_seen_at = r.first_seen_at, f.last_touched_at = r.last_touched_at,
    f.touch_count = r.touch_count
WITH f, r
MATCH (m:Module {id: r.module_id})
MERGE (f)-[:IN]->(m)
RETURN count(*) AS n
