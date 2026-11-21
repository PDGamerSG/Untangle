// 97_preflight_importers: one hop of the reverse import graph. Files that import any of $paths through the
// repository-map import index; the caller walks further hops and keeps the first path found to each file.
// Params: $repo, $paths, $seen (paths already reached, excluded), $limit.
MATCH (a:File {repo: $repo})-[r:IMPORTS]->(b:File {repo: $repo})
WHERE b.path IN $paths AND r.indexer = 'repository-map-v1' AND NOT a.path IN $seen
RETURN a.path AS source, b.path AS target, r.line AS line
ORDER BY source, target
LIMIT $limit
