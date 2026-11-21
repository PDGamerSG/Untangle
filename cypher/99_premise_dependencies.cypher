// 99_premise_dependencies: dependencies whose name is one of $names (lower case), or ends with `/<name>` (so `jest`
// finds `@jest/core` and `lib/pq` finds `github.com/lib/pq`), with the manifest that declares them and, for a
// dependency that is no longer declared, when it was removed. Params: $repo, $names.
MATCH (d:Dependency {repo: $repo})
WHERE toLower(d.name) IN $names OR any(n IN $names WHERE toLower(d.name) ENDS WITH '/' + n)
OPTIONAL MATCH (d)-[:DECLARED_IN]->(f:File)
WITH d, collect(f.path)[0] AS path
OPTIONAL MATCH (r:Decision {status: 'active'})-[:ABOUT]->(d)
WHERE toLower(coalesce(r.object, '')) = 'removed'
RETURN d.id AS id, d.name AS name, d.ecosystem AS ecosystem, d.current_version AS version, path,
       min(r.valid_from) AS removed_at
ORDER BY name
LIMIT 20
