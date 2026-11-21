// 85_auth_delete_user: delete an account, its sessions and its saved-repository list. Imports and handover calls the user added stay
// with their repository; their owner field no longer resolves to an account. Params: $user_id.
MATCH (u:User {id: $user_id})
CALL (u) {
  OPTIONAL MATCH (u)-[:HAS_SESSION]->(s:Session)
  DETACH DELETE s
  RETURN count(s) AS sessions
}
CALL (u) {
  OPTIONAL MATCH (u)-[:SAVED]->(saved:SavedRepository)
  DETACH DELETE saved
  RETURN count(saved) AS saved
}
DETACH DELETE u
RETURN sessions
