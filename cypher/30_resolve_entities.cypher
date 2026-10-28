// 30_resolve_entities: candidate entities (File, Module, Symbol, ConfigKey, Dependency) for a question.
// Params: $repo, $q (Lucene query, e.g. `app^3 OR concurrency^3 OR limit`), $exact (list of raw mentions such as
// paths, dotted keys or identifiers), $limit.
// Full-text hits over `entity_search` are summed with exact-match boosts found through the range indexes
// (File.path, Module.path, ConfigKey.key, Symbol.name, Dependency.name), so `config.toml` or `app.concurrency`
// typed verbatim always ranks first. The router turns the raw Lucene score into a match strength.
CALL () {
  CALL db.index.fulltext.queryNodes('entity_search', $q, {limit: 80}) YIELD node, score
  WHERE node.repo = $repo
  RETURN node, score
  UNION ALL
  UNWIND $exact AS x
  MATCH (node:File {repo: $repo, path: x})
  RETURN node, 100.0 AS score
  UNION ALL
  UNWIND $exact AS x
  MATCH (node:Module {repo: $repo, path: x})
  RETURN node, 100.0 AS score
  UNION ALL
  UNWIND $exact AS x
  MATCH (node:ConfigKey {repo: $repo, key: x})
  RETURN node, 100.0 AS score
  UNION ALL
  UNWIND $exact AS x
  MATCH (node:Symbol {repo: $repo, name: x})
  RETURN node, 100.0 AS score
  UNION ALL
  UNWIND $exact AS x
  MATCH (node:Dependency {repo: $repo, name: x})
  RETURN node, 100.0 AS score
}
WITH node, sum(score) AS score
ORDER BY score DESC
LIMIT $limit
RETURN node.id AS id, labels(node)[0] AS label, coalesce(node.name, node.key, node.path) AS name, node.path AS path,
       node.key AS key, node.kind AS kind, node.ext AS ext, node.tokens AS tokens, node.current_value AS current_value,
       node.current_version AS current_version, node.alive AS alive, node.touch_count AS touch_count,
       node.last_touched_at AS last_touched_at, score
