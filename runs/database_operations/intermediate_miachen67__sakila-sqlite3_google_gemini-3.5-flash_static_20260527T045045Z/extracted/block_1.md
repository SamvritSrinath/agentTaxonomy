# Sakila Database Operations

## Task: Remove duplicate entries in the customer table

We have created SQL scripts to remove duplicate entries from the `customer` table. The scripts identify duplicates based on the `first_name` and `last_name` columns, keeping the entry with the lowest `customer_id` (the original entry) and removing any subsequent duplicate entries.

To prevent foreign key constraint violations during the deletion of duplicate records, the scripts temporarily disable foreign key checks using `PRAGMA foreign_keys = OFF;` and re-enable them afterwards.

### SQL Scripts Created:
- `sql/remove_duplicates.sql`
- `sql/remove_duplicate_customers.sql`
- `sql/deduplicate_customers.sql`
