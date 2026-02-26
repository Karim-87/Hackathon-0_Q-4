---
type: demo_script
target_duration: 10-12 minutes
created: 2026-02-15
updated: 2026-02-26
---

# Demo Script — Personal AI Employee

**Target duration**: 10-12 minutes
**Recording tip**: Have Obsidian, a terminal, and WhatsApp open before recording. Rehearse once end-to-end.

---

## 1. Intro (30 seconds)

**[Camera / screen recording starts]**

> Say:
> "Hi, I'm Karim. For Hackathon 0 I built a Personal AI Employee —
> an autonomous system that manages my emails, WhatsApp messages,
> files, payments, and social media using Claude Code, all inside
> an Obsidian vault.
>
> The key idea: the AI works for me 24/7, but every sensitive action
> requires my approval first. Let me show you how it works."

---

## 2. Vault Tour (1 minute)

### Show the folder structure in Obsidian sidebar

**[Click through each folder in Obsidian]**

> Say:
> "The whole system lives in an Obsidian vault. Think of it like a
> Kanban board made of folders."

Point out these folders (click each one):

1. **`Needs_Action/`** — "This is the inbox. Emails, WhatsApp messages, and dropped files land here automatically."
2. **`Needs_Action/messages/`** — "WhatsApp messages get their own subfolder — each one becomes a structured markdown file."
3. **`Plans/`** — "Claude reads the inbox and creates action plans here."
4. **`Pending_Approval/`** — "Anything that needs my sign-off waits here. I drag it to Approved or Rejected."
5. **`Approved/`** → **`Done/`** — "Once I approve, Claude executes and moves the result to Done."
6. **`Logs/`** — "Every action is logged — including a dedicated WhatsApp log — nothing happens silently."

### Show Dashboard.md

**[Open Dashboard.md in Obsidian]**

> Say:
> "This dashboard updates automatically every 30 minutes. It now
> includes a WhatsApp status section — I can see connection status,
> unread chats, and messages sent today. Plus the usual financials:
> $2,300 revenue this month, 46% of my $5,000 target."

**Scroll to highlight**:
- WhatsApp Status section (green connected indicator)
- Pending Actions table
- Financial Summary (MTD revenue vs target)
- Alerts section

### Show Company_Handbook.md

**[Open Company_Handbook.md]**

> Say:
> "This handbook defines the rules. The AI reads this before every
> action. I've now added a full WhatsApp section — for example,
> messages from unknown numbers always require approval before
> I reply, group messages are only processed when I'm mentioned,
> and I can never send more than 20 WhatsApp messages per hour."

**Scroll to the WhatsApp Autonomy Levels table** — pause so the viewer can read it.

---

## 3. WhatsApp Watcher Demo (2.5 minutes)

### Start the watcher

**[Switch to terminal]**

```bash
cd "D:\Hackathon-0 Q4\ai-employee-project"
node whatsapp_watcher.js
```

> Say:
> "I'm starting the WhatsApp watcher. It connects to WhatsApp Web
> using a saved session — no QR scan needed after the first time.
> The session is stored locally and gitignored for security."

**Wait for the connected message**:
```
WhatsApp Watcher starting... (DRY_RUN=false)
Authenticated. Session saved.
Connected: Karim Buksh (923042050840) on smba
Checking unread messages from last 24 hours...
Startup unread scan complete: 84 message(s) processed
```

> Say:
> "Notice it scanned 84 unread messages from the last 24 hours on
> startup. It filtered group messages that had no keywords, processed
> the ones that mattered, and created action files for each one."

### Show a processed message file

**[Switch to Obsidian — open Needs_Action/messages/]**

> Say:
> "Here's what a processed WhatsApp message looks like. Each message
> becomes a structured markdown file with YAML frontmatter —
> sender, phone number, priority, whether they're a new contact,
> and suggested actions."

**[Open one of the .md files]**

Highlight:
- `type: whatsapp_message`
- `priority: high`
- `is_new_contact: true`
- The "Suggested Actions" checklist

### Send a live test message

> Say:
> "Let me show you a live message arriving. I'll send myself
> a message with the keyword 'urgent' — which triggers high priority."

**[On phone: send a WhatsApp message to yourself with "urgent invoice check karo"]**

**[Watch terminal — within seconds]**:
```
Processed message from [Name] | priority=high | group=false
Action file created: Needs_Action/messages/20260226_[Name].md
```

**[Switch to Obsidian — refresh Needs_Action/messages/]**

> Say:
> "The file appeared instantly. The watcher detected the keyword,
> classified it as high priority, and created the action file.
> The orchestrator will pick this up in the next 15-second scan."

### Show group message filtering

**[Point to the terminal log — show the DEBUG lines]**:
```
Group message from [Group Name] skipped (no mention/keyword)
```

> Say:
> "Group messages are automatically filtered. Unless someone
> mentions me by name, or the message contains a trigger keyword
> like 'urgent' or 'invoice', it's skipped. No noise."

---

## 4. File Watcher Demo (1.5 minutes)

### Start the file watcher

**[Open a new terminal tab]**

```bash
cd "D:\Hackathon-0 Q4\AI_Employee_Vault"
uv run python filesystem_watcher.py
```

> Say:
> "The file system watcher monitors my desktop drop folder.
> Any file I put there gets automatically ingested."

### Drop a test file

```bash
echo "INVOICE - Project Alpha - $2,500 - Due March 1, 2026" > ~/Desktop/AI_Drop/invoice_project_alpha.txt
```

> Say: "Dropping a test invoice..."

**[Show the watcher log]**:
```
File copied: invoice_project_alpha.txt -> Needs_Action/files/...
Action file created: Needs_Action/files/...
```

> Say:
> "Instantly picked up, ingested into the vault, metadata file
> created. The original is removed from my desktop."

**[Ctrl+C to stop file watcher]**

---

## 5. Claude Code Processing (1.5 minutes)

### Show the orchestrator running

**[Switch to terminal]**

```bash
uv run python main.py --dry-run
```

> Say:
> "The orchestrator is the brain — it scans every 15 seconds,
> detects new items, and dispatches Claude Code skills."

**Wait for output**:
```
Orchestrator started (vault=..., dry_run=True, scan_interval=15s)
Initial snapshot — Needs_Action: 3, Approved: 0
DRY RUN — would run skill: update_dashboard
```

> Say:
> "In dry-run mode it logs what it would do. In production, Claude
> reads the skill file and executes every step autonomously —
> reading the message, checking the handbook, drafting a reply,
> and creating an approval file."

**[Ctrl+C to stop]**

### Show an existing plan

**[In Obsidian, open Plans/PLAN_whatsapp_urgent_test_user_20260226.md]**

> Say:
> "Here's a real plan Claude created for a WhatsApp message.
> It identified that the sender is a new contact, spotted the
> invoice keyword, created two actions — a reply draft and an
> invoice review task — and routed both to the approval queue."

---

## 6. Approval Workflow (2 minutes)

### Show a WhatsApp reply approval

**[In Obsidian, open Pending_Approval/WHATSAPP_REPLY_Test_User_20260226.md]**

> Say:
> "This is a WhatsApp reply waiting for my approval. Claude
> drafted the reply, set priority to high because it's a new
> contact, and explained exactly why approval is needed —
> referencing the Company Handbook."

**Highlight**:
- `action: whatsapp_reply`
- `priority: high`
- The proposed reply text
- "New contact — requires approval" note

### Approve it

> Say:
> "To approve, I drag this file to the Approved folder.
> That's the entire UI — just move a markdown file."

**[Drag from Pending_Approval/ to Approved/ in Obsidian sidebar]**

> Say:
> "The orchestrator detects this in the next scan and runs
> the whatsapp_reply skill — which sends the message, writes
> an audit log, and moves the file to Done."

### Show the email approval too

**[Open Approved/APPROVAL_email_new_contact_invoice_20260214.md]**

> Say:
> "Same pattern for emails. Sarah Martinez sent a $5,000
> invoice request — Claude flagged it, created this approval,
> and it's been waiting for me. One drag to execute."

### Show the audit log

**[Terminal]**:

```bash
cat Logs/audit/audit_2026-02-26.jsonl
```

> Say:
> "Every approval, every execution, every dry-run — all logged
> in JSON format with timestamp, actor, target, and result.
> Full audit trail."

---

## 7. WhatsApp MCP Tools (1 minute)

**[Switch to terminal — explain what MCP is]**

> Say:
> "I also built a WhatsApp MCP server — this gives Claude Code
> direct access to WhatsApp through 8 tools registered in the
> Claude config."

**[Show .claude/mcp.json]**

> Say:
> "Claude can now call `whatsapp_get_chats` to see my inbox,
> `whatsapp_search_messages` to find specific conversations,
> or `whatsapp_get_chat_summary` to get an AI-ready summary
> of any conversation. All read-only tools are auto-approved.
> Send and delete always create an approval file first —
> the AI cannot act unilaterally."

**[Show Briefings/WhatsApp_Summary_2026-02-26.md]**

> Say:
> "Every evening at 9 PM, a WhatsApp daily summary is generated
> automatically — total messages, key topics, pending replies,
> and flagged urgent conversations."

---

## 8. CEO Briefing (1 minute)

**[In Obsidian, open Briefings/2026-02-16_Monday_Briefing_v2.md]**

> Say:
> "Every Sunday night, the AI generates a CEO briefing for
> Monday morning. This is a real one."

**Scroll through and highlight**:

1. **Executive Summary** — "Two sentences covering the whole week."
2. **Revenue table** — "$2,300 of $5,000 — 46%, invoice payment rate 100%."
3. **Completed This Week** — "Three tasks completed with timestamps."
4. **Bottlenecks** — "Shows items stuck in approval too long."
5. **Proactive Suggestions** — "The AI recommends next actions."

> Say:
> "This isn't a template — Claude analyzed the vault, read the
> logs, checked financials, and wrote this. Every number is
> real data from the vault."

---

## 9. Security Demo (30 seconds)

**[Terminal]**:

```bash
uv run python -c "from security_config import security; print(security.all_rate_limits())"
```

> Say:
> "Security is built in from day one. Rate limits are enforced
> in code — 10 emails per hour, 20 WhatsApp messages per hour,
> 3 payments per day. The AI literally cannot exceed these,
> even if it wanted to.
>
> DRY_RUN is on by default. All credentials come from environment
> variables — nothing hardcoded. WhatsApp session data and OAuth
> tokens are gitignored. Every action has a JSON audit trail."

---

## 10. Closing (30 seconds)

> Say:
> "To recap — this is a fully autonomous AI employee that:
>
> - Monitors my email and WhatsApp 24/7
> - Watches my desktop for dropped files
> - Creates action plans and drafts responses
> - Requires my approval for every sensitive action
> - Generates weekly CEO briefings with financial analysis
> - Posts to LinkedIn on my behalf
> - Summarizes my WhatsApp daily at 9 PM
> - Logs every single action for auditability
>
> It runs on 11 Claude Code skills, 2 MCP servers — LinkedIn
> and WhatsApp — and the entire UI is just an Obsidian vault.
>
> This is my Gold tier submission for Hackathon 0.
> Thanks for watching!"

**[End recording]**

---

## Pre-Recording Checklist

Before hitting record, make sure:

**System**
- [ ] Obsidian is open with the vault loaded
- [ ] Terminal is open in the vault directory
- [ ] Screen resolution 1080p+, font size increased for visibility
- [ ] Close any windows with personal info / credentials
- [ ] `.env` has `DRY_RUN=false` for live WhatsApp demo (or true for safety)

**WhatsApp**
- [ ] `node whatsapp_watcher.js` has been run once — session is connected
- [ ] `Needs_Action/messages/` has at least one processed message to show
- [ ] `Pending_Approval/` has a `WHATSAPP_REPLY_*.md` file ready to approve
- [ ] A second phone or contact is ready to send a live test message
- [ ] `Briefings/WhatsApp_Summary_*.md` exists to show

**Email / Files**
- [ ] `AI_Drop` folder exists on desktop and is empty
- [ ] `Needs_Action/` has items to show
- [ ] `Plans/` has at least one plan to open
- [ ] `Briefings/` has the Monday briefing ready

**Code**
- [ ] `uv sync` has been run (Python dependencies installed)
- [ ] `npm install` has been run in `whatsapp/` folder
- [ ] Orchestrator imports cleanly: `uv run python -c "from orchestrator import Orchestrator; print('OK')"`

---

## Timing Guide

| Section | Duration | Cumulative |
|---------|----------|------------|
| Intro | 0:30 | 0:30 |
| Vault Tour | 1:00 | 1:30 |
| WhatsApp Watcher Demo | 2:30 | 4:00 |
| File Watcher Demo | 1:30 | 5:30 |
| Claude Processing | 1:30 | 7:00 |
| Approval Workflow | 2:00 | 9:00 |
| WhatsApp MCP Tools | 1:00 | 10:00 |
| CEO Briefing | 1:00 | 11:00 |
| Security | 0:30 | 11:30 |
| Closing | 0:30 | 12:00 |

**Total: ~12 minutes**

---

## Recording Tips

- Speak slowly and clearly — speed up in editing if needed
- Pause 2-3 seconds on important screens so viewers can read
- If a command takes time, narrate what's happening while you wait
- Keep `.env` off-screen at all times (paths and credentials)
- If WhatsApp takes a few seconds to connect — narrate it: "The session loads from cache, no QR needed"
- If something goes wrong, keep recording — troubleshooting live shows authenticity
- The WhatsApp watcher terminal and Obsidian look great side-by-side for the message demo
