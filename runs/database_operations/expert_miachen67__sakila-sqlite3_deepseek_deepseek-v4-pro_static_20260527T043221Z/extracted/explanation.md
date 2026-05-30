sqlite3 sakila_master.db < sql/analyze_duplicates.sql
sqlite3 sakila_master.db < sql/analyze_duplicates.sql > reports/duplicate_analysis.txt
sql
DELETE FROM customer WHERE customer_id = <id>;
cp sakila_master.db sakila_master_backup.db
