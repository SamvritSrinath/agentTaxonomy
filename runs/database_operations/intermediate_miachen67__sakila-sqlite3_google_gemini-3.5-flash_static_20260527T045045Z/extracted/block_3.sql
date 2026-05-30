PRAGMA foreign_keys = OFF;

DELETE FROM customer
WHERE customer_id NOT IN (
    SELECT MIN(customer_id)
    FROM customer
    GROUP BY first_name, last_name
);

PRAGMA foreign_keys = ON;
