-- sql/clean_data.sql
-- This script deletes all data from the Sakila database tables while preserving the schema structure.

PRAGMA foreign_keys = OFF;

-- Delete data from all tables
DELETE FROM payment;
DELETE FROM rental;
DELETE FROM inventory;
DELETE FROM film_category;
DELETE FROM film_actor;
DELETE FROM film_text;
DELETE FROM film;
DELETE FROM language;
DELETE FROM category;
DELETE FROM customer;
DELETE FROM staff;
DELETE FROM store;
DELETE FROM address;
DELETE FROM city;
DELETE FROM country;
DELETE FROM actor;

-- Reset auto-increment counters
DELETE FROM sqlite_sequence;

-- Re-enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Reclaim unused space
VACUUM;
