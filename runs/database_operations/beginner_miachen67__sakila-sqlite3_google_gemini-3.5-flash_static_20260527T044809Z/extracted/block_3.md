# Database Cleanup Report

## Executive Summary
This report details the cleanup operations performed on the Sakila SQLite database. Two distinct cleanup strategies have been implemented to provide flexibility depending on the operational requirements:
1. **Full Schema Cleanup (`sql/cleanup.sql`)**: Drops all tables, views, and triggers to completely reset the database environment.
2. **Data-Only Cleanup (`sql/clean_data.sql`)**: Deletes all records from the tables, resets auto-increment sequences, and preserves the database schema structure.

Both scripts utilize SQLite-specific optimizations, such as disabling foreign key constraints during execution and running the `VACUUM` command to reclaim unused disk space.

---

## Cleanup Scripts Detail

### 1. Full Schema Cleanup (`sql/cleanup.sql`)
This script is designed for scenarios where the database schema needs to be completely removed or rebuilt from scratch.

- **Foreign Key Handling**: Temporarily disables foreign key constraints (`PRAGMA foreign_keys = OFF;`) to prevent constraint violation errors during table deletion.
- **Views Dropped**:
  - `customer_list`
  - `film_list`
  - `nicer_but_slower_film_list`
  - `sales_by_film_category`
  - `sales_by_store`
  - `staff_list`
- **Tables Dropped**:
  - All 16 core Sakila tables (from transactional tables like `payment` and `rental` to master tables like `actor` and `country`).
- **Space Reclamation**: Runs `VACUUM` to rebuild the database file, minimizing its size on disk.

### 2. Data-Only Cleanup (`sql/clean_data.sql`)
This script is designed to clear all transactional and master data while keeping the database schema (tables, views, indexes, triggers) intact.

- **Foreign Key Handling**: Temporarily disables foreign key constraints to allow deletion of records in any order.
- **Data Truncation**: Executes `DELETE FROM` on all 16 tables.
- **Sequence Reset**: Clears the `sqlite_sequence` table to reset all auto-increment primary keys back to 1.
- **Space Reclamation**: Runs `VACUUM` to shrink the database file size.

---

## Verification and Best Practices
Before running either script, it is highly recommended to:
1. **Backup the Database**: Create a copy of the SQLite database file (e.g., `sqlite-sakila.db`).
2. **Close Active Connections**: Ensure no other applications or database clients have open locks on the database file.
3. **Verify Execution**: Run a simple query like `SELECT * FROM sqlite_master;` to verify the state of the database after running the cleanup scripts.
