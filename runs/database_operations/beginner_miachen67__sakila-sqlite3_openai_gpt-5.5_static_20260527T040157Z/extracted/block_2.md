# Database Cleanup

This repository now includes `sql/cleanup_database.sql`, a conservative cleanup script for the Sakila SQLite database.

## What the cleanup does

- Enables foreign-key enforcement during cleanup.
- Removes orphaned records from child and relationship tables:
  - `payment`
  - `rental`
  - `inventory`
  - `film_actor`
  - `film_category`
- Removes duplicate many-to-many rows from:
  - `film_actor`
  - `film_category`
- Normalizes text fields by trimming whitespace.
- Converts blank nullable text values to `NULL`.
- Lowercases staff and customer email addresses.
- Normalizes customer `active` values to `0` or `1`.
- Corrects obvious invalid scalar values:
  - negative payment amounts
  - invalid film rental duration/rates/costs
  - invalid film ratings
  - rental return dates earlier than rental dates
  - invalid optional `film.original_language_id` references
- Runs:
  - `PRAGMA foreign_key_check`
  - `PRAGMA integrity_check`
  - `PRAGMA optimize`
  - `VACUUM`

## How to run

From the repository root:
