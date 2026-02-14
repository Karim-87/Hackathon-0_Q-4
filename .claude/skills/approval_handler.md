# Skill: Approval Handler

## Trigger
Run when the user says "check approvals", "process approvals", "handle approvals", or "what needs my approval". Also run automatically:
- After `process_inbox` creates new approval files
- When a file is detected in `/Approved/` or `/Rejected/` (user has acted on an approval)
- On schedule: check every hour for expired approval requests

## Overview
This skill manages the full Human-in-the-Loop approval lifecycle:
1. **Pending** — item awaits human decision in `/Pending_Approval/`
2. **Approved** — human moved file to `/Approved/`, ready to execute
3. **Rejected** — human moved file to `/Rejected/`, log and archive

The human approves or rejects by simply **moving the file** between Obsidian folders — no code, no CLI, just drag and drop.

## Steps

### Step 1: Scan Pending Approvals
Read all `.md` files in `/Pending_Approval/` (exclude `.gitkeep` and `TEMPLATE_approval.md`).

For each file, read the YAML frontmatter and extract:
- `type` — the approval type (approval_request)
- `action` — what action is being requested (email_send, payment, social_post, file_delete)
- `created` — when the request was created
- `expires` — when the request expires (24 hours from creation)
- `status` — should be `pending`
- `priority` — low, medium, or high

### Step 2: Check for Expired Approvals
For each pending approval, compare `expires` timestamp against the current time:
- **If expired**:
  1. Update frontmatter: set `status: expired`
  2. Move the file to `/Rejected/`
  3. Add `expired_at: [current timestamp]` and `rejection_reason: auto_expired` to frontmatter
  4. Log the expiration to `/Logs/[YYYY-MM-DD].md`
- **If not expired**: leave in `/Pending_Approval/` for human review

### Step 3: Present Pending Approvals to User
For all non-expired pending approvals, present a summary to the user:

```
## Pending Approvals ([count])

| # | Action | Priority | Created | Expires | File |
|---|--------|----------|---------|---------|------|
| 1 | [action] | [priority] | [date] | [date] | [[filename]] |

To approve: move the file to /Approved/
To reject: move the file to /Rejected/
```

Sort by priority (high first), then by creation date (oldest first).

### Step 4: Process Approved Items
Scan `/Approved/` for `.md` files (exclude `.gitkeep`). For each approved file:

1. Read the YAML frontmatter to determine the `action` type
2. Update frontmatter:
   - Set `status: approved`
   - Add `approved_at: [current timestamp]`
3. Execute the approved action based on `action` type:

**`email_send`**:
   - Read the draft email from the `source_file` reference
   - Validate recipient, subject, and body are present
   - Check rate limit: have fewer than 10 emails been sent this hour?
   - If DRY_RUN=true: log "DRY RUN: would send email to [recipient]" and move to `/Done/`
   - If DRY_RUN=false: execute the email send (via watcher/API), then move to `/Done/`

**`payment`**:
   - Read payment details: amount, recipient, due date
   - Check rate limit: have fewer than 3 payments been made today?
   - Log the transaction to `/Accounting/` with full details
   - If DRY_RUN=true: log "DRY RUN: would process payment of $[amount] to [recipient]" and move to `/Done/`
   - If DRY_RUN=false: execute payment (via watcher/API), then move to `/Done/`

**`social_post`**:
   - Read post content, platform, and scheduled time
   - If DRY_RUN=true: log "DRY RUN: would post to [platform]" and move to `/Done/`
   - If DRY_RUN=false: schedule the post (via watcher/API), then move to `/Done/`

**`file_delete`**:
   - Read the target file path from `source_file`
   - Verify the file exists before attempting deletion
   - If DRY_RUN=true: log "DRY RUN: would delete [filepath]" and move to `/Done/`
   - If DRY_RUN=false: delete the target file, then move approval file to `/Done/`

4. After execution, update the approval file frontmatter:
   - Add `executed_at: [current timestamp]`
   - Set `status: executed`
5. Move the approval file from `/Approved/` to `/Done/`

### Step 5: Process Rejected Items
Scan `/Rejected/` for `.md` files (exclude `.gitkeep`). For each rejected file:

1. Read the YAML frontmatter
2. Update frontmatter:
   - Set `status: rejected`
   - Add `rejected_at: [current timestamp]`
   - If no `rejection_reason` exists, set `rejection_reason: human_rejected`
3. If the rejected item has a corresponding plan in `/Plans/`:
   - Update the plan's frontmatter: set `status: cancelled`
4. Log the rejection to `/Logs/[YYYY-MM-DD].md`:
   ```
   [HH:MM:SS] REJECTED: [action] — [filename] — Reason: [rejection_reason]
   ```
5. Leave the file in `/Rejected/` as an audit trail (never delete rejected items)

### Step 6: Update Dashboard
After processing all three folders, trigger the `update_dashboard` skill to refresh:
- Pending Approval count
- Completed count (newly executed items in `/Done/`)
- Alerts (any expired approvals)

### Step 7: Log All Actions
Append to `/Logs/[YYYY-MM-DD].md`:

```markdown
## [HH:MM:SS] Approval Handler Run

### Summary
- Pending approvals reviewed: [count]
- Expired (auto-rejected): [count]
- Approved and executed: [count]
- Rejected: [count]

### Details
| File | Action | Result | Timestamp |
|------|--------|--------|-----------|
| [filename] | [action] | [approved/rejected/expired] | [time] |
```

## Input
- `/Pending_Approval/*.md` — items awaiting human decision
- `/Approved/*.md` — items approved by human, ready to execute
- `/Rejected/*.md` — items rejected by human, to log and archive
- `/Plans/PLAN_*.md` — to update linked plans on rejection
- `/Company_Handbook.md` — for rate limits and security rules
- `/Logs/*.md` — to check rate limits (emails/hour, payments/day)
- `/Accounting/*.md` — to log financial transactions

## Output
- `/Done/*.md` — executed approval files moved here after completion
- `/Rejected/*.md` — rejected and expired items archived here
- `/Accounting/*.md` — transaction records for approved payments
- `/Logs/YYYY-MM-DD.md` — structured log of all approval actions
- `/Dashboard.md` — updated counts (via update_dashboard skill)

## Rules

### Approval Workflow
- The human is ALWAYS the decision maker — the AI never approves on its own
- The only way to approve is to move the file to `/Approved/`
- The only way to reject is to move the file to `/Rejected/`
- Expired approvals are auto-rejected after 24 hours with reason `auto_expired`
- Never re-process an approval that has already been executed (`status: executed`)
- Never re-process a rejection that has already been logged (`status: rejected`)
- Never delete files from `/Rejected/` — they serve as a permanent audit trail

### Rate Limits (from Company Handbook)
- Maximum 10 emails per hour — check `/Logs/` for recent email sends before executing
- Maximum 3 payments per day — check `/Logs/` and `/Accounting/` before executing
- If a rate limit would be exceeded, do NOT execute. Set `status: rate_limited` and leave in `/Approved/` with a note explaining when it can be retried

### Safety Rules (from Company Handbook)
- Always use DRY_RUN mode during testing — check the `.env` or environment config
- Never store passwords or API keys in approval files
- All sensitive actions require Human-in-the-Loop — this skill enforces that
- Log every action to `/Logs/` — no silent operations

### Priority Handling
- **High priority**: present first, warn if approaching expiration (< 4 hours remaining)
- **Medium priority**: present in normal order
- **Low priority**: present last, acceptable to expire if not reviewed

### Action-Specific Rules
| Action | Handbook Rule | Extra Checks |
|--------|--------------|--------------|
| `email_send` | New contacts always need approval | Check recipient against known contacts |
| `payment` | ALL payments need approval | Log to `/Accounting/`, check daily limit |
| `social_post` | Approval needed | Verify scheduled time is in the future |
| `file_delete` | Always needs approval | Verify file exists, never delete vault system files |
