---
type: demo_script
target_duration: 5-10 minutes
created: 2026-02-15
---

# Demo Script — Personal AI Employee

**Target duration**: 5-10 minutes
**Recording tip**: Have Obsidian and a terminal open side by side. Rehearse once before recording.

---

## 1. Intro (30 seconds)

**[Camera / screen recording starts]**

> Say:
> "Hi, I'm Karim. For Hackathon 0 I built a Personal AI Employee —
> an autonomous system that manages my emails, files, payments, and
> social media using Claude Code, all inside an Obsidian vault.
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

1. **`Needs_Action/`** — "This is the inbox. Emails, files, and messages land here automatically."
2. **`Plans/`** — "Claude reads the inbox and creates action plans here."
3. **`Pending_Approval/`** — "Anything that needs my sign-off waits here. I drag it to Approved or Rejected."
4. **`Approved/`** → **`Done/`** — "Once I approve, Claude executes and moves the result to Done."
5. **`Logs/`** — "Every action is logged — nothing happens silently."

### Show Dashboard.md

**[Open Dashboard.md in Obsidian]**

> Say:
> "This dashboard updates automatically. Right now I have 3 pending
> actions, 3 items waiting for my approval, and $2,300 revenue this
> month — 46% of my $5,000 target."

**Scroll to highlight**:
- System Status (green online indicator)
- Pending Actions table
- Financial Summary (MTD revenue vs target)
- Alerts section (invoice request, revenue pace warning)

### Show Company_Handbook.md

**[Open Company_Handbook.md]**

> Say:
> "This handbook defines the rules. The AI reads this before every
> action. For example — any payment requires my approval, emails to
> new contacts need sign-off, and social media posts are never
> auto-published."

**Scroll to the Autonomy Levels table** — pause so the viewer can read it.

---

## 3. File Watcher Demo (2 minutes)

### Start the watcher

**[Switch to terminal]**

```bash
cd "D:\Hackathon-0 Q4\AI_Employee_Vault"
uv run python filesystem_watcher.py
```

> Say:
> "I'm starting the file system watcher. It monitors my desktop
> drop folder — any file I put there gets automatically ingested
> into the vault."

**Wait for the startup message**:
```
Starting FileSystemWatcher (interval=5s, vault=...)
Watching drop folder: C:\Users\User\Desktop\AI_Drop
```

### Drop a test file

**[Open a second terminal or file explorer]**

Create a test file and drop it:

```bash
echo "INVOICE - Project Alpha - $2,500 - Due March 1, 2026" > ~/Desktop/AI_Drop/invoice_project_alpha.txt
```

> Say:
> "I'm dropping a test invoice into the AI Drop folder on my desktop."

### Show the result

**[Switch back to the watcher terminal]**

Wait for the log output:
```
File copied: invoice_project_alpha.txt -> Needs_Action/files/...
Action file created: Needs_Action/files/...
Original removed from drop folder: invoice_project_alpha.txt
```

> Say:
> "Within seconds, the watcher picked it up, copied it into the vault,
> created a metadata file, and removed the original from my desktop.
> Let me show you in Obsidian."

**[Switch to Obsidian]**

Open `Needs_Action/files/` — show the new `.md` file that was created:

> Say:
> "Here's the action file. It has YAML frontmatter with the file type,
> size, timestamp — and a body describing what was dropped. The
> orchestrator will pick this up next."

**[Ctrl+C the watcher in terminal to stop it]**

---

## 4. Claude Code Processing (2 minutes)

### Show Claude processing the inbox

**[Switch to terminal]**

```bash
uv run python main.py --dry-run
```

> Say:
> "Now I'm starting the orchestrator in dry-run mode. It scans the
> vault every 15 seconds and dispatches Claude Code skills to process
> new items."

**Wait for initial output**:
```
Orchestrator started (vault=..., dry_run=True, scan_interval=15s)
Initial snapshot — Needs_Action: X, Approved: 0
DRY RUN — would run skill: update_dashboard
```

> Say:
> "In dry-run mode, it logs what it *would* do without actually
> calling Claude. In production, Claude reads the skill instructions
> and executes each step autonomously."

**[Ctrl+C to stop the orchestrator]**

### Show an existing plan

**[Switch to Obsidian]**

Open `Plans/PLAN_email_urgent_invoice_request_20260214.md`

> Say:
> "Here's a plan Claude created when an urgent invoice email arrived.
> It identified the action type, listed the steps needed, and flagged
> that payment approval is required."

**Scroll to show**:
- The action steps
- The `**[APPROVAL NEEDED]**` markers

### Show the audit log

**[Open Logs/audit/ in file explorer or terminal]**

```bash
cat Logs/audit/audit_2026-02-15.jsonl
```

> Say:
> "Every single action gets logged in JSON format — timestamp, who
> did it, what they did, and whether it was a dry run. This is the
> full audit trail."

---

## 5. Approval Workflow (2 minutes)

### Show a pending approval

**[In Obsidian, open Pending_Approval/]**

Open `APPROVAL_email_new_contact_invoice_20260214.md`

> Say:
> "This is a real approval request. Sarah Martinez sent an urgent
> invoice for $5,000. Claude classified it, flagged it as high
> priority, and created this approval file. It's waiting for me."

**Highlight these sections**:
- `requires_approval: true`
- `priority: high`
- The "Recommended Action" section
- The "Handbook Reference" section (shows *why* approval is needed)

### Approve it (move the file)

> Say:
> "To approve, I simply drag this file from Pending_Approval to
> Approved. That's it — no buttons, no UI. Just move the file."

**[In Obsidian, drag the file from `Pending_Approval/` to `Approved/`]**

*(Alternative: use terminal)*
```bash
mv Pending_Approval/APPROVAL_email_new_contact_invoice_20260214.md Approved/
```

### Show dry-run execution

**[Switch to terminal]**

```bash
uv run python main.py --dry-run
```

Wait for output showing it detected the approved item:
```
Detected 1 approved item(s)
DRY RUN — would run skill: execute_approved
```

> Say:
> "The orchestrator detected the approved file and would execute it.
> In dry-run mode it just logs. In production, it would send the
> email, log the transaction in Accounting, and move the file to Done."

**[Ctrl+C to stop]**

### Show the LinkedIn post approval

**[In Obsidian, open Pending_Approval/LINKEDIN_2026-02-15.md]**

> Say:
> "Here's another example — a LinkedIn post Claude drafted. It read
> my business goals, saw that I completed a logo design project, and
> wrote this post. It won't publish until I approve it."

**Scroll to the post content** — read a line or two aloud.

---

## 6. CEO Briefing (1 minute)

**[In Obsidian, open Briefings/2026-02-16_Monday_Briefing_v2.md]**

> Say:
> "Every Sunday night, the AI generates a CEO briefing for Monday
> morning. This is a real one."

**Scroll through and highlight**:

1. **Executive Summary** — "Two sentences covering the whole week."
2. **Revenue table** — "$2,300 of $5,000 — 46%, invoice payment rate 100%."
3. **Completed This Week** — "Three tasks completed with timestamps."
4. **Bottlenecks** — "Shows items stuck in approval too long."
5. **Proactive Suggestions** — "The AI recommends actions — like exiting dry-run mode."

> Say:
> "This isn't a template — Claude analyzed the vault, read the logs,
> checked financials, and wrote this. Every number comes from real
> data in the vault."

---

## 7. Security Demo (30 seconds)

**[Open security_checklist.md in Obsidian]**

> Say:
> "Security is built in from the start."

Quickly point to:
- "DRY_RUN is on by default"
- "Rate limiting table — 10 emails per hour, 3 payments per day"
- "All credentials from environment variables, never in the vault"
- "JSON audit logs for every action"

**[Quick flash of terminal]**:

```bash
uv run python -c "from security_config import security; print(security.all_rate_limits())"
```

> Say:
> "Rate limits are enforced in code. The AI literally cannot send
> more than 10 emails per hour, even if it wanted to."

---

## 8. Closing (30 seconds)

> Say:
> "To recap — this is a fully autonomous AI employee that:
>
> - Monitors my email and file drops 24/7
> - Creates action plans and drafts responses
> - Requires my approval for anything sensitive
> - Generates weekly briefings with financial analysis
> - Posts to LinkedIn on my behalf
> - Logs every single action for auditability
>
> Everything runs inside an Obsidian vault with Claude Code.
> It's my Gold tier submission for Hackathon 0.
>
> For next steps, I want to add WhatsApp integration, a Stripe
> payment watcher, and move from dry-run to live mode.
>
> Thanks for watching!"

**[End recording]**

---

## Pre-Recording Checklist

Before hitting record, make sure:

- [ ] Obsidian is open with the vault loaded
- [ ] Terminal is open in the vault directory
- [ ] `.env` has `DRY_RUN=true`
- [ ] `AI_Drop` folder exists on desktop and is empty
- [ ] `Needs_Action/` has some items to show
- [ ] `Pending_Approval/` has approval files to demo
- [ ] `Briefings/` has at least one briefing
- [ ] `uv sync` has been run (dependencies installed)
- [ ] Screen resolution is readable for recording (1080p+, large font)
- [ ] Close any windows with personal info / credentials

## Timing Guide

| Section | Duration | Cumulative |
|---------|----------|------------|
| Intro | 0:30 | 0:30 |
| Vault Tour | 1:00 | 1:30 |
| File Watcher | 2:00 | 3:30 |
| Claude Processing | 2:00 | 5:30 |
| Approval Workflow | 2:00 | 7:30 |
| CEO Briefing | 1:00 | 8:30 |
| Security | 0:30 | 9:00 |
| Closing | 0:30 | 9:30 |

**Total: ~9.5 minutes** (within 5-10 minute target)

## Tips

- Speak slowly and clearly — you can always speed up the video in editing
- Pause for 2-3 seconds on important screens so viewers can read
- If a command takes time, narrate what's happening while you wait
- If something goes wrong, keep recording — troubleshooting live shows authenticity
- Keep the `.env` file off-screen to avoid leaking paths or credentials
