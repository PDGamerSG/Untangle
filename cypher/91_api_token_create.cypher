// 91_api_token_create: store a personal access token for coding agents. Only the token's SHA-256 is stored; the
// owner sees the token once. A user keeps at most $max tokens. Params: $t = {id, user_id, name, prefix,
// created_at}, $max.
MATCH (u:User {id: $t.user_id})
OPTIONAL MATCH (u)-[:HAS_TOKEN]->(existing:ApiToken)
WITH u, count(existing) AS held
WHERE held < $max
CREATE (k:ApiToken {id: $t.id, user_id: $t.user_id, name: $t.name, prefix: $t.prefix, created_at: $t.created_at})
CREATE (u)-[:HAS_TOKEN]->(k)
RETURN k.id AS id
