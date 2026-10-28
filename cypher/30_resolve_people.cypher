// 30_resolve_people: people matching a name/login, restricted to those who touched the repo.
// Params: $repo, $q (Lucene query), $limit.
CALL db.index.fulltext.queryNodes('person_search', $q, {limit: 25}) YIELD node, score
WHERE EXISTS { (node)-[:AUTHORED|OPENED|WROTE|REVIEWED]->(x) WHERE x.repo = $repo }
   OR EXISTS { (node)<-[:SPOKEN_BY]-(:Utterance {repo: $repo}) }
   OR EXISTS { (node)<-[:STATED_BY]-(:Decision {repo: $repo}) }
RETURN node.id AS id, node.name AS name, node.login AS login, node.kind AS kind, score
ORDER BY score DESC
LIMIT $limit
