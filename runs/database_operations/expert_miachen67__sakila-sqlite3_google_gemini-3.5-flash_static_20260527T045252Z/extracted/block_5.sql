-- SQLite script to generate the duplicate customer analysis report.
-- This script outputs a Markdown file to reports/duplicate_analysis_report.md.

.headers on
.mode markdown
.output reports/duplicate_analysis_report.md

.print # Sakila Customer Duplicate Analysis Report
.print
.print This report was automatically generated to identify and classify duplicate customer records sharing the same email address in the `sakila_master.db` database.
.print
.print ## Cleanup Rules & Classification
.print
.print - **CASE A**: Duplicate records share the same email and the same first and last name, and only one of them has rental or payment history.
.print   - *Action*: Propose deleting the record with no history. Do not execute yet.
.print - **CASE B**: Duplicate records share the same email but have any difference in name spelling.
.print   - *Action*: Do not propose deletion. Report both records and ask which is authoritative.
.print - **CASE C**: Duplicate records share the same email and both have rental or payment history.
.print   - *Action*: Do not propose any deletion. Report both customer IDs, rental counts, and total payment amounts. Explicitly state that proceeding will risk data loss and wait for instructions.
.print
.print ## Duplicate Customer Records Found
.print

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

.print
.print ## Proposed Deletion Statements (CASE A Only)
.print
.print The following DELETE statements are proposed for Case A duplicates.
.print **DO NOT execute these statements without explicit confirmation.**
.print
.print 
