// 15_upsert_documents: ADRs, design docs, changelogs and READMEs with (Document)-[:STORED_AS]->(File).
// Params: $rows = [{id, repo, path, title, kind, status, adr_number, date, text, superseded_by_path, file_id}].
UNWIND $rows AS r
MERGE (d:Document {id: r.id})
SET d.repo = r.repo, d.path = r.path, d.title = r.title, d.kind = r.kind, d.status = r.status, d.adr_number = r.adr_number,
    d.date = r.date, d.text = r.text, d.superseded_by_path = r.superseded_by_path
WITH d, r
OPTIONAL MATCH (f:File {id: r.file_id})
FOREACH (_ IN CASE WHEN f IS NULL THEN [] ELSE [1] END | MERGE (d)-[:STORED_AS]->(f))
RETURN count(*) AS n
