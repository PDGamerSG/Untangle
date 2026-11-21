// 94_api_token_revoke: delete one of the user's own tokens; another user's token id matches nothing.
// Params: $user_id, $id (token hash).
OPTIONAL MATCH (:User {id: $user_id})-[:HAS_TOKEN]->(k:ApiToken {id: $id})
DETACH DELETE k
RETURN count(k) AS revoked
