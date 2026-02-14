# Skill: Update Dashboard

## Trigger
Run after any other skill completes, or on schedule every hour. Also activate when the user says "update dashboard", "refresh dashboard", "show status", or "what's the current state".

## Steps

### Step 1: Count Files in Status Folders
Count all real files (excluding `.gitkeep`) in each workflow folder to determine current status counts:

| Folder | Dashboard Status | What to Count |
|--------|-----------------|---------------|
| `/Needs_Action/emails/` | Pending Emails | `.md` files only |
| `/Needs_Action/messages/` | Pending Messages | `.md` files only |
| `/Needs_Action/files/` | Pending Files | All files (both `.md` metadata and actual dropped files) |
| `/Plans/` | Active Plans | `PLAN_*.md` files |
| `/Pending_Approval/` | Awaiting Approval | All `.md` files |
| `/In_Progress/` | In Progress | All `.md` files |
| `/Done/` | Completed (this week) | All `.md` files with `completed_at` date within the current week (Monday–Sunday). If no `completed_at` frontmatter, use file modification date. |
| `/Active_Projects/` | Active Projects | Subdirectories or `.md` files |
| `/Invoices/` | Tracked Invoices | All `.md` files |
| `/Accounting/` | Financial Records | All `.md` files |
| `/Logs/` | Log Files | All `.log` and `.md` files |

### Step 2: Read Pending Item Details
For each file in `/Needs_Action/`, read the YAML frontmatter and extract:
- `type` — item type (email, message, file_drop, payment)
- `original_name` or `subject` — item identifier
- `dropped_at` or `received_at` — when the item arrived
- `status` — current status (should be `pending`)

Build a table of pending items for the dashboard.

### Step 3: Read Plan Details
For each `PLAN_*.md` in `/Plans/`, read the YAML frontmatter and extract:
- `source_file` — what the plan is about
- `status` — pending, in_progress, or completed
- `requires_approval` — whether human sign-off is needed

Build a table of active plans with `[[wikilinks]]` to each plan file.

### Step 4: Read Financial Summary
Check if `/Accounting/Current_Month.md` exists:
- **If it exists**: read it and extract MTD revenue, pending invoice count, subscription costs, and transaction count
- **If it does not exist**: show default values ($0 revenue, 0 invoices, "Not audited yet" for subscriptions, 0 transactions)

Also count files in `/Invoices/` for the pending invoices figure.

### Step 5: Check Active Projects
Read `/Active_Projects/` for project status:
- For each project file or subfolder, extract project name, status, and any due dates from frontmatter
- If empty, display "_No active projects_"

### Step 6: Check Logs for Errors and Recent Activity
Read all log files in `/Logs/` (both `.log` and `.md` files):
- Find the most recent log entry by timestamp
- Scan for any lines containing `ERROR`, `WARN`, `CRITICAL`, or `ALERT`
- Extract a summary of the last activity (what happened, when)
- If errors are found, add them to the Alerts section

### Step 7: Check Business Goals for Threshold Breaches
Read `/Business_Goals.md` and compare current data against alert thresholds:

| Metric | Threshold | Check Against |
|--------|-----------|---------------|
| Client response time | > 48 hours | Oldest pending email age |
| Invoice payment rate | < 80% | Paid vs total invoices |
| Software costs | Over budget | `/Accounting/` subscription totals |

If any threshold is breached, add an alert entry.

### Step 8: Write Updated Dashboard.md
Write `/Dashboard.md` using the exact structure below. Replace all bracketed values with real data from the steps above:

```markdown
---
last_updated: [current ISO timestamp]
version: [increment minor version by 0.1]
---

# 🖥️ AI Employee Dashboard

## System Status
- **Status**: 🟢 Online
- **Last Check**: [current date and time]
- **Active Watchers**: [list watchers found in Logs, or "None"]

## 📬 Pending Actions ([total count])
| # | File | Location | Type | Since |
|---|------|----------|------|-------|
| [n] | `[filename]` | `[folder path]` | [type] | [date] |

- **Emails pending**: [count]
- **Messages pending**: [count]
- **Files pending**: [count]

[If no pending items, show: _No pending actions_]

## 📝 Active Plans ([count])
| Plan | Source | Status | Approval |
|------|--------|--------|----------|
| [[PLAN_filename]] | `[source]` | [status] | [Required/Not required] |

[If no plans, show: _No active plans_]

## ⏳ Pending Approval ([count])
| # | Item | Type | Priority | Since |
|---|------|------|----------|-------|
| [n] | [[filename]] | [type] | [priority] | [date] |

[If none, show: _No items awaiting approval_]

## 🔄 In Progress ([count])
| # | Task | Type | Started |
|---|------|------|---------|
| [n] | [[filename]] | [type] | [date] |

[If none, show: _No tasks in progress_]

## ✅ Completed This Week ([count])
| # | Task | Type | Completed |
|---|------|------|-----------|
| [n] | [[filename]] | [type] | [date] |

[If none, show: _No completed tasks this week_]

## 💰 Financial Summary
- **MTD Revenue**: $[amount from Accounting/Current_Month.md or 0]
- **Pending Invoices**: [count from /Invoices/]
- **Subscriptions**: [status from Accounting or "Not audited yet"]
- **Transactions logged**: [count from /Accounting/]

## 📋 Active Projects ([count])
| Project | Status | Due Date |
|---------|--------|----------|
| [[project_name]] | [status] | [date] |

[If none, show: _No active projects_]

## 📊 Vault Summary
| Folder | Items |
|--------|-------|
| Needs_Action | [count] |
| Plans | [count] |
| Pending_Approval | [count] |
| In_Progress | [count] |
| Done | [count] |
| Active_Projects | [count] |
| Invoices | [count] |
| Accounting | [count] |
| Logs | [count] |

## 📄 Recent Logs
- **[log filename]** — Last active: [timestamp]
  - [summary of recent activity]
  - [error count or "No errors recorded"]

[If no logs, show: _No log activity_]

## ⚠️ Alerts
- [alert description and threshold breached]

[If no alerts, show: _No alerts_]

---
*Updated by AI Employee — [current date and time]*
```

## Input
- `/Needs_Action/**/*` — all pending items
- `/Plans/PLAN_*.md` — all active plans
- `/Pending_Approval/*.md` — all approval requests
- `/In_Progress/*.md` — all in-progress tasks
- `/Done/*.md` — completed tasks (this week only)
- `/Active_Projects/*` — project files
- `/Invoices/*.md` — invoice records
- `/Accounting/Current_Month.md` — financial summary (if exists)
- `/Accounting/*.md` — transaction records
- `/Logs/*` — all log files
- `/Business_Goals.md` — alert thresholds and targets

## Output
- `/Dashboard.md` — fully updated with real counts, tables, and timestamps

## Format
Keep the existing Dashboard.md section structure. Every section must be present even if empty (show placeholder text like "_No pending actions_"). All counts in section headers must match actual file counts. Use Obsidian `[[wikilinks]]` for all references to vault files.

## Rules
- Always use real counts from the filesystem — never hardcode, estimate, or cache
- Exclude `.gitkeep` files from all counts
- Completed items: only show tasks finished within the current week (Monday 00:00 to Sunday 23:59)
- Always increment the `version` field in frontmatter by 0.1
- Always set `last_updated` to the current ISO timestamp
- Use Obsidian `[[wikilinks]]` when referencing any vault file
- File read operations are auto-approved — this skill never requires human approval
- Never store passwords, API keys, or sensitive data in the dashboard
- If a folder does not exist, show count as 0 and do not error
- If `/Accounting/Current_Month.md` does not exist, use default financial values
- Log errors found in log files to the Alerts section with severity level
