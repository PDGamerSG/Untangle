// 49_kt_upsert_utterance_chunks: one Chunk per utterance (source_kind 'utterance') with its embedding, linked FROM the
// utterance so the vector-only baseline can quote handover calls too.
// Params: $rows = [{id, repo, text, source_id, seq, created_at, embedding}].
UNWIND $rows AS r
MATCH (u:Utterance {id: r.source_id})
MERGE (c:Chunk {id: r.id})
SET c.repo = r.repo, c.text = r.text, c.source_id = r.source_id, c.source_kind = 'utterance', c.seq = r.seq,
    c.created_at = r.created_at, c.embedding = r.embedding
MERGE (c)-[:FROM]->(u)
RETURN count(c) AS chunks
