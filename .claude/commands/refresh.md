---
description: Switch to main, pull latest changes, and optionally delete a stale branch. Usage: /refresh [branch-to-delete]
allowed-tools: Bash(git:*)
---

The user has provided arguments: $ARGUMENTS

Parse the arguments as an optional single value: <branch-to-delete>
- If provided, this is the name of a local branch to delete after pulling main.
- If omitted, just sync main with no branch deletion.

Run the following steps in sequence, stopping and reporting any error:

1. Check for uncommitted changes on the current branch:
   - Run: git status --porcelain
   - If output is non-empty, print a warning:
     "Warning: You have uncommitted changes on <current-branch>. Stash or commit them before refreshing."
   - Then stop.

2. Note the current branch name (git branch --show-current) — you'll need it for the summary.

3. Switch to main:
   - Run: git checkout main
   - Print: "✓ Switched to main"

4. Pull latest changes:
   - Run: git pull origin main
   - Capture the output.
   - If "Already up to date." is in the output, print: "✓ Already up to date — no changes pulled"
   - Otherwise print: "✓ Pulled latest changes" followed by a short summary of changed files (the list from git pull output)

5. If a <branch-to-delete> argument was provided:
   - Check whether that branch exists locally: git branch --list <branch-to-delete>
   - If it does not exist, print: "Note: Branch '<branch-to-delete>' not found locally — nothing to delete"
   - If it does exist, delete it: git branch -d <branch-to-delete>
     - If the delete fails (e.g. branch not fully merged), retry with -D and note that it was force-deleted.
     - Print: "✓ Deleted local branch '<branch-to-delete>'"

At the end print a one-line summary:
  "Refreshed main from origin" + (if branch deleted: " · deleted <branch-to-delete>") + (if already up to date: " · already up to date")
