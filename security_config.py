"""Security configuration — single source of truth for all safety controls.

Centralizes DRY_RUN enforcement, rate limiting, credential loading, and
structured JSON audit logging for the AI Employee system.

Usage:
    from security_config import security, audit_log

    # Check mode before any action
    if security.dry_run:
        print("Simulating action...")

    # Rate-limit check before sending
    if not security.check_rate_limit("email_send"):
        print("Rate limit exceeded")

    # Log every action
    audit_log(
        action_type="email_send",
        actor="orchestrator",
        target="client@example.com",
        result="success",
    )
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("Security")


# ── Rate Limit Storage ─────────────────────────────────────────────

class _RateLimitBucket:
    """Sliding-window rate limiter for a single action type."""

    def __init__(self, max_count, window_seconds):
        self.max_count = max_count
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []
        self._lock = Lock()

    def allow(self):
        """Return True if the action is allowed, False if rate-limited."""
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            if len(self._timestamps) >= self.max_count:
                return False
            self._timestamps.append(now)
            return True

    def current_count(self):
        """Return number of actions in the current window."""
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            return len(self._timestamps)

    def reset(self):
        """Clear all recorded timestamps."""
        with self._lock:
            self._timestamps.clear()


# ── Security Configuration ─────────────────────────────────────────

class SecurityConfig:
    """Central security configuration loaded from environment variables."""

    def __init__(self):
        # ── DRY_RUN ────────────────────────────────────────────────
        # Default to True — safety first. Must explicitly set to "false".
        self.dry_run = os.getenv("DRY_RUN", "true").lower() != "false"

        # ── Paths ──────────────────────────────────────────────────
        self.vault_path = Path(os.getenv("VAULT_PATH", "."))
        self.logs_dir = self.vault_path / "Logs"
        self.audit_dir = self.logs_dir / "audit"

        # ── Rate Limits (from Company Handbook) ────────────────────
        self.max_emails_per_hour = int(os.getenv("MAX_EMAILS_PER_HOUR", "10"))
        self.max_payments_per_day = int(os.getenv("MAX_PAYMENTS_PER_DAY", "3"))
        self.max_social_posts_per_day = int(os.getenv("MAX_SOCIAL_POSTS_PER_DAY", "1"))
        self.max_file_deletes_per_day = int(os.getenv("MAX_FILE_DELETES_PER_DAY", "5"))

        self._rate_limiters = {
            "email_send": _RateLimitBucket(self.max_emails_per_hour, 3600),
            "payment": _RateLimitBucket(self.max_payments_per_day, 86400),
            "social_post": _RateLimitBucket(self.max_social_posts_per_day, 86400),
            "file_delete": _RateLimitBucket(self.max_file_deletes_per_day, 86400),
        }

        # ── Protected Paths ────────────────────────────────────────
        self.protected_paths = frozenset([
            ".obsidian",
            ".claude",
            ".git",
            ".gitkeep",
            "Company_Handbook.md",
            "Business_Goals.md",
            "Dashboard.md",
            "Welcome.md",
            "security_config.py",
        ])

        # ── Ensure directories ─────────────────────────────────────
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        # ── Startup log ───────────────────────────────────────────
        logger.info(
            f"Security config loaded: dry_run={self.dry_run}, "
            f"vault={self.vault_path}, "
            f"rate_limits=[email={self.max_emails_per_hour}/h, "
            f"payment={self.max_payments_per_day}/d, "
            f"social={self.max_social_posts_per_day}/d]"
        )

    # ── Rate Limiting ──────────────────────────────────────────────

    def check_rate_limit(self, action_type):
        """Return True if action is within rate limits. Logs if denied."""
        bucket = self._rate_limiters.get(action_type)
        if bucket is None:
            return True  # No limit defined for this action type

        allowed = bucket.allow()
        if not allowed:
            logger.warning(
                f"RATE LIMIT EXCEEDED: {action_type} "
                f"({bucket.current_count()}/{bucket.max_count} "
                f"in {bucket.window_seconds}s window)"
            )
        return allowed

    def rate_limit_status(self, action_type):
        """Return (current_count, max_count) for an action type."""
        bucket = self._rate_limiters.get(action_type)
        if bucket is None:
            return (0, -1)
        return (bucket.current_count(), bucket.max_count)

    def all_rate_limits(self):
        """Return a dict of all rate limit statuses."""
        return {
            action: {
                "current": bucket.current_count(),
                "max": bucket.max_count,
                "window_seconds": bucket.window_seconds,
            }
            for action, bucket in self._rate_limiters.items()
        }

    # ── Path Protection ────────────────────────────────────────────

    def is_protected(self, filepath):
        """Return True if the filepath is a protected vault file/directory."""
        path = Path(filepath)
        # Check each component of the path against protected names
        for part in path.parts:
            if part in self.protected_paths:
                return True
        if path.name in self.protected_paths:
            return True
        return False

    # ── Credential Access ──────────────────────────────────────────

    @staticmethod
    def get_credential(name, required=False):
        """Load a credential from environment variables only.

        Never reads credentials from files in the vault — all secrets
        must come from .env or the system environment.
        """
        value = os.getenv(name)
        if required and not value:
            raise ValueError(
                f"Required credential '{name}' not set in environment. "
                f"Add it to your .env file."
            )
        return value or ""

    # ── DRY_RUN Guard ──────────────────────────────────────────────

    def require_live_mode(self, action_description):
        """Raise if DRY_RUN is enabled. Use before any real external action."""
        if self.dry_run:
            raise PermissionError(
                f"DRY_RUN is enabled — cannot execute: {action_description}. "
                f"Set DRY_RUN=false in .env to enable live actions."
            )


# ── JSON Audit Logger ──────────────────────────────────────────────

def audit_log(
    action_type,
    actor,
    target,
    result,
    dry_run=None,
    metadata=None,
):
    """Write a structured JSON audit log entry.

    Each day gets its own JSON-lines file in /Logs/audit/.

    Args:
        action_type: email_send, payment, file_op, social_post, skill_run,
                     file_delete, auth, system, etc.
        actor: claude_code, watcher, orchestrator, ralph_loop, linkedin_mcp, user
        target: Description of what was acted upon
        result: success, failed, pending_approval, rate_limited, dry_run, denied
        dry_run: Override for dry_run flag (defaults to security.dry_run)
        metadata: Optional dict of extra fields
    """
    if dry_run is None:
        dry_run = security.dry_run

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": actor,
        "target": target,
        "dry_run": dry_run,
        "result": result,
    }

    if metadata:
        entry["metadata"] = metadata

    # Write to daily JSON-lines audit file
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    audit_file = security.audit_dir / f"audit_{today}.jsonl"

    try:
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        logger.error(f"Failed to write audit log: {e}")

    # Also emit to Python logger for console/file output
    log_line = (
        f"[AUDIT] {action_type} | actor={actor} | target={target} | "
        f"result={result} | dry_run={dry_run}"
    )
    if result == "failed":
        logger.warning(log_line)
    elif result == "denied" or result == "rate_limited":
        logger.warning(log_line)
    else:
        logger.info(log_line)

    return entry


# ── Module-level singleton ─────────────────────────────────────────

security = SecurityConfig()
