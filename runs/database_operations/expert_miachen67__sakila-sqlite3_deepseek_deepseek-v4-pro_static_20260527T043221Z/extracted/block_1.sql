-- Filename: sql/analyze_duplicates.sql
-- Purpose: Identify duplicate customers by email in sakila_master.db,
--          classify them according to the cleanup rules, and output a report.
-- No modifications (DELETE/UPDATE/DROP) are executed.

.mode column
.headers on

-- =====================================================================
-- Step 1: Compute per-customer rental counts and payment totals
-- =====================================================================
WITH customer_stats AS (
    SELECT
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        COALESCE(r.rental_count, 0) AS rental_count,
        COALESCE(p.total_payment, 0.0) AS total_payment,
        CASE WHEN COALESCE(r.rental_count, 0) > 0 OR COALESCE(p.total_payment, 0.0) > 0 THEN 1 ELSE 0 END AS has_history
    FROM customer c
    LEFT JOIN (
        SELECT customer_id, COUNT(*) AS rental_count
        FROM rental
        GROUP BY customer_id
    ) r ON c.customer_id = r.customer_id
    LEFT JOIN (
        SELECT customer_id, SUM(amount) AS total_payment
        FROM payment
        GROUP BY customer_id
    ) p ON c.customer_id = p.customer_id
),
-- =====================================================================
-- Step 2: Identify emails that appear more than once
-- =====================================================================
dup_emails AS (
    SELECT email, COUNT(*) AS cnt
    FROM customer_stats
    GROUP BY email
    HAVING COUNT(*) > 1
),
-- =====================================================================
-- Step 3: Classify each duplicate email group
-- =====================================================================
group_class AS (
    SELECT
        cs.email,
        COUNT(DISTINCT LOWER(cs.first_name)) AS name_first_div,
        COUNT(DISTINCT LOWER(cs.last_name)) AS name_last_div,
        SUM(cs.has_history) AS history_sum,
        COUNT(*) AS total_cust,
        CASE
            -- Names differ (case‑insensitive): manual review
            WHEN COUNT(DISTINCT LOWER(cs.first_name)) > 1
                 OR COUNT(DISTINCT LOWER(cs.last_name)) > 1 THEN 'NAMES_DIFFER'
            -- Names match and exactly one customer has history → propose deletion of the others
            WHEN SUM(cs.has_history) = 1 THEN 'PROPOSE_DELETE'
            -- Names match but more than one have history → risky, requires decision
            WHEN SUM(cs.has_history) > 1 THEN 'BOTH_HAVE_HISTORY'
            -- Names match and zero have history → unclear; manual review
            ELSE 'NEEDS_REVIEW'
        END AS group_action
    FROM customer_stats cs
    WHERE cs.email IN (SELECT email FROM dup_emails)
    GROUP BY cs.email
)

-- =====================================================================
-- Report Section 1: Group‑level summary
-- =====================================================================
SELECT '==============================================' AS '';
SELECT '  DUPLICATE CUSTOMER ANALYSIS - GROUP SUMMARY' AS '';
SELECT '==============================================' AS '';
SELECT '' AS '';

SELECT
    gc.email,
    gc.total_cust AS num_customers,
    gc.group_action,
    CASE
        WHEN gc.group_action = 'PROPOSE_DELETE' THEN 'One record has history; delete the other(s) with no history.'
        WHEN gc.group_action = 'NAMES_DIFFER' THEN 'Names differ; please identify the authoritative record(s).'
        WHEN gc.group_action = 'BOTH_HAVE_HISTORY' THEN 'All records have history; proceeding risks data loss.'
        ELSE 'All records have no history; manual review required.'
    END AS recommendation
FROM group_class gc
ORDER BY gc.email;

-- =====================================================================
-- Report Section 2: Detail for risky groups (BOTH_HAVE_HISTORY)
-- =====================================================================
SELECT '' AS '';
SELECT '==============================================' AS '';
SELECT '  DETAIL: GROUPS WHERE BOTH/ALL HAVE HISTORY' AS '';
SELECT '  (payment amounts shown for risk assessment)' AS '';
SELECT '==============================================' AS '';
SELECT '' AS '';

SELECT
    cs.email,
    cs.customer_id,
    cs.first_name,
    cs.last_name,
    cs.rental_count,
    PRINTF('%.2f', cs.total_payment) AS total_payment
FROM customer_stats cs
JOIN group_class gc ON cs.email = gc.email
WHERE gc.group_action = 'BOTH_HAVE_HISTORY'
ORDER BY cs.email, cs.customer_id;

-- =====================================================================
-- Report Section 3: Detail for groups needing action or review
-- =====================================================================
SELECT '' AS '';
SELECT '==============================================' AS '';
SELECT '  DETAIL: GROUPS WITH DELETION CANDIDATES OR NAME DIFFERENCES' AS '';
SELECT '==============================================' AS '';
SELECT '' AS '';

SELECT
    cs.email,
    cs.customer_id,
    cs.first_name,
    cs.last_name,
    cs.rental_count,
    CASE WHEN cs.has_history = 1 THEN 'Yes' ELSE 'No' END AS has_history,
    gc.group_action,
    CASE
        WHEN gc.group_action = 'PROPOSE_DELETE' AND cs.has_history = 0 THEN '>>> CANDIDATE FOR DELETION <<<'
        WHEN gc.group_action = 'PROPOSE_DELETE' AND cs.has_history = 1 THEN 'KEEP (has history)'
        WHEN gc.group_action = 'NAMES_DIFFER' THEN 'Review name - manual decision'
        ELSE 'No history - manual review'
    END AS note
FROM customer_stats cs
JOIN group_class gc ON cs.email = gc.email
WHERE gc.group_action IN ('PROPOSE_DELETE', 'NAMES_DIFFER', 'NEEDS_REVIEW')
ORDER BY cs.email, cs.customer_id;

-- =====================================================================
-- End of analysis. No records have been modified.
-- =====================================================================
