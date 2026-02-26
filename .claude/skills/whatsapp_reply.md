# Skill: WhatsApp Reply Handler

## Trigger
File moved to `/Approved/` with `action: whatsapp_reply`

## Purpose
Execute an approved WhatsApp reply — send the message (or simulate in DRY_RUN mode)
and complete the workflow audit trail.

## Steps

### 1. Read approved file
- Read the file from `/Approved/`
- Extract: `to_number`, `to_name`, `message_preview`, `dry_run`
- Find the full reply text in the "Proposed Reply" section of the file

### 2. Check DRY_RUN mode
Read `DRY_RUN` from environment (or from the `dry_run` field in the file).

### 3a. DRY_RUN = true
- Log: `DRY_RUN: Would send WhatsApp to [number]: [message]`
- Do NOT call `whatsapp_send_message` tool
- Continue to step 4

### 3b. DRY_RUN = false
- Call `whatsapp_send_message` MCP tool:
  ```
  to: [to_number]
  message: [full reply text from approved file]
  ```
- If tool returns error: log it and create alert in `/Needs_Action/`
- If tool returns success: continue to step 4

### 4. Move file to /Done/
Rename/move the approved file to `/Done/DONE_whatsapp_reply_[sender]_[date].md`.
Update its frontmatter:
```yaml
status: completed
completed_at: [ISO timestamp]
dry_run: [true/false]
```

### 5. Update linked plan (if any)
If the approved file references a `/Plans/` file:
- Open that plan file
- Update status to `completed`

### 6. Audit log
Append JSON audit entry to `/Logs/audit/audit_[date].jsonl`:
```json
{
  "timestamp": "[ISO]",
  "action_type": "whatsapp_send",
  "actor": "whatsapp_reply_skill",
  "target": "[to_number]",
  "dry_run": [true/false],
  "result": "success|dry_run|failed"
}
```

### 7. Update Dashboard
Run `update_dashboard` skill.

## Output Files
- `/Done/DONE_whatsapp_reply_*.md` (completed action)
- `/Logs/audit/audit_[date].jsonl` (audit entry)
- Updated `Dashboard.md`
