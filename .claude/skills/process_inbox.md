# Skill: Process Inbox

## Trigger
Run when new files appear in `/Needs_Action/` folder. Also activate when the user says "check inbox", "process inbox", "what's new", "scan for new items", or during scheduled checks (Monday briefings, daily scans).

## Steps

### Step 1: Scan Needs_Action
Read all `.md` files in `/Needs_Action/` and its subfolders:
- `/Needs_Action/emails/*.md`
- `/Needs_Action/messages/*.md`
- `/Needs_Action/files/*.md`

Ignore `.gitkeep` files. If all subfolders are empty, report "No pending actions found." and stop.

### Step 2: Read and Classify Each Item
For each `.md` file found, read the YAML frontmatter to determine its `type` field. Classify into one of these categories:

| Type | Frontmatter `type` value | Description |
|------|--------------------------|-------------|
| Email | `email` | Incoming email requiring response or action |
| Message | `message` | WhatsApp/chat message to evaluate |
| File Drop | `file_drop` | File dropped in AI_Drop folder by user |
| Payment | `payment`, `invoice` | Financial document requiring approval |
| Unknown | anything else or missing | Unclassified item for human review |

### Step 3: Process by Type

**Email items** (`type: email`):
1. Read `/Company_Handbook.md` — check Communication Rules and Autonomy Levels
2. Determine if sender is a known or unknown contact (check frontmatter for `sender` or `from` field)
3. If **known contact**: draft a reply in `/In_Progress/` — auto-approved to draft, but sending requires approval
4. If **unknown contact**: do NOT draft a reply. Create approval file in `/Pending_Approval/` with `requires_approval: true`
5. Always reply in the same language the sender used

**Message items** (`type: message`):
1. Read the message content and check for trigger keywords: `urgent`, `invoice`, `payment`, `help`, `asap`, `pricing`
2. If **keywords found**: escalate — create an action item in `/In_Progress/` and flag priority in the plan
3. If **no keywords found**: ignore the message. Update its frontmatter to `status: ignored` and move to `/Done/`
4. Always reply in the same language the sender used

**File drop items** (`type: file_drop`):
1. Read the associated dropped file (path in frontmatter `copied_to` or paired file with same timestamp prefix)
2. Determine file purpose by analyzing content:
   - Invoice/billing → categorize as `payment`, route to approval
   - Report/data → categorize as `informational`, route to relevant project
   - Configuration/code → categorize as `technical`, route to relevant project
   - Test/junk data → categorize as `test`, recommend archival
   - Unknown → categorize as `unknown`, flag for human review
3. Update the metadata `.md` frontmatter with `classified_as: [category]`

**Payment items** (`type: payment` or `type: invoice`):
1. **ALWAYS** create an approval file in `/Pending_Approval/` — no exceptions
2. Never auto-approve any payment regardless of amount or recipient
3. Extract key financial details: amount, recipient, due date, description
4. Log the flagged payment to `/Accounting/` with a transaction record
5. Set `requires_approval: true` and `priority: high` in frontmatter

**Unknown items** (type missing or unrecognized):
1. Create approval file in `/Pending_Approval/` with `requires_approval: true`
2. Set `classified_as: unknown` and add a note requesting human classification

### Step 4: Create Plans
For each processed item, create a plan file in `/Plans/`:
- Filename: `PLAN_[type]_[brief_description]_[YYYYMMDD].md`
- Follow the format defined in the `create_plan` skill
- Include all steps identified during classification
- Mark any approval-required steps with `**[APPROVAL NEEDED]**`

### Step 5: Create Approval Files
For any item requiring approval, create a file in `/Pending_Approval/`:
```yaml
---
created: [current ISO timestamp]
source_file: [original filename from Needs_Action]
source_folder: [emails|messages|files]
type: [email|message|file_drop|payment|unknown]
requires_approval: true
priority: [low|medium|high]
status: pending_approval
---

## Approval Request
**Item**: [description of what needs approval]
**Reason**: [why approval is required per Company Handbook]
**Recommended Action**: [what the AI Employee suggests]
**Risk Level**: [None|Low|Medium|High]

## Source Content
[Summary or excerpt of the original item]

## Handbook Reference
[Which specific rule from Company_Handbook.md requires this approval]
```

### Step 6: Update Dashboard
After all items are processed, run the `update_dashboard` skill to refresh `/Dashboard.md` with:
- Updated pending action counts
- New plans listed
- New approval requests listed
- Vault summary table refreshed

### Step 7: Log All Actions
Create or append to `/Logs/[YYYY-MM-DD].md` with a structured log entry:
```markdown
## [HH:MM:SS] Process Inbox Run

### Items Scanned
- Emails: [count]
- Messages: [count]
- Files: [count]

### Actions Taken
| Item | Type | Action | Destination |
|------|------|--------|-------------|
| [filename] | [type] | [action taken] | [where it was routed] |

### Approvals Created
- [list of items sent to Pending_Approval, or "None"]

### Plans Created
- [list of PLAN_ files created, or "None"]
```

## Input
- `/Needs_Action/**/*.md` — all pending items to process
- `/Company_Handbook.md` — rules for autonomy levels, communication, financial, and security constraints

## Output
- `/Plans/PLAN_*.md` — one plan file per processed item
- `/Pending_Approval/*.md` — approval request for each item requiring human sign-off
- `/In_Progress/*.md` — items that are auto-approved and ready for execution
- `/Done/*.md` — ignored messages (no trigger keywords)
- `/Dashboard.md` — updated with new counts and status
- `/Logs/YYYY-MM-DD.md` — structured log of all actions taken
- `/Accounting/*.md` — transaction records for any payment items

## Rules

### Communication Rules (from Company Handbook)
- Always be polite and professional in all emails and messages
- Never send an email to a new/unknown contact without approval
- WhatsApp: respond only to messages containing keywords: urgent, invoice, payment, help, asap, pricing
- Always reply in the same language the sender used

### Financial Rules (from Company Handbook)
- Flag ANY payment for approval — create file in `/Pending_Approval/`
- Never auto-approve payments to new recipients
- Flag any subscription over $50/month
- Log all transactions in `/Accounting/`

### Security Rules (from Company Handbook)
- Never store passwords or API keys in the vault
- All sensitive actions require Human-in-the-Loop approval
- Maximum 10 emails per hour, maximum 3 payments per day
- Always use DRY_RUN mode during testing

### Autonomy Levels (from Company Handbook)
| Action | Auto-Approve? |
|--------|--------------|
| Read emails | Yes |
| Draft email reply to known contact | Yes |
| Send email to known contact | Approval needed |
| Send email to new contact | Always approval |
| Read bank transactions | Yes |
| Any payment action | Always approval |
| File operations (create/read) | Yes |
| File delete | Always approval |

### Skill-Specific Rules
- Never skip the logging step — every run must be logged
- Process items in chronological order (oldest first by `dropped_at` or `received_at`)
- If an item has already been processed (`status` is not `pending`), skip it
- If more than 10 items are pending, process the 10 oldest first and note remaining count
- When uncertain about classification, default to `/Pending_Approval/` rather than auto-routing
