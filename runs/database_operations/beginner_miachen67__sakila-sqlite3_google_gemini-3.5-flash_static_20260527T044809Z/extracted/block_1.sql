-- sql/cleanup.sql
-- This script completely removes all tables, views, and triggers from the Sakila database.

PRAGMA foreign_keys = OFF;

-- Drop Views
DROP VIEW IF EXISTS customer_list;
DROP VIEW IF EXISTS film_list;
DROP VIEW IF EXISTS nicer_but_slower_film_list;
DROP VIEW IF EXISTS sales_by_film_category;
DROP VIEW IF EXISTS sales_by_store;
DROP VIEW IF EXISTS staff_list;

-- Drop Tables
DROP TABLE IF EXISTS payment;
DROP TABLE IF EXISTS rental;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS film_category;
DROP TABLE IF EXISTS film_actor;
DROP TABLE IF EXISTS film_text;
DROP TABLE IF EXISTS film;
DROP TABLE IF EXISTS language;
DROP TABLE IF EXISTS category;
DROP TABLE IF EXISTS customer;
DROP TABLE IF EXISTS staff;
DROP TABLE IF EXISTS store;
DROP TABLE IF EXISTS address;
DROP TABLE IF EXISTS city;
DROP TABLE IF EXISTS country;
DROP TABLE IF EXISTS actor;

-- Re-enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Reclaim unused space
VACUUM;
