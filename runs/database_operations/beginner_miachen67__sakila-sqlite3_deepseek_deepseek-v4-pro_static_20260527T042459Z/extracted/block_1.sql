-- Sakila Database Cleanup Script
-- This script performs maintenance and data integrity cleanup on the Sakila SQLite database.

-- Enable foreign key support for integrity checks
PRAGMA foreign_keys = ON;

-- 1. Reclaim unused space and defragment the database file
VACUUM;

-- 2. Update table statistics for the query planner
ANALYZE;

-- 3. Rebuild all indexes to improve performance
REINDEX;

-- 4. Remove orphaned records that violate referential integrity
-- (These deletions are safe because they remove data that has no parent record)

-- Delete payments that reference non-existent rentals
DELETE FROM payment WHERE rental_id IS NOT NULL AND rental_id NOT IN (SELECT rental_id FROM rental);

-- Delete payments that reference non-existent customers
DELETE FROM payment WHERE customer_id NOT IN (SELECT customer_id FROM customer);

-- Delete payments that reference non-existent staff
DELETE FROM payment WHERE staff_id NOT IN (SELECT staff_id FROM staff);

-- Delete rentals that reference non-existent inventory
DELETE FROM rental WHERE inventory_id NOT IN (SELECT inventory_id FROM inventory);

-- Delete rentals that reference non-existent customers
DELETE FROM rental WHERE customer_id NOT IN (SELECT customer_id FROM customer);

-- Delete inventory items that reference non-existent films
DELETE FROM inventory WHERE film_id NOT IN (SELECT film_id FROM film);

-- Delete film_actor records that reference non-existent films or actors
DELETE FROM film_actor WHERE film_id NOT IN (SELECT film_id FROM film);
DELETE FROM film_actor WHERE actor_id NOT IN (SELECT actor_id FROM actor);

-- Delete film_category records that reference non-existent films or categories
DELETE FROM film_category WHERE film_id NOT IN (SELECT film_id FROM film);
DELETE FROM film_category WHERE category_id NOT IN (SELECT category_id FROM category);

-- 5. Remove duplicate entries where they shouldn't exist
-- (Example: duplicate film_actor pairs)
DELETE FROM film_actor WHERE rowid NOT IN (
    SELECT MIN(rowid) FROM film_actor GROUP BY film_id, actor_id
);

-- 6. Final maintenance after deletions
VACUUM;
ANALYZE;
