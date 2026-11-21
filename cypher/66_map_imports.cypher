MATCH (a:File {repo: $repo})-[r:IMPORTS]->(b:File {repo: $repo})
WHERE r.indexer = 'repository-map-v1'
WITH a, b, r ORDER BY a.path, b.path SKIP $import_offset LIMIT $import_limit
RETURN {source: a.path, target: b.path, line: r.line, specifier: r.specifier} AS edge
