// 95_api_token_used: note when a token was last used (written at most once a minute per token). Params: $id, $now.
MATCH (k:ApiToken {id: $id})
WHERE coalesce(k.last_used_at, 0) < $now - 60000
SET k.last_used_at = $now
RETURN k.id AS id
