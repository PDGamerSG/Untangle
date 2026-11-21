MATCH (f:File {repo: $repo})
WITH f ORDER BY coalesce(f.alive, false) DESC, f.path SKIP $file_offset LIMIT $file_limit
RETURN f {.path, .alive} AS file
