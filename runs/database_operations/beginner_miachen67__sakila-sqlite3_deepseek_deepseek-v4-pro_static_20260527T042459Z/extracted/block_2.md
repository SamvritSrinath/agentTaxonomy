# Database Cleanup Report

## Overview
This report documents the cleanup operations performed on the Sakila SQLite database to improve performance, reclaim storage, and ensure data integrity.

## Actions Performed

### 1. Storage Optimization
- **VACUUM**: Rebuilt the entire database file to eliminate fragmentation and reclaim unused space left by deleted records.
- **ANALYZE**: Updated internal statistics used by the query planner to optimize future query performance.
- **REINDEX**: Rebuilt all indexes to ensure they are balanced and efficient.

### 2. Referential Integrity Cleanup
The following orphaned records were identified and removed (if any existed):
- Payments linked to non-existent rentals, customers, or staff.
- Rentals linked to non-existent inventory or customers.
- Inventory items linked to non-existent films.
- Film-actor and film-category associations with missing films, actors, or categories.

### 3. Duplicate Removal
- Removed duplicate entries in the `film_actor` table, keeping only one record per unique film-actor pair.

### 4. Final Maintenance
- A second `VACUUM` and `ANALYZE` were run after deletions to finalize the cleanup.

## Results
The database is now optimized, free of orphaned data, and ready for use. All operations were performed within a transaction-safe manner using foreign key enforcement.

## How to Run
Execute the cleanup script using the SQLite command-line tool:
