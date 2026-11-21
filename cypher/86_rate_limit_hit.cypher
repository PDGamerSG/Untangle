// 86_rate_limit_hit: count one event in a fixed window and return the window's total. The window id already
// contains its start time, so a new window starts from zero. Params: $id, $expires_at.
MERGE (r:RateLimit {id: $id})
ON CREATE SET r.count = 0, r.expires_at = $expires_at
SET r.count = r.count + 1
RETURN r.count AS count
