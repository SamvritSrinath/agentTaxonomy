-- Identify duplicate users by email.
-- This query returns the IDs that would be deleted (all but the smallest ID per duplicate email).
-- Run this script to see the list, then approve before executing any DELETE.

SELECT u.id
FROM users u
JOIN (
    SELECT email, MIN(id) AS keep_id
    FROM users
    GROUP BY email
    HAVING COUNT(*) > 1
) dup ON u.email = dup.email
WHERE u.id != dup.keep_id
ORDER BY u.id;
