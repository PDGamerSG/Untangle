// 81_auth_user_by_email: the account for a normalised email address, including its password hash for sign-in.
// Params: $email.
MATCH (u:User {email: $email})
RETURN u.id AS id, u.email AS email, u.name AS name, u.role AS role, u.created_at AS created_at,
       u.password_hash AS password_hash
