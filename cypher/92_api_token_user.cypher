// 92_api_token_user: the account behind a personal access token. Params: $id (token hash).
MATCH (u:User)-[:HAS_TOKEN]->(k:ApiToken {id: $id})
RETURN u.id AS id, u.email AS email, u.name AS name, u.role AS role, u.created_at AS created_at,
       coalesce(u.plan, 'free') AS plan, k.last_used_at AS last_used_at
