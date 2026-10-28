// 47_kt_repo_keyterms: the repository's entities ranked by how often their file was touched, for (a) Sarvam `keyterms`
// (the top names bias speech recognition toward the repo's own vocabulary) and (b) the catalogue that MENTIONS
// matching runs against. Config keys and dependencies get a small bonus: they are what people argue about on calls.
// Params: $repo, $limit.
CALL {
  MATCH (f:File {repo: $repo})
  RETURN f.id AS id, 'File' AS label, f.name AS name, f.path AS path, null AS key, f.tokens AS tokens,
         coalesce(f.touch_count, 0) + CASE WHEN coalesce(f.is_config, false) THEN 3 ELSE 0 END AS score
  UNION ALL
  MATCH (s:Symbol {repo: $repo})
  OPTIONAL MATCH (s)-[:DEFINED_IN]->(f:File)
  RETURN s.id AS id, 'Symbol' AS label, s.name AS name, s.path AS path, null AS key, s.tokens AS tokens,
         coalesce(f.touch_count, 0) * 0.8 AS score
  UNION ALL
  MATCH (c:ConfigKey {repo: $repo})
  OPTIONAL MATCH (c)-[:SET_IN]->(f:File)
  RETURN c.id AS id, 'ConfigKey' AS label, c.key AS name, c.path AS path, c.key AS key, c.tokens AS tokens,
         coalesce(f.touch_count, 0) + 5 AS score
  UNION ALL
  MATCH (d:Dependency {repo: $repo})
  OPTIONAL MATCH (d)-[:DECLARED_IN]->(f:File)
  RETURN d.id AS id, 'Dependency' AS label, d.name AS name, null AS path, null AS key, d.tokens AS tokens,
         coalesce(f.touch_count, 0) + 4 AS score
  UNION ALL
  MATCH (mo:Module {repo: $repo})
  OPTIONAL MATCH (f:File)-[:IN]->(mo)
  WITH mo, sum(coalesce(f.touch_count, 0)) AS touched
  RETURN mo.id AS id, 'Module' AS label, mo.name AS name, mo.path AS path, null AS key, mo.tokens AS tokens,
         touched * 0.5 AS score
}
RETURN id, label, name, path, key, tokens, score
ORDER BY score DESC, label, name
LIMIT $limit
