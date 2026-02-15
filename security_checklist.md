---
type: security_checklist
last_reviewed: 2026-02-15
review_frequency: weekly
---

# Security Checklist — AI Employee

## DRY_RUN Mode

- [x] `DRY_RUN=true` is the default in `.env` and `security_config.py`
- [x] All modules read DRY_RUN from `security_config.security.dry_run` (single source of truth)
- [x] `orchestrator.py` respects DRY_RUN — skips skill execution and logs instead
- [x] `ralph_loop.py` respects DRY_RUN — simulates Claude Code calls
- [x] `linkedin_mcp.py` respects DRY_RUN — logs posts without publishing
- [x] `filesystem_watcher.py` — file ingestion is always active (read-only, safe by design)
- [ ] Set `DRY_RUN=false` only after verifying all integrations in production

## Rate Limiting

| Action | Limit | Window | Enforced By |
|--------|-------|--------|-------------|
| Email send | 10 | per hour | `security_config.py` |
| Payment | 3 | per day | `security_config.py` |
| Social post | 1 | per day | `security_config.py` |
| File delete | 5 | per day | `security_config.py` |

- [x] Rate limits defined in `security_config.py` with sliding-window counters
- [x] Configurable via environment variables (`MAX_EMAILS_PER_HOUR`, etc.)
- [x] `linkedin_mcp.py` checks `security.check_rate_limit("social_post")` before posting
- [x] Rate limit status included in orchestrator health check
- [ ] Rate limits enforced in `execute_approved` skill for email_send and payment actions

## Credential Management

- [x] All credentials loaded from environment variables only (`security.get_credential()`)
- [x] `.env` is in `.gitignore` — never committed
- [x] `.env.example` exists with placeholder values (no real secrets)
- [x] `secrets/` directory is in `.gitignore`
- [x] OAuth tokens stored in `secrets/` directory, excluded from git
- [x] `*_token.json`, `*.credentials`, `*.key`, `*.pem` all in `.gitignore`
- [ ] Rotate LinkedIn access token before expiration (60-day default)
- [ ] Rotate Gmail OAuth refresh token if compromised

## Audit Logging

- [x] JSON-lines audit logs written to `Logs/audit/audit_YYYY-MM-DD.jsonl`
- [x] Every action logged with: timestamp, action_type, actor, target, dry_run, result
- [x] Audit logs are in `.gitignore` (contain action details)
- [x] `orchestrator.py` logs: start/stop, skill runs (success/fail/dry_run)
- [x] `linkedin_mcp.py` logs: profile fetches, post attempts, rate limit hits
- [x] `base_watcher.py` logs: action file creation
- [x] `filesystem_watcher.py` logs: file copy operations
- [x] `ralph_loop.py` logs: task execution iterations

### Audit Log Format
```json
{
  "timestamp": "2026-02-15T08:55:00+00:00",
  "action_type": "social_post",
  "actor": "linkedin_mcp",
  "target": "create_post",
  "dry_run": true,
  "result": "dry_run",
  "metadata": {"chars": 839}
}
```

### Valid `action_type` Values
| Type | Description |
|------|-------------|
| `email_send` | Sending an email |
| `payment` | Processing a payment |
| `social_post` | Publishing to social media |
| `file_op` | File create, copy, move, or delete |
| `file_delete` | Specifically deleting a file |
| `skill_run` | Executing a Claude Code skill |
| `auth` | Authentication events |
| `system` | System start/stop/health events |

### Valid `actor` Values
| Actor | Description |
|-------|-------------|
| `orchestrator` | Main orchestration loop |
| `watcher` | Base watcher / filesystem watcher |
| `ralph_loop` | Persistent task runner |
| `linkedin_mcp` | LinkedIn MCP server |
| `claude_code` | Direct Claude Code execution |
| `user` | Manual human action |

### Valid `result` Values
| Result | Description |
|--------|-------------|
| `success` | Action completed |
| `failed` | Action failed with error |
| `dry_run` | Simulated in DRY_RUN mode |
| `pending_approval` | Awaiting human approval |
| `rate_limited` | Blocked by rate limiter |
| `denied` | Blocked by security policy |

## Protected Files

These files/directories must never be deleted, even with approval:

- `/.obsidian/*` — Obsidian workspace config
- `/.claude/*` — Claude Code skills and settings
- `/.git/*` — Git repository data
- `/.gitkeep` — Folder structure markers
- `/Company_Handbook.md` — AI Employee rules
- `/Business_Goals.md` — Business objectives
- `/Dashboard.md` — System dashboard
- `/Welcome.md` — Vault welcome page
- `/security_config.py` — Security configuration

- [x] Protected paths defined in `security_config.SecurityConfig.protected_paths`
- [x] `security.is_protected(path)` check available for all modules

## Approval Workflow

| Action | Requires Approval? |
|--------|-------------------|
| Read emails / files | No |
| Draft email to known contact | No |
| Send email to known contact | Yes |
| Send email to new contact | Always |
| Any payment action | Always |
| Social media post | Yes |
| File delete | Always |

- [x] Approval workflow enforced via `/Pending_Approval/` folder
- [x] Expired approvals rejected (72-hour default for social posts)
- [x] All approval decisions logged to audit trail

## Environment Variables Reference

### Required
| Variable | Description |
|----------|-------------|
| `VAULT_PATH` | Absolute path to the Obsidian vault |

### Optional (with defaults)
| Variable | Default | Description |
|----------|---------|-------------|
| `DRY_RUN` | `true` | Enable dry-run mode |
| `DROP_FOLDER` | — | File drop folder path |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `MAX_EMAILS_PER_HOUR` | `10` | Email rate limit |
| `MAX_PAYMENTS_PER_DAY` | `3` | Payment rate limit |
| `MAX_SOCIAL_POSTS_PER_DAY` | `1` | Social post rate limit |
| `MAX_FILE_DELETES_PER_DAY` | `5` | File delete rate limit |

### Credentials (never commit)
| Variable | Description |
|----------|-------------|
| `LINKEDIN_CLIENT_ID` | LinkedIn OAuth app ID |
| `LINKEDIN_CLIENT_SECRET` | LinkedIn OAuth secret |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn access token |
| `LINKEDIN_TOKEN_PATH` | Path to token file |
| `GMAIL_CREDENTIALS_PATH` | Google OAuth credentials |
| `GMAIL_TOKEN_PATH` | Gmail token file path |

## Pre-Production Checklist

Before setting `DRY_RUN=false`:

- [ ] All tests pass with DRY_RUN=true
- [ ] Audit logs are being written correctly to `Logs/audit/`
- [ ] Rate limits are configured appropriately for workload
- [ ] All credentials are loaded from environment, not hardcoded
- [ ] `.env` is NOT in version control (verify with `git status`)
- [ ] `secrets/` directory is NOT in version control
- [ ] Protected file list is complete and enforced
- [ ] Approval workflow tested end-to-end (Pending -> Approved -> Done)
- [ ] Backup strategy in place for vault data
- [ ] Monitoring configured for critical errors in Orchestrator.log

---
*Last reviewed: 2026-02-15 by AI Employee*
*Next review: 2026-02-22*
