/*
  Read-only duplicate customer review for sakila_master.db.

  Purpose:
    Identify customer records sharing the same email address and classify them
    according to the cleanup rules.

  Safety:
    - This script enables SQLite query-only mode.
    - This script does not modify data.
    - This script does not print full email addresses.
    - Names are printed only for name-spelling conflicts.
    - Payment totals are printed only where history conflicts require them.
*/

PRAGMA query_only = ON;

SELECT
  'READ-ONLY REVIEW: no data-changing statements are executed by this script.' AS notice;

SELECT
  'Duplicate customer records are grouped by normalized email internally, but full email addresses are not printed.' AS privacy_notice;

SELECT
  'Do not delete anything until the complete proposed-change list has been reviewed and explicitly confirmed.' AS confirmation_required;

/* -------------------------------------------------------------------------- */
/* Summary                                                                    */
/* -------------------------------------------------------------------------- */

WITH
customer_base AS (
  SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    lower(trim(c.email)) AS normalized_email,
    COALESCE(r.rental_count, 0) AS rental_count,
    COALESCE(p.payment_total, 0.00) AS payment_total,
    CASE
      WHEN COALESCE(r.rental_count, 0) > 0 OR COALESCE(p.payment_total, 0.00) > 0
      THEN 1
      ELSE 0
    END AS has_history
  FROM customer AS c
  LEFT JOIN (
    SELECT
      customer_id,
      COUNT(*) AS rental_count
    FROM rental
    GROUP BY customer_id
  ) AS r
    ON r.customer_id = c.customer_id
  LEFT JOIN (
    SELECT
      customer_id,
      ROUND(SUM(amount), 2) AS payment_total
    FROM payment
    GROUP BY customer_id
  ) AS p
    ON p.customer_id = c.customer_id
  WHERE c.email IS NOT NULL
    AND trim(c.email) <> ''
),
duplicate_email_groups AS (
  SELECT
    normalized_email,
    DENSE_RANK() OVER (ORDER BY normalized_email) AS duplicate_email_group,
    COUNT(*) AS customer_count,
    COUNT(DISTINCT COALESCE(first_name, '') || char(31) || COALESCE(last_name, '')) AS distinct_name_count,
    SUM(has_history) AS history_count,
    SUM(CASE WHEN has_history = 0 THEN 1 ELSE 0 END) AS no_history_count
  FROM customer_base
  GROUP BY normalized_email
  HAVING COUNT(*) > 1
),
duplicate_customers AS (
  SELECT
    g.duplicate_email_group,
    g.customer_count,
    g.distinct_name_count,
    g.history_count,
    g.no_history_count,
    b.customer_id,
    b.first_name,
    b.last_name,
    b.rental_count,
    b.payment_total,
    b.has_history
  FROM customer_base AS b
  INNER JOIN duplicate_email_groups AS g
    ON g.normalized_email = b.normalized_email
),
proposed_deletions AS (
  SELECT
    d.duplicate_email_group,
    d.customer_id AS proposed_delete_customer_id,
    keeper.customer_id AS keep_customer_id
  FROM duplicate_customers AS d
  INNER JOIN duplicate_customers AS keeper
    ON keeper.duplicate_email_group = d.duplicate_email_group
   AND keeper.has_history = 1
  WHERE d.distinct_name_count = 1
    AND d.history_count = 1
    AND d.no_history_count >= 1
    AND d.has_history = 0
),
both_history_pairs AS (
  SELECT
    a.duplicate_email_group,
    a.customer_id AS customer_id_1,
    b.customer_id AS customer_id_2
  FROM duplicate_customers AS a
  INNER JOIN duplicate_customers AS b
    ON b.duplicate_email_group = a.duplicate_email_group
   AND b.customer_id > a.customer_id
  WHERE a.has_history = 1
    AND b.has_history = 1
),
conservative_review_groups AS (
  SELECT DISTINCT
    duplicate_email_group
  FROM duplicate_customers
  WHERE distinct_name_count = 1
    AND NOT (
      history_count = 1
      AND no_history_count >= 1
    )
)
SELECT
  (SELECT COUNT(*) FROM duplicate_email_groups) AS duplicate_email_group_count,
  (SELECT COUNT(*) FROM duplicate_customers) AS duplicate_customer_record_count,
  (SELECT COUNT(*) FROM proposed_deletions) AS proposed_no_history_delete_count,
  (SELECT COUNT(DISTINCT duplicate_email_group) FROM duplicate_customers WHERE distinct_name_count > 1) AS name_spelling_conflict_group_count,
  (SELECT COUNT(*) FROM both_history_pairs) AS both_history_pair_count,
  (SELECT COUNT(*) FROM conservative_review_groups) AS conservative_review_group_count;

/* -------------------------------------------------------------------------- */
/* 1. Proposed deletion candidates                                             */
/* -------------------------------------------------------------------------- */

SELECT
  'SECTION 1: Proposed deletion candidates. These are proposals only; no deletion has been executed.' AS section;

SELECT
  'Rule: same duplicate email group, same first and last name for every record in the group, exactly one record has rental/payment history, proposed record has no history.' AS rule_applied;

WITH
customer_base AS (
  SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    lower(trim(c.email)) AS normalized_email,
    COALESCE(r.rental_count, 0) AS rental_count,
    COALESCE(p.payment_total, 0.00) AS payment_total,
    CASE
      WHEN COALESCE(r.rental_count, 0) > 0 OR COALESCE(p.payment_total, 0.00) > 0
      THEN 1
      ELSE 0
    END AS has_history
  FROM customer AS c
  LEFT JOIN (
    SELECT customer_id, COUNT(*) AS rental_count
    FROM rental
    GROUP BY customer_id
  ) AS r
    ON r.customer_id = c.customer_id
  LEFT JOIN (
    SELECT customer_id, ROUND(SUM(amount), 2) AS payment_total
    FROM payment
    GROUP BY customer_id
  ) AS p
    ON p.customer_id = c.customer_id
  WHERE c.email IS NOT NULL
    AND trim(c.email) <> ''
),
duplicate_email_groups AS (
  SELECT
    normalized_email,
    DENSE_RANK() OVER (ORDER BY normalized_email) AS duplicate_email_group,
    COUNT(*) AS customer_count,
    COUNT(DISTINCT COALESCE(first_name, '') || char(31) || COALESCE(last_name, '')) AS distinct_name_count,
    SUM(has_history) AS history_count,
    SUM(CASE WHEN has_history = 0 THEN 1 ELSE 0 END) AS no_history_count
  FROM customer_base
  GROUP BY normalized_email
  HAVING COUNT(*) > 1
),
duplicate_customers AS (
  SELECT
    g.duplicate_email_group,
    g.customer_count,
    g.distinct_name_count,
    g.history_count,
    g.no_history_count,
    b.customer_id,
    b.rental_count,
    b.payment_total,
    b.has_history
  FROM customer_base AS b
  INNER JOIN duplicate_email_groups AS g
    ON g.normalized_email = b.normalized_email
)
SELECT
  d.duplicate_email_group,
  d.customer_id AS proposed_delete_customer_id,
  keeper.customer_id AS keep_customer_id,
  d.rental_count AS proposed_delete_rental_count,
  d.payment_total AS proposed_delete_payment_total
FROM duplicate_customers AS d
INNER JOIN duplicate_customers AS keeper
  ON keeper.duplicate_email_group = d.duplicate_email_group
 AND keeper.has_history = 1
WHERE d.distinct_name_count = 1
  AND d.history_count = 1
  AND d.no_history_count >= 1
  AND d.has_history = 0
ORDER BY
  d.duplicate_email_group,
  d.customer_id;

/* -------------------------------------------------------------------------- */
/* 2. Name-spelling conflicts                                                  */
/* -------------------------------------------------------------------------- */

SELECT
  'SECTION 2: Name-spelling conflicts. No deletion is proposed for these records; ask which record is authoritative.' AS section;

WITH
customer_base AS (
  SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    lower(trim(c.email)) AS normalized_email,
    COALESCE(r.rental_count, 0) AS rental_count,
    COALESCE(p.payment_total, 0.00) AS payment_total,
    CASE
      WHEN COALESCE(r.rental_count, 0) > 0 OR COALESCE(p.payment_total, 0.00) > 0
      THEN 1
      ELSE 0
    END AS has_history
  FROM customer AS c
  LEFT JOIN (
    SELECT customer_id, COUNT(*) AS rental_count
    FROM rental
    GROUP BY customer_id
  ) AS r
    ON r.customer_id = c.customer_id
  LEFT JOIN (
    SELECT customer_id, ROUND(SUM(amount), 2) AS payment_total
    FROM payment
    GROUP BY customer_id
  ) AS p
    ON p.customer_id = c.customer_id
  WHERE c.email IS NOT NULL
    AND trim(c.email) <> ''
),
duplicate_email_groups AS (
  SELECT
    normalized_email,
    DENSE_RANK() OVER (ORDER BY normalized_email) AS duplicate_email_group,
    COUNT(DISTINCT COALESCE(first_name, '') || char(31) || COALESCE(last_name, '')) AS distinct_name_count
  FROM customer_base
  GROUP BY normalized_email
  HAVING COUNT(*) > 1
)
SELECT
  g.duplicate_email_group,
  b.customer_id,
  b.first_name,
  b.last_name,
  b.rental_count,
  CASE WHEN b.has_history = 1 THEN 'yes' ELSE 'no' END AS has_rental_or_payment_history,
  'Administrator must identify the authoritative record before any action.' AS required_action
FROM customer_base AS b
INNER JOIN duplicate_email_groups AS g
  ON g.normalized_email = b.normalized_email
WHERE g.distinct_name_count > 1
ORDER BY
  g.duplicate_email_group,
  b.customer_id;

/* -------------------------------------------------------------------------- */
/* 3. Both-history conflicts                                                   */
/* -------------------------------------------------------------------------- */

SELECT
  'SECTION 3: Both-history conflicts. No deletion is proposed. Proceeding will risk data loss; wait for instructions.' AS section;

WITH
customer_base AS (
  SELECT
    c.customer_id,
    lower(trim(c.email)) AS normalized_email,
    COALESCE(r.rental_count, 0) AS rental_count,
    COALESCE(p.payment_total, 0.00) AS payment_total,
    CASE
      WHEN COALESCE(r.rental_count, 0) > 0 OR COALESCE(p.payment_total, 0.00) > 0
      THEN 1
      ELSE 0
    END AS has_history
  FROM customer AS c
  LEFT JOIN (
    SELECT customer_id, COUNT(*) AS rental_count
    FROM rental
    GROUP BY customer_id
  ) AS r
    ON r.customer_id = c.customer_id
  LEFT JOIN (
    SELECT customer_id, ROUND(SUM(amount), 2) AS payment_total
    FROM payment
    GROUP BY customer_id
  ) AS p
    ON p.customer_id = c.customer_id
  WHERE c.email IS NOT NULL
    AND trim(c.email) <> ''
),
duplicate_email_groups AS (
  SELECT
    normalized_email,
    DENSE_RANK() OVER (ORDER BY normalized_email) AS duplicate_email_group
  FROM customer_base
  GROUP BY normalized_email
  HAVING COUNT(*) > 1
),
duplicate_customers AS (
  SELECT
    g.duplicate_email_group,
    b.customer_id,
    b.rental_count,
    b.payment_total,
    b.has_history
  FROM customer_base AS b
  INNER JOIN duplicate_email_groups AS g
    ON g.normalized_email = b.normalized_email
)
SELECT
  a.duplicate_email_group,
  a.customer_id AS customer_id_1,
  a.rental_count AS customer_1_rental_count,
  a.payment_total AS customer_1_total_payment_amount,
  b.customer_id AS customer_id_2,
  b.rental_count AS customer_2_rental_count,
  b.payment_total AS customer_2_total_payment_amount,
  'Risk of data loss: both records have rental or payment history. Wait for explicit instructions.' AS warning
FROM duplicate_customers AS a
INNER JOIN duplicate_customers AS b
  ON b.duplicate_email_group = a.duplicate_email_group
 AND b.customer_id > a.customer_id
WHERE a.has_history = 1
  AND b.has_history = 1
ORDER BY
  a.duplicate_email_group,
  a.customer_id,
  b.customer_id;

/* -------------------------------------------------------------------------- */
/* 4. Conservative review                                                       */
/* -------------------------------------------------------------------------- */

SELECT
  'SECTION 4: Conservative review. These groups do not meet safe proposal criteria; ask before taking action.' AS section;

WITH
customer_base AS (
  SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    lower(trim(c.email)) AS normalized_email,
    COALESCE(r.rental_count, 0) AS rental_count,
    COALESCE(p.payment_total, 0.00) AS payment_total,
    CASE
      WHEN COALESCE(r.rental_count, 0) > 0 OR COALESCE(p.payment_total, 0.00) > 0
      THEN 1
      ELSE 0
    END AS has_history
  FROM customer AS c
  LEFT JOIN (
    SELECT customer_id, COUNT(*) AS rental_count
    FROM rental
    GROUP BY customer_id
  ) AS r
    ON r.customer_id = c.customer_id
  LEFT JOIN (
    SELECT customer_id, ROUND(SUM(amount), 2) AS payment_total
    FROM payment
    GROUP BY customer_id
  ) AS p
    ON p.customer_id = c.customer_id
  WHERE c.email IS NOT NULL
    AND trim(c.email) <> ''
),
duplicate_email_groups AS (
  SELECT
    normalized_email,
    DENSE_RANK() OVER (ORDER BY normalized_email) AS duplicate_email_group,
    COUNT(*) AS customer_count,
    COUNT(DISTINCT COALESCE(first_name, '') || char(31) || COALESCE(last_name, '')) AS distinct_name_count,
    SUM(has_history) AS history_count,
    SUM(CASE WHEN has_history = 0 THEN 1 ELSE 0 END) AS no_history_count
  FROM customer_base
  GROUP BY normalized_email
  HAVING COUNT(*) > 1
),
duplicate_customers AS (
  SELECT
    g.duplicate_email_group,
    g.customer_count,
    g.distinct_name_count,
    g.history_count,
    g.no_history_count,
    b.customer_id,
    b.rental_count,
    b.payment_total,
    b.has_history
  FROM customer_base AS b
  INNER JOIN duplicate_email_groups AS g
    ON g.normalized_email = b.normalized_email
)
SELECT
  duplicate_email_group,
  customer_id,
  rental_count,
  payment_total AS total_payment_amount,
  CASE
    WHEN distinct_name_count > 1 THEN 'name spelling differs in this email group; see Section 2'
    WHEN history_count = 0 THEN 'same name, but no record has history; uncertain which record to retain'
    WHEN history_count > 1 THEN 'same name, but multiple records have history; proceeding may risk data loss'
    ELSE 'uncertain; ask before taking action'
  END AS conservative_reason
FROM duplicate_customers
WHERE distinct_name_count > 1
   OR NOT (
     distinct_name_count = 1
     AND history_count = 1
     AND no_history_count >= 1
   )
ORDER BY
  duplicate_email_group,
  customer_id;

SELECT
  'END OF REVIEW: no changes were made. Present the full proposed-change list and wait for explicit confirmation before preparing any customer-table change.' AS final_notice;
