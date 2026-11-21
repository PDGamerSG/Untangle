MATCH (f:Feature {repo: $repo})
WITH f ORDER BY f.name, f.id SKIP $feature_offset LIMIT $feature_limit
OPTIONAL MATCH (f)-[:ENTRYPOINT]->(e:File {repo: $repo})
WITH f, collect(e.path) AS entrypoints ORDER BY f.name, f.id
RETURN f {.id, .name, .description, .source, entrypoints: entrypoints} AS feature
