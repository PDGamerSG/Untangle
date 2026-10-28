// 12_upsert_modules: directory Modules and their parent chain. The loader writes them shallowest first so the
// parent always exists. Params: $rows = [{id, repo, path, name, tokens, parent_id}] (parent_id null for the root `.`).
UNWIND $rows AS r
MERGE (m:Module {id: r.id})
SET m.repo = r.repo, m.path = r.path, m.name = r.name, m.tokens = r.tokens
WITH m, r
OPTIONAL MATCH (parent:Module {id: r.parent_id})
FOREACH (_ IN CASE WHEN parent IS NULL THEN [] ELSE [1] END | MERGE (m)-[:IN]->(parent))
RETURN count(*) AS n
