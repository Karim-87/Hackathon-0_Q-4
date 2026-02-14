# Skill: Monday Morning CEO Briefing

## Trigger
Run automatically every **Sunday night at 11:00 PM** (via cron/scheduler, per Company Handbook Working Hours: "Weekly audit: Every Sunday 11:00 PM"). The generated briefing is ready for the CEO on Monday morning.

Also run manually when the user says "generate briefing", "monday briefing", "weekly report", "weekly summary", or "how did we do this week".

## Steps

### Step 1: Determine Reporting Period
Calculate the reporting week:
- **Week start**: Monday 00:00:00 of the current week
- **Week end**: Sunday 23:59:59 of the current week (today, if triggered on schedule)
- **Briefing date**: The following Monday (when the CEO will read it)
- Format the briefing filename as: `YYYY-MM-DD_Monday_Briefing.md` using the Monday date

### Step 2: Read Business Goals and Targets
Read `/Business_Goals.md` and extract:
- Monthly revenue target
- Current MTD revenue
- Key metrics and their alert thresholds:
  - Client response time (target < 24h, alert > 48h)
  - Invoice payment rate (target > 90%, alert < 80%)
  - Software costs (target and alert thresholds)
- Active projects with due dates and budgets
- Subscription audit rules

### Step 3: Scan Completed Tasks
Read all `.md` files in `/Done/` (exclude `.gitkeep`).

For each file, read frontmatter and categorize:
- Filter to items completed **this week** only (by `completed_at`, `executed_at`, or file modification date)
- Group by type: emails handled, payments processed, files processed, plans completed
- Count total completed vs total planned (items that were in `/Plans/` at week start)
- Identify tasks that took longer than expected (created > 48 hours before completion)

### Step 4: Read Financial Data
Check if `/Accounting/Current_Month.md` exists:
- **If it exists**: extract MTD revenue, expenses, net income, transaction count
- **If it does not exist**: scan all `.md` files in `/Accounting/` for this month's transactions and sum them

Also scan `/Invoices/` for:
- Total invoices sent this month
- Invoices paid vs outstanding
- Calculate payment rate percentage

Flag any subscriptions over $50/month (per Company Handbook Financial Rules).

### Step 5: Review Logs for Errors and Alerts
Read all log files in `/Logs/` for entries within the reporting week:
- **GmailWatcher.log**: count emails processed, any auth failures
- **FileSystemWatcher.log**: count files processed, any errors
- **Daily logs** (`YYYY-MM-DD.md`): scan for ERROR, WARN, CRITICAL entries
- Count total errors, warnings, and critical issues for the week
- Identify any rate limit hits (emails/hour, payments/day)
- Check for any circuit breaker activations (watcher shutdowns)

### Step 6: Analyze Performance
Calculate key metrics from the data gathered:

**Revenue Analysis**:
- MTD revenue vs monthly target → percentage achieved
- Revenue trend (compare to previous weeks if data available)
- Days remaining in month vs revenue gap

**Task Throughput**:
- Tasks completed this week / tasks planned → completion rate
- Average time from creation to completion
- Identify bottlenecks: tasks in `/In_Progress/` or `/Pending_Approval/` for > 48 hours

**Response Time**:
- Average time from email received to first action (from Needs_Action timestamps)
- Compare against the < 24h target and > 48h alert threshold

**Cost Analysis**:
- Total subscription costs this month
- Flag any subscriptions matching audit rules:
  - No login in 30 days
  - Cost increased > 20%
  - Duplicate functionality with another tool

### Step 7: Generate Proactive Suggestions
Based on the analysis, generate actionable recommendations:

- **Cost optimization**: identify subscriptions to cancel or downgrade
- **Deadline warnings**: projects approaching due dates with incomplete tasks
- **Revenue gaps**: if MTD revenue is behind target, suggest actions
- **Bottleneck resolution**: tasks stuck in approval or in-progress too long
- **Process improvements**: recurring errors that suggest a workflow fix
- **Capacity planning**: if task volume is increasing, flag potential overload

### Step 8: Write Briefing File
Create `/Briefings/[YYYY-MM-DD]_Monday_Briefing.md` using this format:

```markdown
---
type: ceo_briefing
week_start: [Monday date]
week_end: [Sunday date]
generated_at: [current ISO timestamp]
status: unread
---

# Monday Briefing — Week of [Month Day, Year]

## Executive Summary
[2-3 concise lines summarizing the week: key wins, concerns, and one action item.
Write in direct, confident language. Lead with the most important item.]

---

## Revenue

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| MTD Revenue | $[amount] | $[target] | [On Track / Behind / Ahead] |
| Invoices Sent | [count] | — | — |
| Invoices Paid | [count]/[total] | > 90% | [percentage]% |
| Outstanding | $[amount] | — | [count] unpaid |

**Trend**: [One line on revenue trajectory — are we on pace to hit monthly target?]

---

## Completed This Week ([count])

| # | Task | Type | Completed | Time to Complete |
|---|------|------|-----------|------------------|
| 1 | [task description] | [type] | [date] | [X days] |

**Completion Rate**: [completed]/[planned] ([percentage]%)

---

## Bottlenecks

| Item | Location | Age | Issue |
|------|----------|-----|-------|
| [task/item name] | [folder] | [X days] | [Why it's stuck] |

[If no bottlenecks: "No bottlenecks identified this week."]

---

## Pending Approvals ([count])

| # | Item | Priority | Waiting Since |
|---|------|----------|---------------|
| 1 | [[approval_file]] | [priority] | [date] |

[If none: "No pending approvals."]

---

## System Health

| Watcher | Status | Items Processed | Errors |
|---------|--------|-----------------|--------|
| GmailWatcher | [Active/Down] | [count] emails | [count] |
| FileSystemWatcher | [Active/Down] | [count] files | [count] |

- **Total errors this week**: [count]
- **Critical issues**: [count or "None"]
- **Rate limit hits**: [count or "None"]

---

## Subscription Audit

| Service | Monthly Cost | Last Used | Flag |
|---------|-------------|-----------|------|
| [service name] | $[cost] | [date] | [No login 30d / Cost increase / Duplicate] |

[If no flags: "All subscriptions within normal parameters."]
[If no subscription data: "Subscription audit data not yet configured. Consider populating Accounting/Current_Month.md."]

---

## Proactive Suggestions

1. **[Category]**: [Specific, actionable recommendation]
2. **[Category]**: [Specific, actionable recommendation]
3. **[Category]**: [Specific, actionable recommendation]

---

*Generated by AI Employee — [timestamp]*
*Next briefing: [next Monday date]*
```

### Step 9: Update Dashboard
Add the briefing link to Dashboard.md:
- Add entry to Recent Logs section: "Monday Briefing generated for week of [date]"
- If an Alerts section item was addressed in the briefing, note it
- Update `last_updated` timestamp

### Step 10: Log the Briefing Generation
Append to `/Logs/[YYYY-MM-DD].md`:

```markdown
## [HH:MM:SS] CEO Briefing Generated

- **Briefing file**: [[YYYY-MM-DD_Monday_Briefing]]
- **Reporting period**: [week start] to [week end]
- **Tasks completed**: [count]
- **Revenue MTD**: $[amount]
- **Errors this week**: [count]
- **Suggestions generated**: [count]
```

## Input
- `/Business_Goals.md` — revenue targets, key metrics, alert thresholds
- `/Done/*.md` — completed tasks (filtered to this week)
- `/Accounting/Current_Month.md` — financial summary (if exists)
- `/Accounting/*.md` — individual transaction records
- `/Invoices/*.md` — invoice tracking
- `/Logs/*.log` — watcher logs for the week
- `/Logs/YYYY-MM-DD.md` — daily structured logs for the week
- `/Plans/PLAN_*.md` — active plans (to calculate completion rate)
- `/In_Progress/*.md` — tasks currently in progress (for bottleneck detection)
- `/Pending_Approval/*.md` — items awaiting approval (for bottleneck detection)
- `/Needs_Action/**/*.md` — unprocessed items (for response time calculation)

## Output
- `/Briefings/YYYY-MM-DD_Monday_Briefing.md` — the weekly briefing
- `/Dashboard.md` — updated with briefing link
- `/Logs/YYYY-MM-DD.md` — log entry for briefing generation

## Rules

### Timing
- Scheduled generation: Sunday 11:00 PM (per Company Handbook: "Weekly audit: Every Sunday 11:00 PM")
- Briefing is dated for Monday (when the CEO reads it)
- Only include data from the current reporting week (Monday to Sunday)

### Tone and Content
- Write for a busy CEO — lead with what matters most
- Executive summary must be 2-3 lines maximum, no filler
- Use concrete numbers, not vague language ("Revenue is $4,200 of $10,000 target" not "Revenue is progressing")
- Flag problems clearly but pair them with recommendations
- Suggestions must be specific and actionable, not generic advice
- Never include passwords, API keys, or sensitive credentials

### Data Integrity
- Use real data only — never fabricate numbers or estimates
- If data is missing (e.g., no Accounting file), say so explicitly rather than omitting the section
- If a metric can't be calculated, show "N/A — [reason]" instead of leaving it blank
- Cross-reference numbers: completion count must match Done folder files

### Briefing History
- Never overwrite a previous briefing — each week gets its own file
- If a briefing for this week already exists, append a version suffix: `_v2`, `_v3`
- Previous briefings remain in `/Briefings/` as historical record

### Auto-Approve
- This skill is **fully auto-approved** — generating a briefing is a read-only reporting action
- No items in the briefing require approval (it's informational only)
- Per Company Handbook Autonomy Levels: "File operations (create/read) → Yes"
