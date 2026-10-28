// 12_upsert_renames: (new File)-[:RENAMED_FROM {at, sha}]->(old File), from git's rename detection (-M).
// Params: $rows = [{new_id, old_id, at, sha}].
UNWIND $rows AS r
MATCH (new:File {id: r.new_id})
MATCH (old:File {id: r.old_id})
MERGE (new)-[x:RENAMED_FROM]->(old)
SET x.at = r.at, x.sha = r.sha
RETURN count(*) AS n
