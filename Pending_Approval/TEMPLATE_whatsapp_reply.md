---
type: approval_request
action: whatsapp_reply
to_name: [contact name]
to_number: [phone number]
message_preview: [first 100 chars of reply]
reply_to: [original message summary]
created: [timestamp]
expires: [24 hours later]
status: pending
priority: [low | medium | high]
dry_run: true
---

## Reply Details
- **To**: [name] ([number])
- **Original Message**: [what they said]
- **Proposed Reply**:

> [full reply text here — edit this before approving if needed]

## Risk Level
[Low / Medium / High]

**Justification**: [why this reply was flagged for approval]

## To Approve
Move this file to `/Approved/` folder

## To Edit
Edit the reply text above, then move to `/Approved/`

## To Reject
Move this file to `/Rejected/` folder

---
*Template — do not process this file directly*
