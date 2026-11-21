// 96_agent_memories: decisions that coding agents recorded in a repository, newest first. Params: $repo, $limit.
MATCH (d:Decision {repo: $repo, kind: 'agent'})
OPTIONAL MATCH (d)-[:ABOUT]->(a)
RETURN d.id AS id, d.subject AS subject, d.predicate AS topic, d.object AS decision, d.rationale AS rationale,
       d.status AS status, d.valid_from AS valid_from, d.recorded_by_name AS recorded_by, d.source_url AS source_url,
       collect(DISTINCT coalesce(a.path, a.key, a.name)) AS about
ORDER BY d.valid_from DESC
LIMIT $limit
