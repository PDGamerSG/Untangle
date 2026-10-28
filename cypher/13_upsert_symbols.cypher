// 13_upsert_symbols: Symbols at HEAD and (Symbol)-[:DEFINED_IN]->(File).
// Params: $rows = [{id, repo, name, kind, path, line, tokens, file_id}].
UNWIND $rows AS r
MATCH (f:File {id: r.file_id})
MERGE (s:Symbol {id: r.id})
SET s.repo = r.repo, s.name = r.name, s.kind = r.kind, s.path = r.path, s.line = r.line, s.tokens = r.tokens
MERGE (s)-[:DEFINED_IN]->(f)
RETURN count(*) AS n
