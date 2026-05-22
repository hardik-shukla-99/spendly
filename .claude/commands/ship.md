---
description: Create a branch, commit all changes, and push. Usage: /ship <branch-name> <commit-message>
allowed-tools: Bash(git:*)
---

The user has provided arguments: $ARGUMENTS

Parse the arguments as: <branch-name> <commit-message>
- The first word is the branch name (e.g. feat/login)
- Everything after the first word is the commit message

If no arguments are provided, print:
  Usage: /ship <branch-name> <commit-message>
  Example: /ship feat/login "add user login flow"
Then stop.

If only a branch name is provided with no commit message, print:
  Error: commit message is required.
  Usage: /ship <branch-name> <commit-message>
Then stop.

Otherwise run the following git commands in sequence, stopping and reporting any error:

1. git checkout -b <branch-name>
2. git add .
3. git commit -m "<commit-message>"
4. git push -u origin <branch-name>

After each step print a one-line status so the user can follow along.
At the end print the branch name and the full remote URL returned by git push.