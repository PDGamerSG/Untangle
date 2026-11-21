// 88_auth_prune: remove expired sessions and rate-limit windows in small batches. Params: $now.
CALL () {
  MATCH (s:Session) WHERE s.expires_at <= $now
  WITH s LIMIT 500
  DETACH DELETE s
  RETURN count(*) AS sessions
}
CALL () {
  MATCH (r:RateLimit) WHERE r.expires_at <= $now
  WITH r LIMIT 500
  DETACH DELETE r
  RETURN count(*) AS limits
}
RETURN sessions, limits
