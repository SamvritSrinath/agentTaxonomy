# Sakila Customer Duplicate Review

This repository contains a read-only workflow for reviewing duplicate `customer` records in `sakila_master.db`.

Duplicate candidates are defined as customer records that share the same email address. The provided SQL does not change data. It only produces review lists so an administrator can decide what to do next.

## Files

- `sql/customer_duplicate_review.sql` — read-only SQLite report for duplicate customers.
- `reports/customer_duplicate_review.md` — template for recording review results and explicit administrator decisions.

## Safety rules implemented

The review script:

- Enables SQLite `query_only` mode.
- Uses `SELECT` statements only.
- Does not run `DELETE`, `UPDATE`, or schema-changing statements.
- Does not modify any table.
- Does not print full email addresses.
- Prints names only when needed to resolve name-spelling conflicts.
- Prints payment totals only when required to assess records that both have history.

## How to run

From the repository root:
