// 48_kt_resolve_entities: resolve a spoken or model-produced term ("app concurrency", "the manager package") to the
// repository's entities through the `entity_search` full-text index. The caller sanitises the term to
// `tok1 OR tok2` (kyun.ids.tokens) and applies the precision guard on what comes back.
// Params: $repo, $q (Lucene query), $limit.
CALL db.index.fulltext.queryNodes('entity_search', $q) YIELD node, score
WHERE node.repo = $repo
RETURN node.id AS id, head(labels(node)) AS label, coalesce(node.key, node.name, node.path) AS name,
       node.path AS path, node.key AS key, node.tokens AS tokens, score
ORDER BY score DESC
LIMIT $limit
