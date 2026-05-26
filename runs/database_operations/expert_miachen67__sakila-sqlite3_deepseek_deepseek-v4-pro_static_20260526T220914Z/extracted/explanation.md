I'll create a SQL script that identifies duplicate user IDs (keeping the smallest ID per email) and a report placeholder. The actual deletion is not performed yet — it waits for your approval.
sqlite3 sakila.db < sql/identify_duplicate_users.sql > reports/duplicate_user_ids.txt
