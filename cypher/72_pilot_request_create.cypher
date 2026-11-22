// 72_pilot_request_create: store a pilot or plan request from the public pricing page. The network address is
// kept only as a digest. Params: $p = {id, reference, name, email, company, role, team_size, plan, message,
// user_id, status, ip_digest, created_at}.
CREATE (r:PilotRequest)
SET r = $p
RETURN r.reference AS reference
