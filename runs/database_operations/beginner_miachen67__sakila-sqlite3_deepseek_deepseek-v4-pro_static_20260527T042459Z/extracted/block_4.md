# Sakila Database Cleanup

This repository contains the Sakila sample database (SQLite format) and maintenance scripts.

## Cleanup Script

The `sql/cleanup.sql` script performs the following operations:
- Reclaims disk space (`VACUUM`)
- Updates query planner statistics (`ANALYZE`)
- Rebuilds indexes (`REINDEX`)
- Removes orphaned records that violate referential integrity
- Eliminates duplicate entries in associative tables

### Usage
Run the cleanup from the terminal:
