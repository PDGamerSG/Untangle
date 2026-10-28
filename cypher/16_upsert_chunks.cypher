// 16_upsert_chunks: Chunk nodes with (Chunk)-[:FROM]->(source). Embeddings are stored through
// db.create.setNodeVectorProperty (float32) when present; rows without one keep whatever the node had.
// Params: $rows = [{id, repo, text, source_id, source_kind, seq, created_at, embedding}].
UNWIND $rows AS r
MERGE (c:Chunk {id: r.id})
SET c.repo = r.repo, c.text = r.text, c.source_id = r.source_id, c.source_kind = r.source_kind, c.seq = r.seq,
    c.created_at = r.created_at
WITH c, r
OPTIONAL MATCH (s) WHERE (s:PullRequest OR s:Issue OR s:Comment OR s:Commit OR s:Document OR s:Utterance) AND s.id = r.source_id
FOREACH (_ IN CASE WHEN s IS NULL THEN [] ELSE [1] END | MERGE (c)-[:FROM]->(s))
WITH c, r
WHERE r.embedding IS NOT NULL
CALL db.create.setNodeVectorProperty(c, 'embedding', r.embedding)
RETURN count(*) AS n
