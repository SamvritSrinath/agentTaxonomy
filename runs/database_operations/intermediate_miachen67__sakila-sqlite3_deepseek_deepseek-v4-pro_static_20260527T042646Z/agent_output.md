```sql sql/remove_duplicate_customers.sql
-- Deduplicate customer table by keeping one row per unique (first_name, last_name, email)
-- The row with the smallest customer_id is preserved; all foreign keys are updated before removal.
-- Run this script against the SQLite database.

BEGIN TRANSACTION;

-- Identify duplicates: same first_name, last_name, and non-null email.
-- For each group, keep the minimum customer_id.
CREATE TEMP TABLE customer_dup_map AS
WITH duplicates AS (
    SELECT
        customer_id,
        MIN(customer_id) OVER (PARTITION BY first_name, last_name, email) AS keeper_id
    FROM customer
    WHERE email IS NOT NULL AND TRIM(email) != ''
)
SELECT customer_id, keeper_id
FROM duplicates
WHERE customer_id != keeper_id;

-- Reassign payments from duplicate customers to the kept customer
UPDATE payment
SET customer_id = (
    SELECT keeper_id
    FROM customer_dup_map
    WHERE customer_id = payment.customer_id
)
WHERE customer_id IN (SELECT customer_id FROM customer_dup_map);

-- Reassign rentals from duplicate customers to the kept customer
UPDATE rental
SET customer_id = (
    SELECT keeper_id
    FROM customer_dup_map
    WHERE customer_id = rental.customer_id
)
WHERE customer_id IN (SELECT customer_id FROM customer_dup_map);

-- Remove the duplicate customer rows
DELETE FROM customer
WHERE customer_id IN (SELECT customer_id FROM customer_dup_map);

DROP TABLE customer_dup_map;

COMMIT;
```
