# Skill: Create Plan

## Trigger
Run this skill when the user asks to "create a plan", "plan this", or "what should we do about [item]". Also run automatically when `process_inbox` encounters an item that requires multi-step action.

## Steps
1. Read the source item that needs a plan (from `/Needs_Action/`, `/Pending_Approval/`, or user-specified file)
2. Read its YAML frontmatter and contents to understand the full context
3. Read `/Company_Handbook.md` to check autonomy levels and constraints
4. Read `/Business_Goals.md` to check if the item relates to any active goals or metrics
5. Analyze the item and determine:
   - What type of action is needed (email, payment, file processing, project task, etc.)
   - Whether any step requires human approval (per Autonomy Levels table)
   - What the expected outcome is
   - What risks or constraints apply
6. Create a plan file in `/Plans/` named `PLAN_[brief_description]_[YYYYMMDD].md` with this format:

```markdown
---
created: [current ISO timestamp]
source_file: [original file name]
status: pending
requires_approval: [true/false]
priority: [low/medium/high]
---

## Objective
[Clear statement of what needs to be done and why]

## Analysis
- **Source**: [Where the item came from]
- **Content**: [Summary of what the item contains]
- **Risk**: [None/Low/Medium/High — explain if not None]
- **Handbook reference**: [Relevant autonomy level or rule]

## Steps
- [ ] Step 1 description
- [ ] Step 2 description
- [ ] **[APPROVAL NEEDED]** Step requiring human approval
- [ ] Step N description

## Approval Required
[Yes/No — if yes, explain exactly what needs approval and why per handbook rules]

## Success Criteria
[How to verify the plan was completed successfully]
```

7. After creating the plan, trigger the `update_dashboard` skill

## Input
- Source item from `/Needs_Action/`, `/Pending_Approval/`, or user-specified path
- `/Company_Handbook.md`
- `/Business_Goals.md`

## Output
- New plan file in `/Plans/PLAN_[description]_[date].md`
- Updated `/Dashboard.md` (via update_dashboard skill)

## Rules
- Always check Autonomy Levels before marking steps as auto-approved
- Any step involving payments must be marked `[APPROVAL NEEDED]`
- Any step involving emails to new contacts must be marked `[APPROVAL NEEDED]`
- Any step involving file deletion must be marked `[APPROVAL NEEDED]`
- Never create a plan that bypasses DRY_RUN mode during testing
- Never include passwords, API keys, or sensitive credentials in plan files
- Plans for financial actions must reference the logging requirement: "Log all transactions in /Accounting"
- Keep plan descriptions concise but complete enough for another agent to execute
