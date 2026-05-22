---
description: Seed dummy expenses for a user. Usage: /seed-expenses <user_id> <count> <months>
argument-hint: "<user_id> <count> <months>"
allowed-tools: Read, Bash(python3:*)
---

Read database/db.py to understand the expenses table schema and the get_db() helper.

The command arguments are: $ARGUMENTS
Parse them as three positional values: user_id, count, months.
- user_id: integer — the user to attach expenses to
- count: integer — total number of expense rows to insert
- months: integer — how many past months to spread the expenses across (starting from today)

Then write and run a Python script using Bash that:

1. Validates the arguments:
   - All three must be present and numeric, else print usage and exit.
   - Verify the user_id exists in the users table; exit with a clear error if not.

2. Generates `count` realistic expense records spread randomly across the last `months` months:
   - amount: realistic float for the category (e.g. Food 80–600, Transport 20–200, Bills 500–3000, Health 100–800, Entertainment 50–400, Shopping 200–2000, Other 30–300) — in INR
   - category: random from [Food, Transport, Bills, Health, Entertainment, Shopping, Other]
   - date: random date within the last `months` months, formatted YYYY-MM-DD
   - description: short realistic description matching the category (e.g. "Swiggy order", "Uber ride", "Electricity bill", "Apollo pharmacy", "BookMyShow tickets", "Amazon order", "Miscellaneous")
   - created_at: current datetime

3. Inserts all records in a single executemany call using the get_db() pattern from db.py.

4. Prints a confirmation table:
   - Total inserted
   - Date range covered
   - Breakdown by category (category: count)