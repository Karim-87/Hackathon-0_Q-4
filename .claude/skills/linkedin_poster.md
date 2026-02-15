# Skill: LinkedIn Post Generator

## Trigger
Run when the user says "create linkedin post", "linkedin update", "post on linkedin", "draft linkedin", "social media post", or "share on linkedin".

Also triggered by the orchestrator when a `social_post` action with `platform: linkedin` is detected in `/Needs_Action/` or `/Approved/`.

## Steps

### Step 1: Read Business Context
Read the following files to understand the current business state:

1. **`/Business_Goals.md`** — extract:
   - Current quarter objectives
   - Revenue progress (MTD vs target)
   - Active projects (names, types, status)
   - Key metrics and achievements

2. **`/Active_Projects/`** — scan all `.md` files and extract:
   - Project names and descriptions
   - Client types (without revealing client names — use "a client" or industry terms)
   - Technologies and services being delivered
   - Milestones reached or upcoming
   - Any completed projects worth highlighting

3. **`/Company_Handbook.md`** — check:
   - Communication Rules (professional tone)
   - Autonomy Levels: "Social media scheduled post → Approval needed"
   - Security Rules: never share sensitive data

### Step 2: Determine Post Topic
Based on the business context gathered, select the most relevant topic for a LinkedIn post. Prioritize in this order:

1. **Recently completed project** — if any project in `/Active_Projects/` or `/Done/` was recently completed
2. **Milestone reached** — if revenue target hit, key metric achieved, or project milestone reached
3. **Industry insight** — based on the type of work being done (web development, design, etc.)
4. **Business update** — general progress, growth, or team/process improvements
5. **Thought leadership** — professional insight related to active project domains

If multiple topics are viable, pick the one with the most concrete data to reference.

### Step 3: Generate Post Content
Write a professional LinkedIn post following these guidelines:

**Format**:
- Opening hook line (attention-grabbing, under 15 words)
- 2-3 short paragraphs (each 2-3 sentences max)
- Key insight or lesson learned
- Call-to-action or question to drive engagement
- 3-5 relevant hashtags

**Tone**:
- Professional but approachable
- Confident, not boastful
- Value-driven — share insights, not just announcements
- Written in first person ("I" / "we")

**Rules**:
- NEVER mention specific client names — use "a client", "a partner", or industry terms
- NEVER include revenue numbers, financial data, or pricing
- NEVER share internal metrics, goals, or targets
- NEVER include API keys, passwords, or technical credentials
- Keep under 1300 characters (LinkedIn optimal length)
- Include line breaks for readability

### Step 4: Create Approval File
Create the post draft in `/Pending_Approval/` for human review:

**Filename**: `LINKEDIN_[YYYY-MM-DD].md`

If a file with today's date already exists, append a version suffix: `LINKEDIN_[YYYY-MM-DD]_v2.md`, `_v3.md`, etc.

**File format**:
```markdown
---
type: social_post
platform: linkedin
created: [current ISO timestamp]
status: pending_approval
action: social_post
requires_approval: true
priority: medium
expires: [72 hours from now, ISO timestamp]
dry_run_on_approve: true
---

# LinkedIn Post Draft

## Post Content

[The generated post content here, exactly as it should appear on LinkedIn]

## Context
- **Topic**: [selected topic from Step 2]
- **Based on**: [which files/data informed this post]
- **Character count**: [count]

## Approval Request
**Action**: Publish this post to LinkedIn
**Reason**: Per Company Handbook — "Social media scheduled post → Approval needed"
**Risk Level**: Low

### To approve:
Move this file to `/Approved/`

### To request changes:
Edit the post content above and leave in `/Pending_Approval/`

### To reject:
Move this file to `/Rejected/`
```

### Step 5: Update Dashboard
Add an entry to `/Dashboard.md`:
- Note in Recent Logs: "LinkedIn post draft created — pending approval"
- Update Pending Approval count

### Step 6: Log the Action
Append to `/Logs/[YYYY-MM-DD].md`:

```markdown
## [HH:MM:SS] LinkedIn Post Draft Created

- **Topic**: [selected topic]
- **Character count**: [count]
- **Status**: Pending approval in `/Pending_Approval/LINKEDIN_[date].md`
- **Expires**: [expiration timestamp]
- **Data sources**: [list of files read]
```

## Execution (After Approval)

When the approved file appears in `/Approved/`, the `execute_approved` skill handles it:

### DRY_RUN Mode (DRY_RUN=true):
- Log to `/Logs/[YYYY-MM-DD].md`:
  ```
  [HH:MM:SS] DRY RUN — social_post (linkedin)
    Content: [first 100 chars]...
    Result: Simulated — no post published
  ```
- Update frontmatter: `status: executed`, `executed_at: [timestamp]`, `dry_run: true`
- Move to `/Done/`

### LIVE Mode (DRY_RUN=false):
- Call the LinkedIn MCP server tool `create_post` with the post content
- If successful: log confirmation, update frontmatter, move to `/Done/`
- If failed: log error, set `status: execution_failed`, leave in `/Approved/`

## Input
- `/Business_Goals.md` — revenue targets, active projects, key metrics
- `/Active_Projects/*.md` — project details for content generation
- `/Company_Handbook.md` — communication rules, autonomy levels
- `/Done/*.md` — recently completed projects (for topic selection)

## Output
- `/Pending_Approval/LINKEDIN_[YYYY-MM-DD].md` — post draft awaiting approval
- `/Dashboard.md` — updated with draft notification
- `/Logs/YYYY-MM-DD.md` — structured log entry

## Rules

### Content Safety
- NEVER mention specific client names or identifying details
- NEVER include financial figures (revenue, pricing, budgets)
- NEVER share internal metrics, KPIs, or business targets
- NEVER include technical credentials, API keys, or internal URLs
- NEVER post without human approval — this is a hard requirement
- NEVER fabricate achievements, metrics, or testimonials

### Approval Requirement
- Per Company Handbook Autonomy Levels: "Social media scheduled post → Approval needed"
- Posts MUST go through `/Pending_Approval/` before execution
- Expired approvals (>72 hours) must not be posted — create a fresh draft instead

### Post Quality
- Every post must provide value — insight, lesson, or useful information
- Avoid generic platitudes ("Excited to announce...", "Thrilled to share...")
- Lead with the insight or result, not the announcement
- Include a question or CTA to encourage engagement
- Hashtags should be relevant to the content, not trending-chasing

### Frequency
- Maximum one LinkedIn post per day
- Before creating a new draft, check `/Pending_Approval/` and `/Done/` for existing posts today
- If a post was already published or is pending today, skip and log: "LinkedIn post already exists for today"
