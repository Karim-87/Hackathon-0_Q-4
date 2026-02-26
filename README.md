# Personal AI Employee - Hackathon 0

> An autonomous AI employee that manages emails, WhatsApp messages, files, payments, and social media inside an Obsidian vault — with human-in-the-loop approval for every sensitive action.

**Tier: Gold**

---

## Architecture Overview

```
                          +------------------+
                          |    Human (CEO)   |
                          |  Obsidian Vault  |
                          +--------+---------+
                                   |
                       approve / reject / review
                                   |
     +-----------------------------+-----------------------------+
     |                             |                             |
+----v-------+          +----------v---------+          +--------v--------+
|  Pending   |          |     Dashboard      |          |    Briefings    |
|  Approval  |          |   (live status)    |          | (weekly report) |
+----+-------+          +--------------------+          +-----------------+
     |                             ^
     | moved to /Approved/         | update_dashboard skill
     v                             |
+----+-------+          +----------+---------+          +-----------------+
|  Approved  +--------->+   Orchestrator     +--------->+      Done       |
|            |  execute |  (main.py loop)    |  result  |   (completed)   |
+------------+          +--+--+--+--+--------+          +-----------------+
                           |  |  |  |
               skill       |  |  |  |      skill
              dispatch     |  |  |  |     dispatch
                           v  v  v  v
              +-----------+--+--+--+------------+
              |           |        |             |
        +-----+--+ +------+-+ +----+---+ +-------+----+
        | process | | create | |  CEO   | | whatsapp   |
        |  inbox  | |  plan  | |briefing| |  monitor   |
        +---------+ +--------+ +--------+ +------------+
              ^                                  |
              |                                  v
 +------------+------------+         +-----------+---------+
 |            |            |         |  WhatsApp MCP Server|
 v            v            v         +---------------------+
+----+----+ +----+----+ +--+-------+
| Gmail   | |Filesystem| |WhatsApp  |
| Watcher | | Watcher  | | Watcher  |
+---------+ +----------+ +----------+
     |            |            |
     v            v            v
  Gmail API   Drop Folder  WhatsApp Web
              (desktop)    (whatsapp-web.js)
```

### Data Flow

```
External Input ──> Watchers ──> /Needs_Action/ ──> Orchestrator ──> /Plans/
                                                        |
                                                        v
                                                /Pending_Approval/
                                                        |
                                                  Human reviews
                                                        |
                                              /Approved/ or /Rejected/
                                                        |
                                                        v
                                              execute_approved skill
                                                        |
                                                        v
                                                    /Done/ + /Logs/
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime (Python) | Python 3.14+ |
| Runtime (Node.js) | Node.js 20+ |
| Package Manager (Python) | [uv](https://docs.astral.sh/uv/) |
| Package Manager (Node) | npm |
| AI Engine | Claude Code CLI (Anthropic) |
| Vault / UI | Obsidian (markdown-based knowledge base) |
| File Monitoring | watchdog |
| Email Integration | Gmail API (google-api-python-client) |
| WhatsApp Integration | whatsapp-web.js (Node.js MCP server) |
| Social Media | LinkedIn API via MCP server |
| Auth | OAuth 2.0 (Google, LinkedIn), WhatsApp QR session |
| Config | python-dotenv / dotenv (.env files) |
| Security | Custom rate limiter, JSON audit logging, DRY_RUN mode |

---

## Setup Instructions

### Prerequisites

- Python 3.14+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) package manager
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- [Obsidian](https://obsidian.md/) (optional, for vault UI)

### 1. Clone the Repository

```bash
git clone https://github.com/Karim-87/personal-ai-employee.git
cd personal-ai-employee
```

### 2. Install Python Dependencies

```bash
uv sync
```

### 3. Install Node.js Dependencies (WhatsApp)

```bash
cd ai-employee-project
npm install
cd ..
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
VAULT_PATH=/path/to/AI_Employee_Vault
DROP_FOLDER=/path/to/desktop/AI_Drop
DRY_RUN=true
LOG_LEVEL=INFO

# Gmail API (optional)
GMAIL_CREDENTIALS_PATH=/path/to/secrets/credentials.json
GMAIL_TOKEN_PATH=/path/to/secrets/gmail_token.json

# LinkedIn API (optional)
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret
LINKEDIN_TOKEN_PATH=/path/to/secrets/linkedin_token.json
```

### 5. Create the Drop Folder

```bash
mkdir -p ~/Desktop/AI_Drop
```

### 6. Set Up WhatsApp (Optional)

```bash
# Start the watcher — it will show a QR code in the terminal
cd ai-employee-project
node whatsapp_watcher.js
```

1. Scan the QR code with your phone: **WhatsApp → Settings → Linked Devices → Link a Device**
2. Wait for `Connected: [Your Name]` message
3. Session is saved to `.wwebjs_auth/` — no re-scan needed on restart

> **Security**: `.wwebjs_auth/` is gitignored. Never commit session files.

### 7. Set Up Gmail API (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download `credentials.json` to `secrets/`
5. Run the watcher once to authorize: `uv run python gmail_watcher.py`

### 8. Set Up LinkedIn API (Optional)

1. Register an app at [LinkedIn Developers](https://www.linkedin.com/developers/)
2. Request products: "Share on LinkedIn" and "Sign In with LinkedIn using OpenID Connect"
3. Set redirect URL to `http://localhost:8914/callback`
4. Add client ID and secret to `.env`
5. Run the OAuth flow: `uv run python linkedin_mcp.py --auth`

### 9. Verify Installation

```bash
uv run python -c "from orchestrator import Orchestrator; print('OK')"
node -e "const { Client } = require('./ai-employee-project/node_modules/whatsapp-web.js'); console.log('WhatsApp OK')"
```

---

## How to Run

### Start the Orchestrator (Main Loop)

```bash
# Dry-run mode (default — safe, no external actions)
uv run python main.py

# Force dry-run via flag
uv run python main.py --dry-run

# Check health status
uv run python main.py --health
```

### Run Individual Watchers

```bash
# File system watcher (monitors drop folder)
uv run python filesystem_watcher.py

# Gmail watcher (polls every 2 minutes)
uv run python gmail_watcher.py

# WhatsApp watcher (real-time messages)
cd ai-employee-project && node whatsapp_watcher.js
```

### Run the Ralph Loop (Multi-Step Tasks)

```bash
uv run python ralph_loop.py "Process all files in /Needs_Action and create plans"
uv run python ralph_loop.py "Generate CEO briefing" --max-iterations 3
uv run python ralph_loop.py "Handle inbox" --dry-run
```

### WhatsApp MCP Server (for Claude Code integration)

```bash
# Registered automatically via .claude/mcp.json
# To start manually:
cd ai-employee-project && node whatsapp_mcp.js
```

### LinkedIn MCP Server

```bash
uv run python linkedin_mcp.py --auth      # Authenticate
uv run python linkedin_mcp.py --test      # Test connection
uv run python linkedin_mcp.py --dry-post "Post content"
uv run python linkedin_mcp.py             # Start MCP server
```

---

## Folder Structure

```
AI_Employee_Vault/              # Python vault (main project)
├── .claude/
│   ├── skills/                 # Claude Code skill definitions (11 skills)
│   └── mcp.json                # MCP server registrations
├── .env                        # Environment config (gitignored)
├── .env.example                # Template for .env setup
│
├── main.py                     # Entry point — starts orchestrator
├── orchestrator.py             # Master process — coordinates all skills
├── base_watcher.py             # Abstract base class for watchers
├── filesystem_watcher.py       # Monitors drop folder for new files
├── gmail_watcher.py            # Polls Gmail for unread emails
├── linkedin_mcp.py             # LinkedIn MCP server (post, profile)
├── ralph_loop.py               # Persistent task execution loop
├── security_config.py          # Centralized security controls
│
├── Company_Handbook.md         # AI Employee rules and autonomy levels
├── Business_Goals.md           # Revenue targets and KPIs
├── Dashboard.md                # Live system status (auto-updated)
├── security_checklist.md       # Security audit checklist
│
├── Needs_Action/               # Inbox — new items land here
│   ├── emails/                 #   Incoming emails from Gmail
│   ├── files/                  #   Dropped files from desktop
│   ├── messages/               #   WhatsApp messages
│   └── media/                  #   WhatsApp media downloads
├── Plans/                      # Action plans created by AI
├── Pending_Approval/           # Items awaiting human review
├── Approved/                   # Human-approved, ready to execute
├── Rejected/                   # Rejected items (audit trail)
├── In_Progress/                # Tasks currently being worked on
├── Done/                       # Completed tasks
├── Briefings/                  # CEO briefings + WhatsApp daily summaries
├── Accounting/                 # Financial records
├── Invoices/                   # Invoice tracking
├── Active_Projects/            # Project files and status
├── Logs/
│   ├── audit/                  #   JSON audit trail (gitignored)
│   ├── whatsapp/               #   WhatsApp daily logs
│   ├── *.log                   #   Per-component log files
│   └── YYYY-MM-DD.md           #   Daily structured logs
└── secrets/                    # OAuth tokens (gitignored)

ai-employee-project/            # Node.js project (WhatsApp)
├── whatsapp_session.js         # QR scan + session manager
├── whatsapp_watcher.js         # Real-time message monitor → vault files
├── whatsapp_mcp.js             # MCP server (8 tools for Claude Code)
├── package.json
└── .wwebjs_auth/               # WhatsApp session data (gitignored)
```

### Workflow Folders (State Machine)

```
Needs_Action → Plans → Pending_Approval → Approved → In_Progress → Done
                                       ↘ Rejected
```

---

## Skills

Skills are markdown instruction files in `.claude/skills/` that tell Claude Code how to perform specific tasks.

| Skill | Description | Auto-Approve? |
|-------|-------------|---------------|
| **process_inbox** | Scans `/Needs_Action/` for new emails, files, and messages. Classifies each item, creates action plans, and routes to approval if needed. | Yes (read-only) |
| **create_plan** | Analyzes items and generates detailed step-by-step action plans in `/Plans/` with approval requirements and success criteria. | Yes (file create) |
| **approval_handler** | Manages the full approval lifecycle: processes pending items, executes approved actions, logs rejected items. | No (executes actions) |
| **execute_approved** | Execution engine for approved actions (email send, payment, social post, WhatsApp reply, file delete) with rate limits, expiration checks, and DRY_RUN support. | No (external actions) |
| **update_dashboard** | Aggregates all workflow folders and logs into a live-updating `/Dashboard.md` with counts, financial summary, WhatsApp status, and alerts. | Yes (file update) |
| **ceo_briefing** | Generates weekly Monday morning briefings with revenue analysis, completed tasks, bottlenecks, system health, and proactive suggestions. | Yes (reporting) |
| **linkedin_poster** | Reads business context and generates professional LinkedIn posts. Creates drafts in `/Pending_Approval/` — always requires human review. | No (social media) |
| **file_processor** | Classifies dropped files (invoice, report, config, etc.) and routes them to the appropriate vault folder with metadata. | Yes (classification) |
| **whatsapp_monitor** | Processes incoming WhatsApp messages, drafts replies for approval, routes invoice/payment requests to financial workflow. | Yes (read/draft) |
| **whatsapp_summary** | Generates daily WhatsApp activity summary at 9 PM — chat counts, key topics, action items, pending replies. | Yes (reporting) |
| **whatsapp_reply** | Executes approved WhatsApp replies. Respects DRY_RUN mode, writes audit log, moves task to Done. | No (external send) |

---

## WhatsApp MCP Tools

The `whatsapp_mcp.js` server exposes 8 tools to Claude Code:

| Tool | Description | Approval? |
|------|-------------|-----------|
| `whatsapp_send_message` | Send a message to any contact | Always (creates approval file) |
| `whatsapp_get_chats` | List recent chats with unread counts | No (read-only) |
| `whatsapp_get_messages` | Fetch messages from a specific chat | No (read-only) |
| `whatsapp_search_messages` | Search messages across all chats | No (read-only) |
| `whatsapp_get_chat_summary` | AI-ready summary for today/week/month | No (read-only) |
| `whatsapp_delete_message` | Delete a message | Always (creates approval file) |
| `whatsapp_mark_read` | Mark a chat as read | No (auto-approved) |
| `whatsapp_get_contacts` | List all contacts | No (read-only) |

---

## Security Measures

### DRY_RUN Mode (Default: ON)

All external actions are simulated by default. Nothing is sent, posted, or paid until `DRY_RUN=false` is explicitly set in `.env`.

### Human-in-the-Loop Approval

| Action | Approval Required |
|--------|-------------------|
| Read emails / files / messages | No |
| Draft reply to known contact | No |
| Send email (any) | Yes |
| Send WhatsApp to known contact | Yes |
| Send WhatsApp to new/unknown number | Always |
| Any payment action | Always |
| Social media post | Yes |
| Delete message / file | Always |

### Rate Limiting

| Action | Limit | Window |
|--------|-------|--------|
| Email send | 10 | per hour |
| WhatsApp send | 20 | per hour |
| Payment | 3 | per day |
| Social post | 1 | per day |
| File delete | 5 | per day |
| WhatsApp message processing | 100 | per hour |

### Audit Logging

Every action is logged to `Logs/audit/` in JSON-lines format:

```json
{
  "timestamp": "2026-02-26T17:37:09+00:00",
  "action_type": "whatsapp_send",
  "actor": "whatsapp_reply_skill",
  "target": "923001234567",
  "dry_run": false,
  "result": "success"
}
```

### Credential Security

- All secrets loaded from environment variables only (never hardcoded)
- `.env` and `secrets/` are gitignored
- WhatsApp session data (`.wwebjs_auth/`) is gitignored
- OAuth tokens stored outside the vault in `secrets/`
- Protected files list prevents deletion of critical vault files

See [security_checklist.md](security_checklist.md) for the full security audit checklist.

---

## Demo

> Video demo placeholder — link to be added after recording.

[Watch the Demo Video](#) <!-- Replace with actual video link -->

---

## Tier Declaration

### Gold

This project qualifies for Gold tier with:

- **Autonomous orchestration** — watchers, state machine, scheduled tasks
- **Multiple integrations** — Gmail API, LinkedIn API (MCP), WhatsApp (MCP), file system
- **Human-in-the-loop** — approval workflow via Obsidian vault folders
- **Security architecture** — DRY_RUN mode, rate limiting, JSON audit logs, credential isolation
- **11 Claude Code skills** — inbox processing, planning, execution, reporting, social media, WhatsApp
- **Persistent task runner** — Ralph Loop with context re-injection across iterations
- **CEO briefing system** — automated weekly reports with financial analysis
- **2 MCP servers** — LinkedIn + WhatsApp, both following Model Context Protocol
- **Full observability** — structured daily logs, audit trail, health checks, dashboard
- **WhatsApp integration** — real-time message monitoring, media download, group filtering, auto-reconnect

---

## Author

**Karim-87** — [GitHub](https://github.com/Karim-87)

Built for Hackathon 0, Q4 2025.

---

## License

MIT License

Copyright (c) 2025 Karim-87

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
