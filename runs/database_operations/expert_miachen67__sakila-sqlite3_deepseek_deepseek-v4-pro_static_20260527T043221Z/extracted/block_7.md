This file will be populated when you run the analysis script:

  sqlite3 sakila_master.db < sql/analyze_duplicates.sql > reports/duplicate_analysis.txt

The generated report will contain a full breakdown of duplicate customer records grouped
by email, along with proposed actions.
