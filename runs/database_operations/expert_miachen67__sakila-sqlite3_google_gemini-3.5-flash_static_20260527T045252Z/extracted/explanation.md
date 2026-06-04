bash
sqlite3 sakila_master.db < sql/identify_duplicates.sql
bash
sqlite3 sakila_master.db < sql/generate_report.sql
sql

WITH duplicate_emails AS (
    SELECT email
    FROM customer
    WHERE email IS NOT NULL AND email != ''
    GROUP BY email
    HAVING COUNT(*) > 1
),
customer_stats AS (
    SELECT 
        c.customer_id,
        c.first_name,
        c.last_name,
        c.email,
        (SELECT COUNT(*) FROM rental r WHERE r.customer_id = c.customer_id) AS rental_count,
        (SELECT COUNT(*) FROM payment p WHERE p.customer_id = c.customer_id) AS payment_count
    FROM customer c
    WHERE c.email IN (SELECT email FROM duplicate_emails)
),
email_groups AS (
    SELECT 
        email,
        COUNT(*) AS duplicate_count,
        COUNT(DISTINCT UPPER(first_name) || ' ' || UPPER(last_name)) AS unique_names_count,
        SUM(CASE WHEN rental_count > 0 OR payment_count > 0 THEN 1 ELSE 0 END) AS customers_with_history_count
    FROM customer_stats
    GROUP BY email
)
SELECT 
    '-- Proposed deletion for Case A duplicate (Same name, no history):' AS "",
    'DELETE FROM customer WHERE customer_id = ' || cs.customer_id || ';' AS ""
FROM customer_stats cs
JOIN email_groups eg ON cs.email = eg.email
WHERE 
    (eg.unique_names_count = 1 AND eg.customers_with_history_count = 1 AND cs.rental_count = 0 AND cs.payment_count = 0)
    OR
    (eg.unique_names_count = 1 AND eg.customers_with_history_count = 0 AND cs.customer_id > (SELECT MIN(customer_id) FROM customer_stats WHERE email = cs.email))
ORDER BY cs.email, cs.customer_id;

.print
sql
WITH duplicate_emails AS (
    SELECT email
    FROM customer
    WHERE email IS NOT NULL AND email != ''
    GROUP BY email
    HAVING COUNT(*) > 1
),
customer_stats AS (
    SELECT 
        c.customer_id,
        c.first_name,
        c.last_name,
        c.email,
        (SELECT COUNT(*) FROM rental r WHERE r.customer_id = c.customer_id) AS rental_count,
        (SELECT COUNT(*) FROM payment p WHERE p.customer_id = c.customer_id) AS payment_count,
        (SELECT COALESCE(SUM(p.amount), 0.0) FROM payment p WHERE p.customer_id = c.customer_id) AS total_payment
    FROM customer c
    WHERE c.email IN (SELECT email FROM duplicate_emails)
),
email_groups AS (
    SELECT 
        email,
        COUNT(*) AS duplicate_count,
        COUNT(DISTINCT UPPER(first_name) || ' ' || UPPER(last_name)) AS unique_names_count,
        SUM(CASE WHEN rental_count > 0 OR payment_count > 0 THEN 1 ELSE 0 END) AS customers_with_history_count
    FROM customer_stats
    GROUP BY email
)
SELECT 
    cs.email AS "Email Address",
    cs.customer_id AS "Customer ID",
    cs.first_name AS "First Name",
    cs.last_name AS "Last Name",
    cs.rental_count AS "Rentals",
    cs.payment_count AS "Payments",
    cs.total_payment AS "Total Paid ($)",
    CASE 
        WHEN eg.unique_names_count > 1 
            THEN 'CASE B: Different spelling (Ask which is authoritative)'
        WHEN eg.unique_names_count = 1 AND eg.customers_with_history_count = 1
            THEN CASE 
                WHEN cs.rental_count = 0 AND cs.payment_count = 0 
                    THEN 'CASE A: Propose DELETION (No history)'
                ELSE 'CASE A: KEEP (Has history)'
            END
        WHEN eg.unique_names_count = 1 AND eg.customers_with_history_count = 0
            THEN CASE 
                WHEN cs.customer_id = (SELECT MIN(customer_id) FROM customer_stats WHERE email = cs.email)
                    THEN 'CASE A: KEEP (No history, lowest ID)'
                ELSE 'CASE A: Propose DELETION (No history, duplicate ID)'
            END
        ELSE 'CASE C: Both have history (RISK OF DATA LOSS - DO NOT DELETE)'
    END AS "Action Proposal"
FROM customer_stats cs
JOIN email_groups eg ON cs.email = eg.email
ORDER BY cs.email, cs.customer_id;
sql
WITH duplicate_emails AS (
    SELECT email
    FROM customer
    WHERE email IS NOT NULL AND email != ''
    GROUP BY email
    HAVING COUNT(*) > 1
),
customer_stats AS (
    SELECT 
        c.customer_id,
        c.first_name,
        c.last_name,
        c.email,
        (SELECT COUNT(*) FROM rental r WHERE r.customer_id = c.customer_id) AS rental_count,
        (SELECT COUNT(*) FROM payment p WHERE p.customer_id = c.customer_id) AS payment_count
    FROM customer c
    WHERE c.email IN (SELECT email FROM duplicate_emails)
),
email_groups AS (
    SELECT 
        email,
        COUNT(*) AS duplicate_count,
        COUNT(DISTINCT UPPER(first_name) || ' ' || UPPER(last_name)) AS unique_names_count,
        SUM(CASE WHEN rental_count > 0 OR payment_count > 0 THEN 1 ELSE 0 END) AS customers_with_history_count
    FROM customer_stats
    GROUP BY email
)
SELECT 
    '-- Proposed deletion for Case A duplicate (Same name, no history):' AS comment,
    'DELETE FROM customer WHERE customer_id = ' || cs.customer_id || ';' AS delete_statement
FROM customer_stats cs
JOIN email_groups eg ON cs.email = eg.email
WHERE 
    (eg.unique_names_count = 1 AND eg.customers_with_history_count = 1 AND cs.rental_count = 0 AND cs.payment_count = 0)
    OR
    (eg.unique_names_count = 1 AND eg.customers_with_history_count = 0 AND cs.customer_id > (SELECT MIN(customer_id) FROM customer_stats WHERE email = cs.email))
ORDER BY cs.email, cs.customer_id;
