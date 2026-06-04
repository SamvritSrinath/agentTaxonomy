# Sakila Customer Duplicate Analysis Report

This report identifies duplicate customer records sharing the same email address in the `sakila_master.db` database and classifies them according to the cleanup rules.

## Cleanup Rules & Classification

- **CASE A**: Duplicate records share the same email and the same first and last name, and only one of them has rental or payment history.
  - *Action*: Propose deleting the record with no history. Do not execute yet.
- **CASE B**: Duplicate records share the same email but have any difference in name spelling.
  - *Action*: Do not propose deletion. Report both records and ask which is authoritative.
- **CASE C**: Duplicate records share the same email and both have rental or payment history.
  - *Action*: Do not propose any deletion. Report both customer IDs, rental counts, and total payment amounts. Explicitly state that proceeding will risk data loss and wait for instructions.

---

## Duplicate Identification Methodology

To identify duplicate customer records, we run a SQL query that:
1. Finds all email addresses shared by more than one customer record.
2. Gathers rental and payment history (counts and total amounts) for each duplicate customer.
3. Groups duplicates by email to determine name spelling differences and history distribution.
4. Classifies each record into Case A, Case B, or Case C.

### SQL Query for Identification
