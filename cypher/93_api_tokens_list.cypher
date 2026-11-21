// 93_api_tokens_list: a user's tokens, newest first, without any secret. Params: $user_id.
MATCH (:User {id: $user_id})-[:HAS_TOKEN]->(k:ApiToken)
RETURN k.id AS id, k.name AS name, k.prefix AS prefix, k.created_at AS created_at, k.last_used_at AS last_used_at
ORDER BY k.created_at DESC
