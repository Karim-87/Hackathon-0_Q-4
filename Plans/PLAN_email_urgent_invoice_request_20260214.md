---
created: 2026-02-14T12:05:00Z
source_file: 20260214_120200_URGENT_Invoice_Request.md
status: in_progress
requires_approval: true
priority: high
---

## Objective
Handle an urgent email from a **new contact** (Sarah Martinez, sarah.martinez@newclient.com) requesting an invoice for a $5,000 initial consultation fee for a web development project. This email contains both financial keywords and urgency indicators, and the sender is not in the known contacts list.

## Analysis
- **Source**: Gmail inbox, detected by GmailWatcher at 2026-02-14 12:02:00 UTC
- **Content**: Sarah Martinez requests an invoice for $5,000 for an initial consultation. She references a prior networking event conversation and provides company details (Martinez Digital Solutions, Austin TX).
- **Risk**: Medium — new contact with financial request. The sender's identity and the referenced conversation have not been verified.
- **Handbook references**:
  - "Never send an email to a new/unknown contact without my approval" (Communication Rules)
  - "Send email to new contact → Always approval" (Autonomy Levels)
  - "Flag ANY payment for my approval" (Financial Rules)
  - "Log all transactions in /Accounting" (Financial Rules)

## Steps
- [x] Email detected and ingested by GmailWatcher
- [x] Email classified as: `email`, priority `high`, new contact `true`
- [x] Financial keywords detected: "invoice", "consultation fee", "$5,000"
- [x] Urgency keywords detected: "URGENT", "as soon as possible"
- [ ] **[APPROVAL NEEDED]** Verify sender identity — confirm Sarah Martinez and the networking event conversation are legitimate
- [ ] **[APPROVAL NEEDED]** Decide whether to reply to this new contact
- [ ] **[APPROVAL NEEDED]** If replying: review and approve the draft reply before sending
- [ ] **[APPROVAL NEEDED]** If creating an invoice: approve the $5,000 amount and recipient details
- [ ] If approved: draft a professional reply acknowledging the request
- [ ] If approved: create invoice in `/Invoices/` with details from the email
- [ ] Log any financial transaction to `/Accounting/`
- [ ] Move email action file to `/Done/` after completion

## Approval Required
**Yes** — Multiple approvals needed:

1. **Reply to new contact** — Sarah Martinez (sarah.martinez@newclient.com) is not in the known contacts list. Per Company Handbook Communication Rules: "Never send an email to a new/unknown contact without my approval."

2. **Financial action** — The email requests an invoice for $5,000. Per Company Handbook Financial Rules: "Flag ANY payment for my approval." Creating and sending an invoice is a financial action that must be approved.

An approval request has been created at [[APPROVAL_email_new_contact_invoice_20260214]].

## Success Criteria
- Human has verified the sender's identity
- Human has approved or rejected the reply
- If approved: reply sent, invoice created in `/Invoices/`, transaction logged in `/Accounting/`
- If rejected: email archived in `/Done/` with `status: rejected`, no reply sent
- All actions logged to `/Logs/2026-02-14.md`
