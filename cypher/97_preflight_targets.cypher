// 97_preflight_targets: the indexed files a proposed change names, with the configuration keys and dependencies
// declared in each, so changed diff lines can be matched to them. Params: $repo, $paths.
UNWIND $paths AS p
MATCH (f:File {repo: $repo, path: p})
CALL (f) {
  OPTIONAL MATCH (k:ConfigKey)-[:SET_IN]->(f)
  RETURN collect(k {.id, .key, .current_value}) AS keys
}
CALL (f) {
  OPTIONAL MATCH (d:Dependency)-[:DECLARED_IN]->(f)
  RETURN collect(d {.id, .name, .ecosystem, .current_version}) AS deps
}
RETURN f.id AS id, f.path AS path, coalesce(f.alive, true) AS alive, keys, deps
