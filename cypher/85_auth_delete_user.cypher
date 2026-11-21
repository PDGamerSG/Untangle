// 85_auth_delete_user: delete an account and all of its sessions. Imports and handover calls the user added stay
// with their repository; their owner field no longer resolves to an account. Params: $user_id.
MATCH (u:User {id: $user_id})
CALL (u) {
  OPTIONAL MATCH (u)-[:HAS_SESSION]->(s:Session)
  DETACH DELETE s
  RETURN count(s) AS sessions
}
DETACH DELETE u
RETURN sessions
