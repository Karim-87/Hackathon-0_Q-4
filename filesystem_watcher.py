import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from base_watcher import BaseWatcher


class _DropHandler(FileSystemEventHandler):
    """Watchdog handler that collects newly created files."""

    def __init__(self):
        self.pending_files = []

    def on_created(self, event):
        if not event.is_directory:
            self.pending_files.append(event.src_path)


class FileSystemWatcher(BaseWatcher):
    """Monitors a drop folder and ingests files into the vault."""

    def __init__(self, vault_path, drop_folder, check_interval=5):
        self.drop_folder = Path(drop_folder)
        self.drop_folder.mkdir(parents=True, exist_ok=True)

        super().__init__(vault_path, check_interval)

        self._handler = _DropHandler()
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.drop_folder), recursive=False)

    @classmethod
    def from_env(cls, check_interval=5, **kwargs):
        """Create instance from .env (VAULT_PATH + DROP_FOLDER)."""
        load_dotenv()
        vault_path = os.getenv("VAULT_PATH")
        drop_folder = os.getenv("DROP_FOLDER")
        if not vault_path:
            raise ValueError("VAULT_PATH not set in .env file")
        if not drop_folder:
            raise ValueError("DROP_FOLDER not set in .env file")
        return cls(
            vault_path=vault_path,
            drop_folder=drop_folder,
            check_interval=check_interval,
            **kwargs,
        )

    def _wait_for_copy_complete(self, filepath: Path, timeout=30):
        """Wait until a file is fully written (size stops changing)."""
        previous_size = -1
        elapsed = 0
        while elapsed < timeout:
            try:
                current_size = filepath.stat().st_size
                if current_size == previous_size and current_size > 0:
                    return True
                previous_size = current_size
            except OSError:
                pass
            time.sleep(0.5)
            elapsed += 0.5
        return False

    def check_for_updates(self):
        """Return list of file paths that were dropped since last check."""
        files = list(self._handler.pending_files)
        self._handler.pending_files.clear()

        actions = []
        for filepath_str in files:
            filepath = Path(filepath_str)
            if filepath.exists():
                actions.append({"path": filepath})
        return actions

    def create_action_file(self, action):
        """Copy dropped file to vault and create metadata .md file."""
        source: Path = action["path"]

        # Wait for file to finish copying
        if not self._wait_for_copy_complete(source):
            self.logger.warning(f"Timeout waiting for file: {source.name}")
            return

        # Copy file to Needs_Action/files/
        dest_dir = self.needs_action / "files"
        dest_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest_filename = f"{timestamp}_{source.name}"
        dest_path = dest_dir / dest_filename

        shutil.copy2(source, dest_path)
        self.logger.info(f"File copied: {source.name} -> {dest_path.relative_to(self.vault_path)}")

        # Create metadata .md file
        file_size = dest_path.stat().st_size
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        frontmatter = {
            "type": "file_drop",
            "original_name": source.name,
            "size": self._human_readable_size(file_size),
            "size_bytes": file_size,
            "dropped_at": now_iso,
            "status": "pending",
        }

        body = (
            f"# 📁 File Drop: {source.name}\n\n"
            f"A new file was dropped in the AI Drop folder.\n\n"
            f"- **Original name**: `{source.name}`\n"
            f"- **Size**: {self._human_readable_size(file_size)}\n"
            f"- **Copied to**: `{dest_path.relative_to(self.vault_path)}`\n"
            f"- **Time**: {now_iso}\n\n"
            f"## Action Required\n"
            f"Review this file and move to the appropriate project folder."
        )

        md_filename = f"{timestamp}_{source.stem}.md"
        self.write_action_md("files", md_filename, frontmatter, body)

        # Remove original from drop folder after successful processing
        source.unlink()
        self.logger.info(f"Original removed from drop folder: {source.name}")

    @staticmethod
    def _human_readable_size(size_bytes):
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def run(self):
        """Start watchdog observer then enter the base check loop."""
        self._observer.start()
        self.logger.info(f"Watching drop folder: {self.drop_folder}")
        try:
            super().run()
        finally:
            self._observer.stop()
            self._observer.join()
            self.logger.info("Watchdog observer stopped.")


if __name__ == "__main__":
    watcher = FileSystemWatcher.from_env()
    watcher.run()
