// 98_briefing_areas: the repository's code areas for a day-one briefing. An area is a file's first directory, or its
// first two for container directories ($nested: src, packages, ...); top-level files form "(root)". Per area:
// current files, commits that touched them, the latest change, the three people who authored most of those commits
// (bots excluded) and the active decisions about the files or about keys, dependencies and symbols defined in them.
// Params: $repo, $nested, $limit.
MATCH (f:File {repo: $repo})
WHERE coalesce(f.alive, true)
WITH f, split(f.path, '/') AS parts
WITH f, CASE WHEN size(parts) = 1 THEN '(root)'
             WHEN parts[0] IN $nested AND size(parts) > 2 THEN parts[0] + '/' + parts[1]
             ELSE parts[0] END AS area
WITH area, collect(f) AS files
CALL (files) {
  UNWIND files AS f
  OPTIONAL MATCH (c:Commit)-[:TOUCHED]->(f)
  RETURN count(DISTINCT c) AS commits, max(coalesce(c.committed_at, c.authored_at)) AS last_changed
}
CALL (files) {
  UNWIND files AS f
  MATCH (p:Person)-[:AUTHORED]->(c:Commit)-[:TOUCHED]->(f)
  WHERE NOT coalesce(p.login, p.name, '') ENDS WITH '[bot]'
  WITH p, count(DISTINCT c) AS n
  ORDER BY n DESC, p.name
  LIMIT 3
  RETURN collect({id: p.id, name: p.name, login: p.login, commits: n}) AS people
}
CALL (files) {
  UNWIND files AS f
  OPTIONAL MATCH (d1:Decision {status: 'active'})-[:ABOUT]->(f)
  OPTIONAL MATCH (d2:Decision {status: 'active'})-[:ABOUT]->(:ConfigKey|Dependency|Symbol)-[:SET_IN|DECLARED_IN|DEFINED_IN]->(f)
  WITH collect(DISTINCT d1) + collect(DISTINCT d2) AS ds
  UNWIND (CASE WHEN size(ds) = 0 THEN [null] ELSE ds END) AS d
  RETURN count(DISTINCT d) AS decisions
}
RETURN area, size(files) AS files, commits, last_changed, people, decisions
ORDER BY commits DESC, files DESC, area
LIMIT $limit
