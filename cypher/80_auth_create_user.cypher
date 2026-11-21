// 80_auth_create_user: create one account unless the email is already registered. MERGE on the normalised email
// returns the existing account instead of a second one; the unique constraint on User.email (applied by
// untangle.auth.service before the first sign-up) also rejects two simultaneous sign-ups with one address.
// Params: $u = {id, email, name, password_hash, role, created_at}. Returns created = false for a taken email.
MERGE (u:User {email: $u.email})
ON CREATE SET u.id = $u.id, u.name = $u.name, u.password_hash = $u.password_hash, u.role = $u.role,
              u.created_at = $u.created_at, u.fresh = true
WITH u, coalesce(u.fresh, false) AS created
REMOVE u.fresh
RETURN created, u.id AS id, u.email AS email, u.name AS name, u.role AS role, u.created_at AS created_at
