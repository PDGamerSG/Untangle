// 84_auth_revoke_session: end one session (sign out). Params: $id (token hash).
OPTIONAL MATCH (s:Session {id: $id})
DETACH DELETE s
RETURN count(s) AS revoked
