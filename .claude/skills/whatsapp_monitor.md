# Skill: WhatsApp Monitor

## Trigger
New file in `/Needs_Action/messages/` with `type: whatsapp_message`

## Purpose
Process incoming WhatsApp messages — classify them, draft replies where needed,
and route everything through the approval workflow.

## Steps

### 1. Read the message file
- Read the triggering file from `/Needs_Action/messages/`
- Extract: sender, phone, priority, is_new_contact, is_group, message body

### 2. Check Company Handbook rules
- Read `Company_Handbook.md` (WhatsApp Rules section)
- Determine if message falls under trigger keywords:
  `urgent, asap, invoice, payment, help, pricing, deadline, emergency, critical`

### 3. Decide if reply is needed
A reply is needed if:
- Message contains a trigger keyword, OR
- Sender is a known contact AND message requires a response, OR
- Message mentions you directly in a group

No reply needed if:
- Casual/social message with no action required
- Spam or promotional content
- Already replied recently (check `/Done/` folder)

### 4a. Reply needed — KNOWN contact
1. Draft a professional reply (match sender's language per Company Handbook)
2. Create `/Pending_Approval/WHATSAPP_REPLY_[sender]_[YYYYMMDD].md`:

```markdown
---
type: approval_request
action: whatsapp_reply
to_name: [contact name]
to_number: [phone number]
message_preview: [first 100 chars]
reply_to: [summary of original message]
created: [ISO timestamp]
expires: [24 hours later]
status: pending
priority: [low | medium | high]
dry_run: true
---

## Reply Details
- **To**: [name] ([number])
- **Original Message**: [what they said]
- **Proposed Reply**: [full reply text]

## To Approve
Move this file to /Approved/ folder

## To Edit
Edit the reply text above, then move to /Approved/

## To Reject
Move this file to /Rejected/ folder
```

### 4b. Reply needed — NEW contact
Same as 4a but:
- Set `priority: high` in the approval file
- Add warning: "⚠️ NEW CONTACT — verify identity before approving"

### 5. Invoice/payment related
If message contains invoice/payment keywords:
1. Create `/Plans/PLAN_whatsapp_invoice_[sender]_[date].md` with:
   - What was requested
   - Suggested invoice amount (if mentioned)
   - Steps: draft invoice → approval → send
2. Link the plan to the approval file

### 6. Update Dashboard
Run `update_dashboard` skill to reflect new WhatsApp message count.

### 7. Log action
Append to `/Logs/whatsapp/[YYYY-MM-DD].log`:
```
[HH:MM:SS] | process | sender=[name] | priority=[p] | action=[reply_drafted|no_action|invoice_plan]
```

## Output Files
- `/Pending_Approval/WHATSAPP_REPLY_*.md` — if reply needed
- `/Plans/PLAN_whatsapp_invoice_*.md` — if financial action needed
- Updated `/Logs/whatsapp/[date].log`
