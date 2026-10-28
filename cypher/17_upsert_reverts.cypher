// 17_upsert_reverts: (Commit)-[:REVERTS]->(Commit) for revert commits whose target is in the ingested history.
// Params: $rows = [{revert_id, reverted_id}].
UNWIND $rows AS r
MATCH (a:Commit {id: r.revert_id})
MATCH (b:Commit {id: r.reverted_id})
MERGE (a)-[:REVERTS]->(b)
RETURN count(*) AS n
