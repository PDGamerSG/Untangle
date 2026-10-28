// 13_upsert_dependencies: Dependencies declared in manifests and (Dependency)-[:DECLARED_IN]->(File).
// Params: $rows = [{id, repo, name, ecosystem, tokens, current_version, file_id}].
UNWIND $rows AS r
MATCH (f:File {id: r.file_id})
MERGE (d:Dependency {id: r.id})
SET d.repo = r.repo, d.name = r.name, d.ecosystem = r.ecosystem, d.tokens = r.tokens, d.current_version = r.current_version
MERGE (d)-[:DECLARED_IN]->(f)
RETURN count(*) AS n
