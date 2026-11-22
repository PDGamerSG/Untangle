// 73_pilot_requests_list: the newest pilot requests, for administrators. Params: $limit.
MATCH (r:PilotRequest)
RETURN r.id AS id, r.reference AS reference, r.name AS name, r.email AS email, r.company AS company, r.role AS role,
       r.team_size AS team_size, r.plan AS plan, r.message AS message, r.status AS status, r.user_id AS user_id,
       r.created_at AS created_at
ORDER BY r.created_at DESC
LIMIT $limit
