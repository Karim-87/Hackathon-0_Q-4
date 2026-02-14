# Skill: Execute Approved Actions

## Trigger
Run when a file appears in the `/Approved/` folder. Also activate when the user says "execute approvals", "run approved", "process approved items", or "execute actions".

This skill is the **execution engine** — it only runs actions that a human has explicitly approved by moving a file to `/Approved/`. It never makes approval decisions on its own.

## Steps

### Step 1: Scan Approved Folder
Read all `.md` files in `/Approved/` (exclude `.gitkeep`).

If the folder is empty, report "No approved actions to execute." and stop.

For each file, read the YAML frontmatter and extract:
- `action` — the action type (email_send, payment, social_post, file_delete)
- `created` — when the request was originally created
- `expires` — expiration timestamp
- `status` — should be `pending` or `approved` (skip if `executed` or `expired`)
- `priority` — low, medium, or high
- `source_file` — the original item that triggered this request

### Step 2: Validate Before Execution
For each approved file, run these safety checks **before** executing anything:

**Check 1 — Expiration**:
- Compare `expires` timestamp against the current time
- If expired: do NOT execute. Update frontmatter to `status: expired`, add `rejection_reason: expired_before_execution`, move to `/Rejected/`, log the event, and continue to the next file
- If not expired: proceed

**Check 2 — Already Processed**:
- If `status` is `executed`: skip this file (already done)
- If `status` is `expired` or `rejected`: skip this file (should not be in `/Approved/`)

**Check 3 — Rate Limits**:
- Read `/Logs/` for today's date file to count actions already taken
- For `email_send`: count emails sent in the last hour. If >= 10, set `status: rate_limited`, add `rate_limit_note: "Email hourly limit reached (10/hour). Retry after [time]."`, leave in `/Approved/`, and skip
- For `payment`: count payments made today. If >= 3, set `status: rate_limited`, add `rate_limit_note: "Payment daily limit reached (3/day). Retry tomorrow."`, leave in `/Approved/`, and skip

**Check 4 — DRY_RUN Mode**:
- Check if the system is in DRY_RUN mode (from `.env` configuration or assume DRY_RUN=true if uncertain)
- This check determines whether to perform real execution or simulated logging

### Step 3: Execute by Action Type
Process each validated file based on its `action` field:

---

**`email_send`**:
1. Read the approval file body to extract email details:
   - Recipient (`To:`)
   - Subject (`Subject:`)
   - Body (draft content)
2. Validate all three fields are present. If any are missing, set `status: execution_failed`, add `error: "Missing required field: [field]"`, log the error, and skip
3. **DRY_RUN mode** (DRY_RUN=true):
   - Log to `/Logs/[YYYY-MM-DD].md`:
     ```
     [HH:MM:SS] DRY RUN — email_send
       To: [recipient]
       Subject: [subject]
       Body: [first 100 chars]...
       Result: Simulated — no email sent
     ```
   - Update frontmatter: `status: executed`, `executed_at: [timestamp]`, `dry_run: true`
4. **LIVE mode** (DRY_RUN=false):
   - Send the email via the configured watcher/API
   - Log the actual send with confirmation details
   - Update frontmatter: `status: executed`, `executed_at: [timestamp]`, `dry_run: false`

---

**`payment`**:
1. Read the approval file body to extract payment details:
   - Amount
   - Recipient
   - Due date
   - Description/reference
2. Validate amount and recipient are present. If missing, set `status: execution_failed`, add `error: "Missing required field: [field]"`, log the error, and skip
3. **DRY_RUN mode** (DRY_RUN=true):
   - Log to `/Logs/[YYYY-MM-DD].md`:
     ```
     [HH:MM:SS] DRY RUN — payment
       Amount: $[amount]
       To: [recipient]
       Due: [date]
       Reference: [description]
       Result: Simulated — no payment processed
     ```
   - Create a transaction record in `/Accounting/`:
     ```markdown
     ---
     type: transaction_log
     action: payment
     amount: [amount]
     recipient: [recipient]
     date: [timestamp]
     status: dry_run
     approval_file: [filename]
     ---
     # Transaction: Payment to [recipient]
     **DRY RUN** — This payment was simulated, not executed.
     ```
   - Update frontmatter: `status: executed`, `executed_at: [timestamp]`, `dry_run: true`
4. **LIVE mode** (DRY_RUN=false):
   - Execute the payment via the configured watcher/API
   - Create a real transaction record in `/Accounting/` with `status: completed`
   - Update frontmatter: `status: executed`, `executed_at: [timestamp]`, `dry_run: false`

---

**`social_post`**:
1. Read the approval file body to extract post details:
   - Platform (Twitter, LinkedIn, etc.)
   - Content/body
   - Scheduled time (if any)
2. If a scheduled time is set, verify it is in the future. If in the past, set `status: execution_failed`, add `error: "Scheduled time is in the past"`, log the error, and skip
3. **DRY_RUN mode** (DRY_RUN=true):
   - Log to `/Logs/[YYYY-MM-DD].md`:
     ```
     [HH:MM:SS] DRY RUN — social_post
       Platform: [platform]
       Content: [first 100 chars]...
       Scheduled: [time or "immediate"]
       Result: Simulated — no post published
     ```
   - Update frontmatter: `status: executed`, `executed_at: [timestamp]`, `dry_run: true`
4. **LIVE mode** (DRY_RUN=false):
   - Schedule or publish the post via the configured watcher/API
   - Log the actual post with confirmation details
   - Update frontmatter: `status: executed`, `executed_at: [timestamp]`, `dry_run: false`

---

**`file_delete`**:
1. Read the approval file body to extract the target file path from `source_file`
2. Verify the target file exists. If it does not exist, set `status: execution_failed`, add `error: "Target file not found: [path]"`, log the error, and skip
3. Verify the target is NOT a vault system file (`.obsidian/`, `.claude/`, `.git/`, `.gitkeep`, `Company_Handbook.md`, `Business_Goals.md`, `Dashboard.md`). If it is, set `status: execution_failed`, add `error: "Cannot delete vault system file"`, log the error, and skip
4. **DRY_RUN mode** (DRY_RUN=true):
   - Log to `/Logs/[YYYY-MM-DD].md`:
     ```
     [HH:MM:SS] DRY RUN — file_delete
       Target: [filepath]
       Size: [filesize]
       Result: Simulated — file NOT deleted
     ```
   - Update frontmatter: `status: executed`, `executed_at: [timestamp]`, `dry_run: true`
5. **LIVE mode** (DRY_RUN=false):
   - Delete the target file
   - Log the deletion with the file path and size
   - Update frontmatter: `status: executed`, `executed_at: [timestamp]`, `dry_run: false`

---

**Unknown action type**:
- Do NOT execute. Set `status: execution_failed`, add `error: "Unknown action type: [action]"`
- Log the error and leave the file in `/Approved/` for human review

### Step 4: Move Executed Files to Done
For each successfully executed file (including dry runs):
1. Update the approval file frontmatter with final status:
   - `status: executed`
   - `executed_at: [current ISO timestamp]`
   - `dry_run: [true|false]`
2. Move the file from `/Approved/` to `/Done/`

For failed files (`status: execution_failed` or `status: rate_limited`):
- Do NOT move to `/Done/`
- Leave in `/Approved/` with the error details in frontmatter
- The user can review, fix, and re-trigger execution

### Step 5: Update Linked Plans
For each executed file, check if a corresponding plan exists in `/Plans/`:
- Search for `PLAN_*.md` files where `source_file` matches
- If found, update the plan's frontmatter:
  - Set `status: completed`
  - Add `completed_at: [current timestamp]`
  - Mark all checklist steps as done: `- [x]`
- If the execution was a dry run, update plan status to `dry_run_completed` instead

### Step 6: Log All Executions
Append to `/Logs/[YYYY-MM-DD].md`:

```markdown
## [HH:MM:SS] Execute Approved Actions Run

### Mode
DRY_RUN: [true|false]

### Results
| # | File | Action | Result | Dry Run | Timestamp |
|---|------|--------|--------|---------|-----------|
| 1 | [filename] | [action] | [executed|failed|rate_limited|expired] | [yes|no] | [time] |

### Execution Details
[For each executed item, include the DRY RUN log or real execution confirmation from Step 3]

### Errors
[List any failures with error messages, or "None"]

### Rate Limit Status
- Emails sent this hour: [count]/10
- Payments made today: [count]/3
```

### Step 7: Update Dashboard
Trigger the `update_dashboard` skill to refresh:
- Completed count (new items in `/Done/`)
- Pending Approval count (reduced)
- Active Plans (any plans marked completed)
- Alerts (any execution failures or rate limit warnings)

## Input
- `/Approved/*.md` — files approved by human, ready to execute
- `/Plans/PLAN_*.md` — linked plans to update on completion
- `/Logs/[YYYY-MM-DD].md` — today's log for rate limit checks
- `/Accounting/*.md` — for payment transaction logging
- `/Company_Handbook.md` — for rate limits and security rules
- System config (`.env`) — for DRY_RUN mode status

## Output
- `/Done/*.md` — executed approval files (moved from `/Approved/`)
- `/Rejected/*.md` — expired approvals caught during execution
- `/Accounting/*.md` — transaction records for payment actions
- `/Plans/PLAN_*.md` — updated plan status to completed
- `/Logs/YYYY-MM-DD.md` — detailed execution log
- `/Dashboard.md` — updated counts (via update_dashboard skill)

## Safety

### DRY_RUN Mode
- When DRY_RUN=true, **NEVER execute real actions** — only log what would happen
- All dry-run logs must clearly state "DRY RUN" and "Simulated"
- Dry-run executions still move files to `/Done/` (with `dry_run: true` in frontmatter) so the workflow progresses
- Accounting records created during dry run must be marked `status: dry_run`
- If DRY_RUN mode cannot be determined, **assume DRY_RUN=true** — always err on the side of safety

### Expiration Enforcement
- Always verify the `expires` timestamp before executing — even if the file is in `/Approved/`
- An expired approval is invalid regardless of who approved it
- Expired files are moved to `/Rejected/` with `rejection_reason: expired_before_execution`

### Never Execute Without Logging
- Every action (real or simulated) must be logged to `/Logs/`
- Every payment (real or simulated) must create a record in `/Accounting/`
- If logging fails, do NOT proceed with execution — log integrity is mandatory

### Protected Files
Never delete these vault system files, even if an approval requests it:
- `/.obsidian/*`
- `/.claude/*`
- `/.git/*`
- `/.gitkeep` (in any folder)
- `/Company_Handbook.md`
- `/Business_Goals.md`
- `/Dashboard.md`
- `/Welcome.md`

### Rate Limit Enforcement
- Check limits BEFORE execution, not after
- Rate-limited items stay in `/Approved/` for automatic retry on the next run
- Always report the current rate limit status in the log
