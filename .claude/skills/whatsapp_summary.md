# Skill: WhatsApp Daily Summary

## Trigger
- Daily at 9:00 PM (scheduled by orchestrator), OR
- On demand via: `Run skill: whatsapp_summary`

## Purpose
Generate a structured daily summary of WhatsApp activity and update the Dashboard.

## Steps

### 1. Get all active chats
Use the `whatsapp_get_chats` MCP tool to retrieve all chats.
Filter to chats with activity today (timestamp within last 24 hours).

### 2. Summarize each active chat
For each chat with today's activity:
- Use `whatsapp_get_chat_summary` with `period: today`
- Collect: message count, sent/received split, key topics, action items

### 3. Check pending replies
Scan `/Needs_Action/messages/` for any unprocessed WhatsApp messages (status: pending).

### 4. Generate summary file
Create `/Briefings/WhatsApp_Summary_[YYYY-MM-DD].md`:

```markdown
---
generated: [ISO timestamp]
period: [YYYY-MM-DD]
type: whatsapp_daily_summary
---

# WhatsApp Daily Summary — [date]

## Overview
- Total chats active: [count]
- Messages received: [count]
- Messages sent: [count]
- Pending replies: [count]

## Important Conversations
### [Contact Name]
- Messages: [count]
- Key Topics: [topics]
- Action Required: [yes/no — what]

## Pending Actions
- [ ] [list of things that need response]

## Flagged Messages
[any messages with urgent keywords that were not yet addressed]
```

### 5. Update Dashboard
Add/update the WhatsApp section in `Dashboard.md`:

```markdown
## WhatsApp Status
- **Connection**: [Connected/Disconnected]
- **Unread Chats**: [count]
- **Pending Replies**: [count]
- **Messages Today**: Sent [x] / Received [y]
- **Last Summary**: [[WhatsApp_Summary_YYYY-MM-DD]]
```

### 6. Log
Append to `/Logs/whatsapp/[date].log`:
```
[HH:MM:SS] | summary | chats=[n] | received=[n] | sent=[n] | pending=[n]
```

## Output Files
- `/Briefings/WhatsApp_Summary_[date].md`
- Updated `Dashboard.md` (WhatsApp section)
- Updated `/Logs/whatsapp/[date].log`
