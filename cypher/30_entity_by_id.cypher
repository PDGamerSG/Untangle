// 30_entity_by_id: one entity with the file and module it belongs to. Params: $id.
MATCH (e:File|Module|Symbol|ConfigKey|Dependency {id: $id})
RETURN e.id AS id, labels(e)[0] AS label, coalesce(e.name, e.key, e.path) AS name, e.path AS path, e.key AS key,
       e.kind AS kind, e.ecosystem AS ecosystem, e.ext AS ext, e.tokens AS tokens, e.line AS line,
       e.current_value AS current_value, e.current_since AS current_since, e.current_version AS current_version,
       e.alive AS alive, e.is_config AS is_config, e.is_doc AS is_doc, e.first_seen_at AS first_seen_at,
       e.last_touched_at AS last_touched_at, e.touch_count AS touch_count,
       [(e)-[:DEFINED_IN|SET_IN|DECLARED_IN]->(f:File) | {id: f.id, path: f.path}][0] AS file,
       [(e)-[:IN]->(m:Module) | {id: m.id, path: m.path}][0] AS module
