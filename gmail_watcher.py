"""Gmail Watcher — monitors Gmail for unread important emails.

Extends BaseWatcher to poll the Gmail API every 2 minutes,
create action files in the vault for each new email, and
mark processed emails as read.

Requirements:
    pip install google-auth google-auth-oauthlib google-api-python-client

Setup:
    1. Place credentials.json in the secrets/ folder
    2. Set GMAIL_CREDENTIALS_PATH in .env
    3. Run this file once to complete OAuth flow (opens browser)
    4. Token is saved to secrets/gmail_token.json and auto-refreshes
"""

import base64
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

from dotenv import load_dotenv
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from base_watcher import BaseWatcher

# If modifying scopes, delete gmail_token.json to re-authorize
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


class GmailWatcher(BaseWatcher):
    """Monitors Gmail for unread important emails and creates vault action files."""

    def __init__(
        self,
        vault_path,
        credentials_path,
        token_path=None,
        check_interval=120,
        max_results=10,
    ):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path) if token_path else self.credentials_path.parent / "gmail_token.json"
        self.max_results = max_results
        self._service = None

        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Gmail credentials not found: {self.credentials_path}\n"
                "Download credentials.json from Google Cloud Console and place it in the secrets/ folder."
            )

        super().__init__(vault_path, check_interval)

        # Ensure emails subfolder exists
        emails_dir = self.needs_action / "emails"
        emails_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls, check_interval=120, **kwargs):
        """Create instance from .env configuration."""
        load_dotenv()
        vault_path = os.getenv("VAULT_PATH")
        credentials_path = os.getenv("GMAIL_CREDENTIALS_PATH")
        token_path = os.getenv("GMAIL_TOKEN_PATH")
        max_results = int(os.getenv("GMAIL_MAX_RESULTS", "10"))

        if not vault_path:
            raise ValueError("VAULT_PATH not set in .env file")
        if not credentials_path:
            raise ValueError("GMAIL_CREDENTIALS_PATH not set in .env file")

        return cls(
            vault_path=vault_path,
            credentials_path=credentials_path,
            token_path=token_path,
            check_interval=check_interval,
            max_results=max_results,
            **kwargs,
        )

    # ── Authentication ──────────────────────────────────────────────

    def _authenticate(self):
        """Authenticate with Gmail API, refreshing or creating tokens as needed."""
        creds = None

        # Load existing token
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as e:
                self.logger.warning(f"Failed to load token file: {e}")
                creds = None

        # Refresh or create new credentials
        if creds and creds.expired and creds.refresh_token:
            try:
                self.logger.info("Refreshing expired Gmail token...")
                creds.refresh(Request())
            except RefreshError as e:
                self.logger.warning(f"Token refresh failed: {e}. Re-authenticating...")
                creds = None

        if not creds or not creds.valid:
            self.logger.info("Starting OAuth flow — a browser window will open for authorization.")
            flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future runs
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json(), encoding="utf-8")
        self.logger.info(f"Token saved to {self.token_path}")

        return creds

    def _get_service(self):
        """Get or create the Gmail API service, handling token refresh."""
        if self._service is None:
            creds = self._authenticate()
            self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def _reset_service(self):
        """Force re-authentication on next call (e.g. after auth errors)."""
        self._service = None

    # ── Gmail API Operations ────────────────────────────────────────

    def check_for_updates(self):
        """Fetch unread important emails from Gmail."""
        try:
            service = self._get_service()

            # Query: unread emails in inbox, marked as important or primary category
            results = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    q="is:unread category:primary",
                    maxResults=self.max_results,
                )
                .execute()
            )

            messages = results.get("messages", [])
            if not messages:
                return []

            actions = []
            for msg_info in messages:
                try:
                    msg = (
                        service.users()
                        .messages()
                        .get(userId="me", id=msg_info["id"], format="full")
                        .execute()
                    )
                    action = self._parse_email(msg)
                    if action:
                        actions.append(action)
                except HttpError as e:
                    if e.resp.status == 429:
                        self.logger.warning("Gmail API rate limit hit. Backing off.")
                        break
                    self.logger.error(f"Failed to fetch message {msg_info['id']}: {e}")

            return actions

        except HttpError as e:
            if e.resp.status == 401:
                self.logger.warning("Gmail auth expired during request. Resetting service.")
                self._reset_service()
                raise
            if e.resp.status == 429:
                self.logger.warning("Gmail API rate limit hit. Will retry next cycle.")
                return []
            raise
        except RefreshError:
            self.logger.warning("Token refresh failed during request. Resetting service.")
            self._reset_service()
            raise
        except ConnectionError as e:
            self.logger.error(f"Network error connecting to Gmail: {e}")
            return []
        except TimeoutError as e:
            self.logger.error(f"Timeout connecting to Gmail: {e}")
            return []

    def _parse_email(self, msg):
        """Extract relevant fields from a Gmail API message object."""
        headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}

        sender = headers.get("from", "Unknown")
        subject = headers.get("subject", "(No Subject)")
        date_str = headers.get("date", "")
        message_id = msg["id"]
        labels = msg.get("labelIds", [])

        # Parse received date
        received_at = None
        if date_str:
            try:
                received_at = parsedate_to_datetime(date_str)
            except Exception:
                received_at = datetime.now(timezone.utc)
        else:
            received_at = datetime.now(timezone.utc)

        # Determine priority from Gmail labels
        priority = "medium"
        if "IMPORTANT" in labels:
            priority = "high"
        if "CATEGORY_PROMOTIONS" in labels or "CATEGORY_SOCIAL" in labels:
            priority = "low"

        # Extract body text
        body = self._extract_body(msg["payload"])
        snippet = msg.get("snippet", "")

        return {
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
            "received_at": received_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "priority": priority,
            "body": body,
            "snippet": unescape(snippet),
            "labels": labels,
        }

    def _extract_body(self, payload):
        """Recursively extract plain text body from email payload."""
        # Direct body on the payload
        if payload.get("body", {}).get("data"):
            return self._decode_body(payload["body"]["data"])

        # Multipart: look for text/plain first, then text/html
        parts = payload.get("parts", [])
        plain_text = None
        html_text = None

        for part in parts:
            mime = part.get("mimeType", "")
            if mime == "text/plain" and part.get("body", {}).get("data"):
                plain_text = self._decode_body(part["body"]["data"])
            elif mime == "text/html" and part.get("body", {}).get("data"):
                html_text = self._decode_body(part["body"]["data"])
            elif mime.startswith("multipart/"):
                # Recurse into nested multipart
                nested = self._extract_body(part)
                if nested:
                    plain_text = plain_text or nested

        if plain_text:
            return plain_text
        if html_text:
            return self._strip_html(html_text)
        return ""

    @staticmethod
    def _decode_body(data):
        """Decode base64url-encoded email body."""
        try:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        except Exception:
            return ""

    @staticmethod
    def _strip_html(html):
        """Basic HTML tag stripping for fallback when no plain text is available."""
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = unescape(text)
        # Collapse multiple blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # ── Action File Creation ────────────────────────────────────────

    def create_action_file(self, action):
        """Create a .md file in Needs_Action/emails/ and mark email as read."""
        message_id = action["message_id"]
        sender = action["sender"]
        subject = action["subject"]
        received_at = action["received_at"]
        priority = action["priority"]
        body = action["body"]
        snippet = action["snippet"]

        # Sanitize subject for filename
        safe_subject = re.sub(r'[<>:"/\\|?*]', "", subject)
        safe_subject = re.sub(r"\s+", "_", safe_subject)[:50]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_subject}.md"

        # Determine if sender is likely a known contact
        # (In production, this would check a contacts list)
        is_new_contact = True  # Default to cautious — treat as new until verified

        # Suggest actions based on email content and sender
        suggested_actions = self._suggest_actions(sender, subject, body, is_new_contact)

        frontmatter = {
            "type": "email",
            "from": f'"{sender}"',
            "subject": f'"{subject}"',
            "received_at": received_at,
            "priority": priority,
            "status": "pending",
            "gmail_id": message_id,
            "is_new_contact": is_new_contact,
        }

        # Truncate body to a reasonable length for the vault
        display_body = body[:2000] if body else snippet
        if len(body) > 2000:
            display_body += "\n\n_(Email truncated — full content available via Gmail)_"

        md_body = (
            f"# Email: {subject}\n\n"
            f"**From**: {sender}\n"
            f"**Received**: {received_at}\n"
            f"**Priority**: {priority}\n"
            f"**New Contact**: {'Yes' if is_new_contact else 'No'}\n\n"
            f"## Content\n\n"
            f"{display_body}\n\n"
            f"## Suggested Actions\n\n"
            f"{suggested_actions}\n\n"
            f"## Action Required\n"
            f"Review this email and decide on next steps.\n"
            f"{'**Note**: Sender is a new contact — replying requires approval.' if is_new_contact else ''}"
        )

        self.write_action_md("emails", filename, frontmatter, md_body)

        # Mark email as read in Gmail
        self._mark_as_read(message_id)

    def _suggest_actions(self, sender, subject, body, is_new_contact):
        """Generate suggested actions based on email content analysis."""
        suggestions = []
        lower_subject = subject.lower()
        lower_body = (body or "").lower()
        combined = f"{lower_subject} {lower_body}"

        # Check for payment/invoice keywords
        if any(kw in combined for kw in ["invoice", "payment", "billing", "amount due", "pay"]):
            suggestions.append("- **Flag for payment review** — contains financial keywords")
            suggestions.append("- Route to `/Pending_Approval/` (per Company Handbook: all payments need approval)")

        # Check for urgency
        if any(kw in combined for kw in ["urgent", "asap", "immediately", "deadline", "critical"]):
            suggestions.append("- **High priority** — sender indicates urgency")

        # Check for meeting/calendar
        if any(kw in combined for kw in ["meeting", "calendar", "schedule", "call", "zoom"]):
            suggestions.append("- **Calendar action** — may need to schedule a meeting")

        # New contact handling
        if is_new_contact:
            suggestions.append("- **New contact** — do NOT reply without approval (Company Handbook rule)")
        else:
            suggestions.append("- **Known contact** — draft reply is auto-approved, sending needs approval")

        if not suggestions:
            suggestions.append("- Review and classify manually")

        return "\n".join(suggestions)

    def _mark_as_read(self, message_id):
        """Remove UNREAD label from the email in Gmail."""
        try:
            service = self._get_service()
            service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
            self.logger.info(f"Marked email as read: {message_id}")
        except HttpError as e:
            if e.resp.status == 429:
                self.logger.warning(f"Rate limit hit when marking email as read: {message_id}")
            else:
                self.logger.error(f"Failed to mark email as read: {message_id}: {e}")
        except (ConnectionError, TimeoutError) as e:
            self.logger.error(f"Network error marking email as read: {message_id}: {e}")


if __name__ == "__main__":
    watcher = GmailWatcher.from_env()
    watcher.run()
