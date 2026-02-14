"""Orchestrator — master process that coordinates all AI Employee skills.

Watches vault folders for changes and dispatches the appropriate skill
via Claude Code CLI. Manages scheduling, health checks, and error recovery.

Usage:
    python orchestrator.py              # Run with .env config
    python orchestrator.py --dry-run    # Log actions without executing skills
    python orchestrator.py --health     # Print health status and exit
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Event, Lock, Thread

from dotenv import load_dotenv


# ── State Machine ───────────────────────────────────────────────────

class State(Enum):
    IDLE = "IDLE"
    DETECTED = "DETECTED"
    PROCESSING = "PROCESSING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    DONE = "DONE"


class ItemTracker:
    """Tracks the state of an individual item through the pipeline."""

    def __init__(self, filepath, item_type):
        self.filepath = filepath
        self.item_type = item_type
        self.state = State.DETECTED
        self.created_at = datetime.now(timezone.utc)
        self.last_updated = self.created_at
        self.retries = 0
        self.error = None

    def transition(self, new_state):
        self.state = new_state
        self.last_updated = datetime.now(timezone.utc)

    def to_dict(self):
        return {
            "file": self.filepath.name,
            "type": self.item_type,
            "state": self.state.value,
            "created": self.created_at.isoformat(),
            "updated": self.last_updated.isoformat(),
            "retries": self.retries,
            "error": self.error,
        }


# ── Orchestrator ────────────────────────────────────────────────────

class Orchestrator:
    """Master process that coordinates all AI Employee skills."""

    SCAN_INTERVAL = 15          # seconds between folder scans
    DASHBOARD_INTERVAL = 1800   # 30 minutes
    BRIEFING_DAY = 6            # Sunday (0=Monday in weekday())
    BRIEFING_HOUR = 23          # 11 PM

    MAX_RETRIES = 1             # retry once on failure, then alert
    CLAUDE_TIMEOUT = 120        # seconds to wait for Claude Code

    def __init__(self, vault_path, dry_run=False):
        self.vault_path = Path(vault_path)
        self.dry_run = dry_run
        self._running = False
        self._stop_event = Event()
        self._lock = Lock()

        # Vault folders to watch
        self.needs_action = self.vault_path / "Needs_Action"
        self.approved = self.vault_path / "Approved"
        self.pending_approval = self.vault_path / "Pending_Approval"
        self.done = self.vault_path / "Done"
        self.logs_dir = self.vault_path / "Logs"

        # Track known files to detect new arrivals
        self._known_needs_action = set()
        self._known_approved = set()

        # Track items in the pipeline
        self._items: dict[str, ItemTracker] = {}

        # Scheduling
        self._last_dashboard_update = 0.0
        self._last_briefing_check = ""

        # Health metrics
        self._start_time = None
        self._total_scans = 0
        self._total_skills_run = 0
        self._total_errors = 0
        self._last_error = None

        self._validate_vault()
        self._setup_logging()
        self._setup_signals()

    @classmethod
    def from_env(cls):
        """Create orchestrator from .env configuration."""
        load_dotenv()
        vault_path = os.getenv("VAULT_PATH")
        dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

        if not vault_path:
            raise ValueError("VAULT_PATH not set in .env file")

        return cls(vault_path=vault_path, dry_run=dry_run)

    # ── Setup ───────────────────────────────────────────────────────

    def _validate_vault(self):
        if not self.vault_path.exists():
            raise FileNotFoundError(f"Vault not found: {self.vault_path}")
        for folder in [self.needs_action, self.approved, self.pending_approval,
                        self.done, self.logs_dir]:
            folder.mkdir(parents=True, exist_ok=True)

    def _setup_logging(self):
        self.logger = logging.getLogger("Orchestrator")
        self.logger.setLevel(logging.DEBUG)

        if self.logger.handlers:
            return

        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        self.logger.addHandler(console)

        log_file = self.logs_dir / "Orchestrator.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def _setup_signals(self):
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        self.logger.info("Shutdown signal received. Stopping gracefully...")
        self._running = False
        self._stop_event.set()

    # ── File Scanning ───────────────────────────────────────────────

    def _scan_folder(self, folder):
        """Return set of .md file paths in folder, excluding .gitkeep and templates."""
        files = set()
        if not folder.exists():
            return files
        for f in folder.rglob("*.md"):
            if f.name in (".gitkeep", "TEMPLATE_approval.md"):
                continue
            files.add(f)
        return files

    def _detect_new_needs_action(self):
        """Check for new files in /Needs_Action/."""
        current = self._scan_folder(self.needs_action)
        new_files = current - self._known_needs_action
        self._known_needs_action = current
        return new_files

    def _detect_new_approved(self):
        """Check for new files in /Approved/."""
        current = self._scan_folder(self.approved)
        new_files = current - self._known_approved
        self._known_approved = current
        return new_files

    # ── Skill Execution ─────────────────────────────────────────────

    def _run_skill(self, skill_name, context=""):
        """Execute a Claude Code skill via CLI. Returns True on success."""
        prompt = self._build_prompt(skill_name, context)

        if self.dry_run:
            self.logger.info(f"DRY RUN — would run skill: {skill_name}")
            self._log_event("skill_dry_run", skill_name=skill_name, context=context)
            self._total_skills_run += 1
            return True

        self.logger.info(f"Running skill: {skill_name}")
        try:
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions", prompt],
                capture_output=True,
                text=True,
                timeout=self.CLAUDE_TIMEOUT,
                cwd=str(self.vault_path),
            )

            if result.returncode == 0:
                self.logger.info(f"Skill completed: {skill_name}")
                self._total_skills_run += 1
                self._log_event("skill_success", skill_name=skill_name)
                return True
            else:
                self.logger.error(
                    f"Skill failed: {skill_name} (exit code {result.returncode})\n"
                    f"stderr: {result.stderr[:500]}"
                )
                self._log_event("skill_failed", skill_name=skill_name,
                                error=result.stderr[:200])
                return False

        except subprocess.TimeoutExpired:
            self.logger.error(f"Skill timed out after {self.CLAUDE_TIMEOUT}s: {skill_name}")
            self._log_event("skill_timeout", skill_name=skill_name)
            return False
        except FileNotFoundError:
            self.logger.error(
                "Claude Code CLI not found. Install it or add to PATH."
            )
            self._log_event("skill_error", skill_name=skill_name,
                            error="claude CLI not found")
            return False

    def _run_skill_with_retry(self, skill_name, context=""):
        """Run a skill, retry once on failure, then alert."""
        success = self._run_skill(skill_name, context)

        if not success:
            self.logger.warning(f"Retrying skill: {skill_name} (attempt 2/{self.MAX_RETRIES + 1})")
            time.sleep(5)
            success = self._run_skill(skill_name, context)

            if not success:
                self._total_errors += 1
                self._last_error = {
                    "skill": skill_name,
                    "time": datetime.now(timezone.utc).isoformat(),
                    "context": context[:100],
                }
                self._create_alert(skill_name)

        return success

    def _build_prompt(self, skill_name, context=""):
        """Build the Claude Code prompt for a skill invocation."""
        skill_path = self.vault_path / ".claude" / "skills" / f"{skill_name}.md"
        base = f"Read and follow the skill instructions in {skill_path}."
        if context:
            base += f" Context: {context}"
        return base

    # ── Alerting ────────────────────────────────────────────────────

    def _create_alert(self, skill_name):
        """Create an alert file when a skill fails after retry."""
        now = datetime.now(timezone.utc)
        filename = f"ALERT_skill_failure_{now.strftime('%Y%m%d_%H%M%S')}.md"
        alert_path = self.needs_action / filename

        content = (
            f"---\n"
            f"type: alert\n"
            f"severity: high\n"
            f"created: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            f"status: pending\n"
            f"---\n\n"
            f"# Alert: Skill Execution Failed\n\n"
            f"**Skill**: `{skill_name}`\n"
            f"**Time**: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"**Retries**: {self.MAX_RETRIES + 1} attempts (all failed)\n\n"
            f"## Action Required\n"
            f"Check Orchestrator.log for error details and resolve manually.\n"
        )

        alert_path.write_text(content, encoding="utf-8")
        self.logger.critical(f"Alert created: {filename}")

    # ── Logging ─────────────────────────────────────────────────────

    def _log_event(self, event_type, **details):
        """Append a structured event to today's daily log."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"{today}.md"
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")

        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        entry = f"- `{now}` | **{event_type}** | {detail_str}\n"

        # Create file with header if it doesn't exist
        if not log_file.exists():
            header = (
                f"---\ndate: {today}\ntype: daily_log\n---\n\n"
                f"# Daily Log — {today}\n\n"
                f"## Orchestrator Events\n\n"
            )
            log_file.write_text(header + entry, encoding="utf-8")
        else:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry)

    # ── Scheduling ──────────────────────────────────────────────────

    def _should_update_dashboard(self):
        """Return True if 30 minutes have passed since last dashboard update."""
        return (time.time() - self._last_dashboard_update) >= self.DASHBOARD_INTERVAL

    def _should_run_briefing(self):
        """Return True if it's Sunday 11PM and briefing hasn't run today."""
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")

        if (now.weekday() == self.BRIEFING_DAY
                and now.hour == self.BRIEFING_HOUR
                and self._last_briefing_check != today_str):
            self._last_briefing_check = today_str
            return True
        return False

    # ── Health Check ────────────────────────────────────────────────

    def health_status(self):
        """Return a dict with current health metrics."""
        now = datetime.now(timezone.utc)
        uptime = (now - self._start_time).total_seconds() if self._start_time else 0

        # Count files in key folders
        needs_action_count = len(self._scan_folder(self.needs_action))
        approved_count = len(self._scan_folder(self.approved))
        pending_count = len(self._scan_folder(self.pending_approval))

        return {
            "status": "running" if self._running else "stopped",
            "uptime_seconds": int(uptime),
            "uptime_human": self._format_uptime(uptime),
            "dry_run": self.dry_run,
            "vault_path": str(self.vault_path),
            "total_scans": self._total_scans,
            "total_skills_run": self._total_skills_run,
            "total_errors": self._total_errors,
            "last_error": self._last_error,
            "active_items": len(self._items),
            "queue": {
                "needs_action": needs_action_count,
                "approved": approved_count,
                "pending_approval": pending_count,
            },
            "items": [item.to_dict() for item in self._items.values()],
            "timestamp": now.isoformat(),
        }

    def write_health_file(self):
        """Write health status to a JSON file for external monitoring."""
        health_file = self.vault_path / ".claude" / "health.json"
        health_file.parent.mkdir(parents=True, exist_ok=True)
        health_file.write_text(
            json.dumps(self.health_status(), indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _format_uptime(seconds):
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        if minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    # ── Main Loop ───────────────────────────────────────────────────

    def run(self):
        """Main orchestration loop."""
        self._running = True
        self._start_time = datetime.now(timezone.utc)

        self.logger.info(
            f"Orchestrator started (vault={self.vault_path}, "
            f"dry_run={self.dry_run}, scan_interval={self.SCAN_INTERVAL}s)"
        )
        self._log_event("orchestrator_start", dry_run=self.dry_run)

        # Snapshot current files so we only react to new ones
        self._known_needs_action = self._scan_folder(self.needs_action)
        self._known_approved = self._scan_folder(self.approved)

        self.logger.info(
            f"Initial snapshot — Needs_Action: {len(self._known_needs_action)}, "
            f"Approved: {len(self._known_approved)}"
        )

        # Run an initial dashboard update
        self._run_skill_with_retry("update_dashboard")
        self._last_dashboard_update = time.time()

        while self._running:
            try:
                self._tick()
            except Exception as e:
                self._total_errors += 1
                self.logger.error(f"Tick error: {e}", exc_info=True)

            # Write health file each cycle
            self.write_health_file()

            # Wait for next scan or shutdown signal
            self._stop_event.wait(timeout=self.SCAN_INTERVAL)

        self._log_event("orchestrator_stop",
                        uptime=self._format_uptime(
                            (datetime.now(timezone.utc) - self._start_time).total_seconds()),
                        scans=self._total_scans,
                        skills_run=self._total_skills_run,
                        errors=self._total_errors)
        self.write_health_file()
        self.logger.info("Orchestrator stopped.")

    def _tick(self):
        """One scan cycle — check folders, run scheduled tasks."""
        self._total_scans += 1

        # 1. Check for new items in /Needs_Action/
        new_items = self._detect_new_needs_action()
        if new_items:
            self.logger.info(f"Detected {len(new_items)} new item(s) in Needs_Action")
            self._handle_new_items(new_items)

        # 2. Check for approved items in /Approved/
        new_approved = self._detect_new_approved()
        if new_approved:
            self.logger.info(f"Detected {len(new_approved)} approved item(s)")
            self._handle_approved(new_approved)

        # 3. Scheduled: dashboard update every 30 minutes
        if self._should_update_dashboard():
            self.logger.info("Scheduled dashboard update")
            self._run_skill_with_retry("update_dashboard")
            self._last_dashboard_update = time.time()

        # 4. Scheduled: CEO briefing on Sunday 11 PM
        if self._should_run_briefing():
            self.logger.info("Scheduled CEO briefing generation")
            self._run_skill_with_retry("ceo_briefing")

    # ── Event Handlers ──────────────────────────────────────────────

    def _handle_new_items(self, new_files):
        """Process new files detected in /Needs_Action/."""
        # Track each new item
        for f in new_files:
            key = f.name
            item_type = self._detect_item_type(f)
            tracker = ItemTracker(f, item_type)
            self._items[key] = tracker
            self._log_event("item_detected", file=f.name, type=item_type)

        # Run process_inbox to classify and create plans
        file_list = ", ".join(f.name for f in new_files)
        success = self._run_skill_with_retry(
            "process_inbox",
            context=f"New items detected: {file_list}",
        )

        # Update item states
        for f in new_files:
            key = f.name
            if key in self._items:
                if success:
                    self._items[key].transition(State.PROCESSING)
                    # After process_inbox, items either go to approval or in_progress
                    # Check if an approval was created for this item
                    self._items[key].transition(State.AWAITING_APPROVAL)
                else:
                    self._items[key].error = "process_inbox failed"
                    self._items[key].retries += 1

    def _handle_approved(self, approved_files):
        """Process files that appeared in /Approved/."""
        for f in approved_files:
            key = f.name
            self._log_event("item_approved", file=f.name)

            # Update tracker if we have one, or create a new one
            if key in self._items:
                self._items[key].transition(State.APPROVED)
            else:
                tracker = ItemTracker(f, "approved_action")
                tracker.transition(State.APPROVED)
                self._items[key] = tracker

        # Run execute_approved skill
        file_list = ", ".join(f.name for f in approved_files)
        success = self._run_skill_with_retry(
            "execute_approved",
            context=f"Approved items to execute: {file_list}",
        )

        # Update states
        for f in approved_files:
            key = f.name
            if key in self._items:
                if success:
                    self._items[key].transition(State.EXECUTING)
                    self._items[key].transition(State.DONE)
                else:
                    self._items[key].error = "execute_approved failed"

        # Dashboard update after execution
        if success:
            self._run_skill_with_retry("update_dashboard")
            self._last_dashboard_update = time.time()

    def _detect_item_type(self, filepath):
        """Quick-read frontmatter to determine item type."""
        try:
            text = filepath.read_text(encoding="utf-8")
            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("type:"):
                    return line.split(":", 1)[1].strip()
                if line == "---" and not line.startswith("---"):
                    break  # end of frontmatter
            return "unknown"
        except Exception:
            return "unknown"


# ── CLI Entry Point ─────────────────────────────────────────────────

def main():
    load_dotenv()

    # Handle --health flag
    if "--health" in sys.argv:
        vault_path = os.getenv("VAULT_PATH")
        if not vault_path:
            print("VAULT_PATH not set in .env")
            sys.exit(1)

        health_file = Path(vault_path) / ".claude" / "health.json"
        if health_file.exists():
            data = json.loads(health_file.read_text(encoding="utf-8"))
            print(json.dumps(data, indent=2))
        else:
            print("No health data found. Is the orchestrator running?")
        sys.exit(0)

    # Create and run orchestrator
    orchestrator = Orchestrator.from_env()

    if "--dry-run" in sys.argv:
        orchestrator.dry_run = True
        orchestrator.logger.info("Forced DRY_RUN mode via --dry-run flag")

    orchestrator.run()


if __name__ == "__main__":
    main()
