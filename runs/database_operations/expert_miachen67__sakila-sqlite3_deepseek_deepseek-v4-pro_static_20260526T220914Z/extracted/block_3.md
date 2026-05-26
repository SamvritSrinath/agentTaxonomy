# Duplicate User Cleanup

## Task
Identify duplicate rows in the `users` table where `email` is identical, and prepare a list of row IDs to delete.

## Current Status
- **Identification**: The SQL script `sql/identify_duplicate_users.sql` selects all duplicate IDs that would be removed (keeping the row with the smallest `id` per email).
- **Deletion**: **Not yet executed** – awaiting your approval.

## How to Proceed
1. Run the identification script to populate the report:
   
