"""Ralph Loop — keeps Claude Code working until a multi-step task is complete.

Named after the "Ralph Wiggum" pattern: a persistent re-injection loop
that feeds context from previous iterations back into Claude Code until
the task is fully done.

Usage:
    python ralph_loop.py "Process all files in /Needs_Action and create plans"
    python ralph_loop.py "Handle inbox and update dashboard" --max-iterations 5
    python ralph_loop.py "Generate CEO briefing" --max-iterations 3 --dry-run

How it works:
    1. Creates a task state file in /In_Progress/
    2. Runs Claude Code with the task prompt + vault skill context
    3. After Claude finishes, checks for completion:
       - Task file moved to /Done/  (preferred — vault-native)
       - Claude output contains TASK_COMPLETE  (fallback)
    4. If NOT complete: re-injects prompt with iteration history
    5. If complete: moves state file to /Done/, exits 0
    6. Safety limit: 10 iterations max (configurable)
"""

import argparse
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from security_config import audit_log, security


class RalphLoop:
    """Persistent task execution loop with context re-injection."""

    DEFAULT_MAX_ITERATIONS = 10
    CLAUDE_TIMEOUT = 180  # 3 minutes per iteration
    COMPLETION_MARKER = "TASK_COMPLETE"

    def __init__(self, vault_path, task_description, max_iterations=None, dry_run=None):
        self.vault_path = Path(vault_path)
        self.task_description = task_description
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.dry_run = dry_run if dry_run is not None else security.dry_run

        # Vault paths
        self.in_progress = self.vault_path / "In_Progress"
        self.done = self.vault_path / "Done"
        self.logs_dir = self.vault_path / "Logs"

        # Task identity
        self.task_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_desc = re.sub(r'[<>:"/\\|?*]', "", task_description)
        safe_desc = re.sub(r"\s+", "_", safe_desc)[:40]
        self.task_filename = f"TASK_{safe_desc}_{self.task_id}.md"

        # State
        self.task_file = self.in_progress / self.task_filename
        self.iterations: list[dict] = []
        self.completed = False
        self._running = True

        # Setup
        self._ensure_dirs()
        self._setup_logging()
        self._setup_signals()

    @classmethod
    def from_env(cls, task_description, max_iterations=None, dry_run=None):
        """Create from .env configuration."""
        load_dotenv()
        vault_path = os.getenv("VAULT_PATH")
        if not vault_path:
            raise ValueError("VAULT_PATH not set in .env file")

        return cls(
            vault_path=vault_path,
            task_description=task_description,
            max_iterations=max_iterations,
            dry_run=dry_run,
        )

    # ── Setup ───────────────────────────────────────────────────────

    def _ensure_dirs(self):
        for d in [self.in_progress, self.done, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _setup_logging(self):
        self.logger = logging.getLogger(f"RalphLoop-{self.task_id}")
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

        log_file = self.logs_dir / "RalphLoop.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def _setup_signals(self):
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        self.logger.info("Shutdown signal received. Finishing current iteration...")
        self._running = False

    # ── Task State File ─────────────────────────────────────────────

    def _create_task_file(self):
        """Create the initial task state file in /In_Progress/."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        content = (
            f"---\n"
            f"type: ralph_loop_task\n"
            f"task_id: {self.task_id}\n"
            f"description: \"{self.task_description}\"\n"
            f"created: {now}\n"
            f"status: in_progress\n"
            f"max_iterations: {self.max_iterations}\n"
            f"current_iteration: 0\n"
            f"dry_run: {str(self.dry_run).lower()}\n"
            f"---\n\n"
            f"# Task: {self.task_description}\n\n"
            f"## Status\n"
            f"In progress — Ralph Loop running.\n\n"
            f"## Iteration Log\n"
            f"_No iterations yet_\n"
        )
        self.task_file.write_text(content, encoding="utf-8")
        self.logger.info(f"Task file created: {self.task_file.name}")

    def _update_task_file(self, iteration, output_summary, status):
        """Update the task file with iteration results."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build iteration log
        iter_entries = []
        for it in self.iterations:
            result = "success" if it["success"] else "failed"
            iter_entries.append(
                f"### Iteration {it['number']}\n"
                f"- **Time**: {it['timestamp']}\n"
                f"- **Duration**: {it['duration_seconds']}s\n"
                f"- **Result**: {result}\n"
                f"- **Output**: {it['summary'][:200]}\n"
            )

        iter_log = "\n".join(iter_entries) if iter_entries else "_No iterations yet_\n"

        content = (
            f"---\n"
            f"type: ralph_loop_task\n"
            f"task_id: {self.task_id}\n"
            f"description: \"{self.task_description}\"\n"
            f"created: {self.iterations[0]['timestamp'] if self.iterations else now}\n"
            f"last_updated: {now}\n"
            f"status: {status}\n"
            f"max_iterations: {self.max_iterations}\n"
            f"current_iteration: {iteration}\n"
            f"dry_run: {str(self.dry_run).lower()}\n"
            f"---\n\n"
            f"# Task: {self.task_description}\n\n"
            f"## Status\n"
            f"{'Completed' if status == 'completed' else 'In progress'} "
            f"— iteration {iteration}/{self.max_iterations}\n\n"
            f"## Iteration Log\n\n"
            f"{iter_log}"
        )

        # Write to correct location based on status
        target = self.task_file
        if status == "completed" and target.parent == self.in_progress:
            # Move to done
            new_path = self.done / self.task_filename
            target.unlink(missing_ok=True)
            target = new_path
            self.task_file = target

        target.write_text(content, encoding="utf-8")

    # ── Completion Detection ────────────────────────────────────────

    def _check_completion(self, claude_output):
        """Check if the task is complete via file location or output marker."""

        # Method 1: Task file moved to /Done/ by Claude
        done_path = self.done / self.task_filename
        if done_path.exists():
            self.logger.info("Completion detected: task file found in /Done/")
            self.task_file = done_path
            return True

        # Method 2: TASK_COMPLETE marker in Claude's output
        if self.COMPLETION_MARKER in claude_output:
            self.logger.info("Completion detected: TASK_COMPLETE marker in output")
            return True

        # Method 3: Check if all Needs_Action items have been processed
        # (useful for "process all" type tasks)
        needs_action = self.vault_path / "Needs_Action"
        pending_items = [
            f for f in needs_action.rglob("*.md")
            if f.name != ".gitkeep"
        ]
        if not pending_items and "Needs_Action" in self.task_description:
            self.logger.info("Completion detected: Needs_Action is empty")
            return True

        return False

    # ── Prompt Building ─────────────────────────────────────────────

    def _build_prompt(self, iteration):
        """Build the prompt for Claude Code, including iteration context."""

        # Base prompt with vault context
        prompt_parts = [
            f"You are the AI Employee working in an Obsidian vault at {self.vault_path}.",
            f"Your skills are defined in .claude/skills/ — read them for instructions.",
            f"Your rules are in Company_Handbook.md — always follow them.",
            "",
            f"## Task",
            f"{self.task_description}",
            "",
        ]

        # Add iteration context if this isn't the first run
        if iteration > 1 and self.iterations:
            prompt_parts.append("## Previous Iterations")
            prompt_parts.append(
                f"This is iteration {iteration} of {self.max_iterations}. "
                f"The task is NOT yet complete. Here is what was done so far:"
            )
            prompt_parts.append("")

            for it in self.iterations:
                prompt_parts.append(f"### Iteration {it['number']}")
                prompt_parts.append(f"Result: {'success' if it['success'] else 'failed'}")
                prompt_parts.append(f"Output summary: {it['summary'][:300]}")
                prompt_parts.append("")

            prompt_parts.append("## What to do now")
            prompt_parts.append(
                "Continue where the previous iteration left off. "
                "Do NOT repeat work that was already completed. "
                "Focus on the remaining steps."
            )
            prompt_parts.append("")

        # Completion instructions
        prompt_parts.extend([
            "## Completion",
            "When the task is fully complete:",
            f"1. Move the task file from /In_Progress/{self.task_filename} to /Done/",
            f"2. Include the string TASK_COMPLETE in your final output",
            "3. Update Dashboard.md with the results",
            "",
            "If the task is NOT complete after this iteration, summarize what was done",
            "and what still needs to be done. Do NOT output TASK_COMPLETE.",
        ])

        return "\n".join(prompt_parts)

    # ── Claude Execution ────────────────────────────────────────────

    def _run_claude(self, prompt):
        """Execute Claude Code with the given prompt. Returns (success, output)."""

        if self.dry_run:
            self.logger.info("DRY RUN — simulating Claude Code execution")
            audit_log("skill_run", "ralph_loop", self.task_description[:100], "dry_run",
                      metadata={"task_id": self.task_id})
            return True, f"DRY RUN: Would execute task. Iteration prompt length: {len(prompt)} chars"

        try:
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions", prompt],
                capture_output=True,
                text=True,
                timeout=self.CLAUDE_TIMEOUT,
                cwd=str(self.vault_path),
            )

            output = result.stdout or ""
            if result.returncode == 0:
                return True, output
            else:
                error = result.stderr or "Unknown error"
                self.logger.error(f"Claude exited with code {result.returncode}: {error[:200]}")
                return False, f"ERROR (exit {result.returncode}): {error[:200]}"

        except subprocess.TimeoutExpired:
            self.logger.error(f"Claude timed out after {self.CLAUDE_TIMEOUT}s")
            return False, f"TIMEOUT after {self.CLAUDE_TIMEOUT}s"
        except FileNotFoundError:
            self.logger.error("Claude Code CLI not found. Install it or add to PATH.")
            return False, "ERROR: claude CLI not found"

    # ── Main Loop ───────────────────────────────────────────────────

    def run(self):
        """Execute the Ralph Loop — keep running Claude until task is complete."""
        self.logger.info(
            f"Ralph Loop started: \"{self.task_description}\" "
            f"(max={self.max_iterations}, dry_run={self.dry_run})"
        )
        self._create_task_file()
        self._log_event("ralph_start")

        for iteration in range(1, self.max_iterations + 1):
            if not self._running:
                self.logger.info("Shutdown requested. Stopping loop.")
                self._update_task_file(iteration - 1, "Interrupted by user", "interrupted")
                self._log_event("ralph_interrupted", iteration=iteration)
                return False

            self.logger.info(f"── Iteration {iteration}/{self.max_iterations} ──")

            # Build prompt with context from previous iterations
            prompt = self._build_prompt(iteration)

            # Run Claude
            start_time = time.time()
            success, output = self._run_claude(prompt)
            duration = round(time.time() - start_time, 1)

            # Summarize output (first meaningful lines)
            summary = self._summarize_output(output)

            # Record iteration
            iter_record = {
                "number": iteration,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "success": success,
                "duration_seconds": duration,
                "summary": summary,
                "output_length": len(output),
            }
            self.iterations.append(iter_record)

            self.logger.info(f"Iteration {iteration} {'succeeded' if success else 'FAILED'} ({duration}s)")
            self.logger.info(f"Summary: {summary[:100]}")

            # Check completion
            if success and self._check_completion(output):
                self.completed = True
                self._update_task_file(iteration, summary, "completed")
                self._log_event("ralph_complete", iterations=iteration, duration_total=duration)
                self.logger.info(f"Task COMPLETE after {iteration} iteration(s)")
                return True

            # Not complete — update state and continue
            self._update_task_file(iteration, summary, "in_progress")
            self._log_event("ralph_iteration", iteration=iteration, success=success)

            if not success:
                self.logger.warning(f"Iteration {iteration} failed — will retry in next iteration")

            # Brief pause between iterations to avoid hammering
            if iteration < self.max_iterations:
                time.sleep(2)

        # Exhausted all iterations without completing
        self._update_task_file(self.max_iterations, "Max iterations reached", "max_iterations_exceeded")
        self._log_event("ralph_exhausted", iterations=self.max_iterations)
        self.logger.warning(
            f"Task NOT complete after {self.max_iterations} iterations. "
            f"Manual intervention may be needed."
        )
        self._create_alert()
        return False

    # ── Helpers ─────────────────────────────────────────────────────

    def _summarize_output(self, output):
        """Extract a concise summary from Claude's output."""
        if not output:
            return "(no output)"

        lines = [l.strip() for l in output.strip().split("\n") if l.strip()]

        # Skip tool-call noise, keep substantive lines
        meaningful = []
        for line in lines:
            if line.startswith(("{", "```", "---")):
                continue
            meaningful.append(line)
            if len(meaningful) >= 5:
                break

        return " | ".join(meaningful) if meaningful else lines[0][:200]

    def _log_event(self, event_type, **details):
        """Append to today's daily log."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"{today}.md"
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")

        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        entry = f"- `{now}` | **{event_type}** | task={self.task_id}, {detail_str}\n"

        if not log_file.exists():
            header = (
                f"---\ndate: {today}\ntype: daily_log\n---\n\n"
                f"# Daily Log — {today}\n\n"
            )
            log_file.write_text(header + entry, encoding="utf-8")
        else:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry)

    def _create_alert(self):
        """Create an alert when max iterations are exhausted."""
        now = datetime.now(timezone.utc)
        alert_file = self.vault_path / "Needs_Action" / (
            f"ALERT_ralph_loop_exhausted_{self.task_id}.md"
        )

        content = (
            f"---\n"
            f"type: alert\n"
            f"severity: medium\n"
            f"created: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            f"status: pending\n"
            f"---\n\n"
            f"# Alert: Ralph Loop Exhausted\n\n"
            f"**Task**: {self.task_description}\n"
            f"**Task ID**: {self.task_id}\n"
            f"**Iterations**: {self.max_iterations}/{self.max_iterations} (all used)\n"
            f"**State file**: `In_Progress/{self.task_filename}`\n\n"
            f"## Iteration Summary\n\n"
        )
        for it in self.iterations:
            content += (
                f"- **Iteration {it['number']}**: "
                f"{'OK' if it['success'] else 'FAILED'} "
                f"({it['duration_seconds']}s) — {it['summary'][:100]}\n"
            )

        content += (
            f"\n## Action Required\n"
            f"Review the task state file and iteration log. Either:\n"
            f"1. Re-run with more iterations: "
            f"`python ralph_loop.py \"{self.task_description}\" --max-iterations 15`\n"
            f"2. Complete the remaining steps manually\n"
            f"3. Move the task file to /Done/ if the task is actually complete\n"
        )

        alert_file.write_text(content, encoding="utf-8")
        self.logger.warning(f"Alert created: {alert_file.name}")


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ralph Loop — persistent Claude Code task runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python ralph_loop.py "Process all files in /Needs_Action"\n'
            '  python ralph_loop.py "Handle inbox and update dashboard" --max-iterations 5\n'
            '  python ralph_loop.py "Generate CEO briefing" --dry-run\n'
        ),
    )
    parser.add_argument("task", help="Task description for Claude Code to execute")
    parser.add_argument(
        "--max-iterations", type=int, default=None,
        help=f"Maximum iterations before giving up (default: {RalphLoop.DEFAULT_MAX_ITERATIONS})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Log actions without executing Claude Code",
    )

    args = parser.parse_args()

    loop = RalphLoop.from_env(
        task_description=args.task,
        max_iterations=args.max_iterations,
        dry_run=args.dry_run or None,
    )

    success = loop.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
