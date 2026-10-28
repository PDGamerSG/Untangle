// 34_repo_people: fallback "person to ask" for a whole repository when the question matched no entity:
// authors of the 2000 most recent commits, ranked by exp(-age_days / 365). Params: $repo, $now (epoch ms), $limit.
// Same row shape as 34_person_to_ask so the caller renders both the same way.
MATCH (c:Commit)
WHERE c.repo = $repo AND c.authored_at >= 0
WITH c ORDER BY c.authored_at DESC LIMIT 2000
WITH collect(c) AS recent
WITH recent, size(recent) AS total_commits
UNWIND recent AS c
MATCH (p:Person)-[:AUTHORED]->(c)
WITH total_commits, p, count(DISTINCT c) AS n, sum(exp(-toFloat($now - c.authored_at) / 31536000000.0)) AS score
ORDER BY score DESC
LIMIT $limit
RETURN p.id AS id, p.name AS name, p.login AS login, score, [{kind: 'commit', n: n, weight: score}] AS parts,
       total_commits, 0 AS total_prs
