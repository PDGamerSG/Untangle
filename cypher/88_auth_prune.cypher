// 88_auth_prune: remove expired sessions, rate-limit windows and abandoned guest accounts (no session left,
// older than $guest_age ms) in small batches. Params: $now, $guest_age.
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
CALL () {
  MATCH (u:User {role: 'guest'}) WHERE u.created_at <= $now - $guest_age AND NOT (u)-[:HAS_SESSION]->(:Session)
  WITH u LIMIT 500
  CALL (u) {
    OPTIONAL MATCH (u)-[:SAVED]->(saved:SavedRepository)
    DETACH DELETE saved
  }
  DETACH DELETE u
  RETURN count(*) AS guests
}
RETURN sessions, limits, guests
