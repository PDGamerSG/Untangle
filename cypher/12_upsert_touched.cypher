// 12_upsert_touched: (Commit)-[:TOUCHED {change, additions, deletions}]->(File). additions/deletions are null for
// binary files. Params: $rows = [{commit_id, file_id, change, additions, deletions}].
UNWIND $rows AS r
MATCH (c:Commit {id: r.commit_id})
MATCH (f:File {id: r.file_id})
MERGE (c)-[t:TOUCHED]->(f)
SET t.change = r.change, t.additions = r.additions, t.deletions = r.deletions
RETURN count(*) AS n
