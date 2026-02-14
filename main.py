"""AI Employee — Main entry point.

Starts the orchestrator, which coordinates all watchers and skills.
Individual watchers (filesystem, gmail) run as separate processes.

Usage:
    python main.py                  # Start orchestrator
    python main.py --dry-run        # Start in dry-run mode
    python main.py --health         # Show health status

    python filesystem_watcher.py    # Start filesystem watcher separately
    python gmail_watcher.py         # Start gmail watcher separately
"""

from orchestrator import main

if __name__ == "__main__":
    main()
