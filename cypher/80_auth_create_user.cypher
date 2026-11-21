// 80_auth_create_user: create one account. The unique constraint on User.email rejects a duplicate atomically,
// so two simultaneous sign-ups with one address cannot both succeed.
// Params: $u = {id, email, name, password_hash, role, created_at}.
CREATE (u:User {id: $u.id, email: $u.email, name: $u.name, password_hash: $u.password_hash, role: $u.role,
                created_at: $u.created_at})
RETURN u.id AS id, u.email AS email, u.name AS name, u.role AS role, u.created_at AS created_at
