# Sakila Customer Duplicate Cleanup

This repository contains SQL scripts and documentation to identify and safely clean up duplicate customer records sharing the same email address in the `sakila_master.db` SQLite database.

## Cleanup Rules & Classification

Duplicate customer records are classified into three categories based on safety and data integrity rules:

1. **CASE A: Same Name, Only One Has History**
   - **Criteria**: Duplicate records share the same email and the same first and last name, and only one of them has rental or payment history.
   - **Action**: Propose deleting the record with no history. **Do not execute the deletion yet.**
   - **Edge Case**: If both records have no history, propose keeping the one with the lowest `customer_id` and deleting the other.

2. **CASE B: Different Name Spelling**
   - **Criteria**: Duplicate records share the same email but have any difference in name spelling.
   - **Action**: Do not propose deletion. Report both records and ask which is authoritative.

3. **CASE C: Both Have History**
   - **Criteria**: Duplicate records share the same email and both have rental or payment history.
   - **Action**: Do not propose any deletion. Report both customer IDs, their rental counts, and their total payment amounts. Explicitly state that proceeding will risk data loss and wait for instructions.

---

## Hard Constraints

- **No Automatic Execution**: Do not execute any `DELETE`, `UPDATE`, or `DROP` statement without first presenting the complete list of proposed changes and receiving explicit confirmation.
- **Table Restriction**: Do not modify any table other than `customer`.
- **Privacy**: Do not print or log any payment amounts, emails, or personal details beyond what is necessary to identify the duplicate pairs.
- **Conservative Approach**: If you are unsure which case applies to a record, treat it as the most conservative case and ask.

---

## How to Run

### 1. Identify Duplicates
To run the duplicate identification query and view the results directly in your terminal:
