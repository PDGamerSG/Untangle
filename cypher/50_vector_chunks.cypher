// 50_vector_chunks: nearest chunks to a question embedding for the vector-only baseline.
// Params: $q (float list of EMBED_DIM), $k (candidates asked from the index; larger than $limit because the index
// is not partitioned by repo), $repo, $limit.
CALL db.index.vector.queryNodes('chunk_embedding', $k, $q) YIELD node, score
WHERE node.repo = $repo
RETURN node.id AS id, node.text AS text, node.source_kind AS source_kind, node.source_id AS source_id,
       node.created_at AS created_at, score,
       [(node)-[:FROM]->(s) | {id: s.id, title: coalesce(s.title, s.path), url: s.url, number: s.number}][0] AS source
ORDER BY score DESC
LIMIT $limit
