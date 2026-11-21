// 83_auth_session_user: the signed-in user for an unexpired session. Params: $id (token hash), $now.
MATCH (u:User)-[:HAS_SESSION]->(s:Session {id: $id})
WHERE s.expires_at > $now
RETURN u.id AS id, u.email AS email, u.name AS name, u.role AS role, u.created_at AS created_at,
       s.expires_at AS expires_at
