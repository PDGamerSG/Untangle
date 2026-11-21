// 97_preflight_cochange: files that changed in the same commits as $paths, most shared commits first. Merges and
// sweeping commits that touched more than $max_files files are ignored so a formatting pass does not dominate.
// Params: $repo, $paths, $max_files, $limit. `total` is the number of qualifying commits on $paths.
MATCH (t:File {repo: $repo})
WHERE t.path IN $paths
MATCH (c:Commit)-[:TOUCHED]->(t)
WHERE NOT coalesce(c.is_merge, false) AND COUNT { (c)-[:TOUCHED]->() } <= $max_files
WITH collect(DISTINCT c) AS commits
WITH commits, size(commits) AS total
UNWIND commits AS c
MATCH (c)-[:TOUCHED]->(o:File {repo: $repo})
WHERE NOT o.path IN $paths AND coalesce(o.alive, true)
WITH total, o, count(DISTINCT c) AS together
ORDER BY together DESC, o.path
LIMIT $limit
RETURN o.path AS path, together, total
