// 82_auth_create_session: start a session for a user. Only the SHA-256 of the session token is stored, so a
// database read cannot be replayed as a cookie. $rehash replaces the stored hash when its parameters are outdated.
// Params: $id (token hash), $user_id, $now, $expires_at, $rehash (nullable).
MATCH (u:User {id: $user_id})
CREATE (s:Session {id: $id, user_id: $user_id, created_at: $now, expires_at: $expires_at})
CREATE (u)-[:HAS_SESSION]->(s)
SET u.last_login_at = $now, u.password_hash = coalesce($rehash, u.password_hash)
RETURN s.id AS id
