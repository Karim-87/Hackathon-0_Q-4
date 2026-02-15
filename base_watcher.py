import logging
import signal
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from security_config import audit_log, security


class BaseWatcher(ABC):
    """Base class for all AI Employee vault watchers."""

    MAX_CONSECUTIVE_ERRORS = 10

    def __init__(self, vault_path, check_interval=60):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / "Needs_Action"
        self.logs_dir = self.vault_path / "Logs"
        self.check_interval = check_interval
        self._running = False
        self._error_count = 0

        self._validate_vault()
        self._setup_logging()
        self._setup_signal_handlers()

    @classmethod
    def from_env(cls, check_interval=60, **kwargs):
        """Create a watcher instance using VAULT_PATH from .env file."""
        load_dotenv()
        import os

        vault_path = os.getenv("VAULT_PATH")
        if not vault_path:
            raise ValueError("VAULT_PATH not set in .env file")
        return cls(vault_path=vault_path, check_interval=check_interval, **kwargs)

    def _validate_vault(self):
        """Ensure required vault directories exist."""
        if not self.vault_path.exists():
            raise FileNotFoundError(f"Vault path does not exist: {self.vault_path}")
        self.needs_action.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _setup_logging(self):
        """Configure logging to both console and vault log file."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        if self.logger.handlers:
            return

        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Console handler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        self.logger.addHandler(console)

        # File handler — one log file per watcher class
        log_file = self.logs_dir / f"{self.__class__.__name__}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def _setup_signal_handlers(self):
        """Handle Ctrl+C for graceful shutdown."""
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        self.logger.info("Shutdown signal received. Stopping gracefully...")
        self._running = False

    @abstractmethod
    def check_for_updates(self):
        """Check external source for new items. Return list of action dicts."""
        pass

    @abstractmethod
    def create_action_file(self, action):
        """Create a .md file in Needs_Action from an action dict."""
        pass

    def write_action_md(self, subfolder, filename, frontmatter: dict, body: str):
        """Write an Obsidian-compatible .md file with YAML frontmatter.

        Args:
            subfolder: Subfolder inside Needs_Action (e.g. 'emails', 'messages')
            filename: Name of the .md file to create
            frontmatter: Dict of YAML metadata fields
            body: Markdown body content
        """
        target_dir = self.needs_action / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        filepath = target_dir / filename

        # Build YAML frontmatter
        lines = ["---"]
        for key, value in frontmatter.items():
            lines.append(f"{key}: {value}")
        lines.append("---")
        lines.append("")
        lines.append(body)

        filepath.write_text("\n".join(lines), encoding="utf-8")
        self.logger.info(f"Action file created: {filepath.relative_to(self.vault_path)}")
        audit_log("file_op", "watcher", str(filepath.relative_to(self.vault_path)),
                  "success", metadata={"operation": "create_action_file"})
        return filepath

    def run(self):
        """Main loop — checks for updates at each interval."""
        self.logger.info(
            f"Starting {self.__class__.__name__} "
            f"(interval={self.check_interval}s, vault={self.vault_path})"
        )
        self._running = True
        self._error_count = 0

        while self._running:
            try:
                updates = self.check_for_updates()
                if updates:
                    self.logger.info(f"Found {len(updates)} new item(s)")
                    for action in updates:
                        self.create_action_file(action)
                else:
                    self.logger.debug("No new updates")

                self._error_count = 0  # reset on success

            except Exception as e:
                self._error_count += 1
                self.logger.error(f"Error ({self._error_count}/{self.MAX_CONSECUTIVE_ERRORS}): {e}")

                if self._error_count >= self.MAX_CONSECUTIVE_ERRORS:
                    self.logger.critical(
                        f"Reached {self.MAX_CONSECUTIVE_ERRORS} consecutive errors. Shutting down."
                    )
                    self._running = False
                    break

            if self._running:
                time.sleep(self.check_interval)

        self.logger.info(f"{self.__class__.__name__} stopped.")
