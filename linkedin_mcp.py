"""LinkedIn MCP Server — Model Context Protocol server for LinkedIn API.

Provides tools for Claude Code to interact with LinkedIn:
  - get_profile: Fetch the authenticated user's LinkedIn profile
  - create_post: Publish a text post to LinkedIn

Setup:
    1. Register an app at https://www.linkedin.com/developers/
    2. Request the products: "Share on LinkedIn" and "Sign In with LinkedIn using OpenID Connect"
    3. Set OAuth 2.0 redirect URL to http://localhost:8914/callback
    4. Add to .env:
         LINKEDIN_CLIENT_ID=your_client_id
         LINKEDIN_CLIENT_SECRET=your_client_secret
         LINKEDIN_ACCESS_TOKEN=your_access_token  (after OAuth flow)
    5. Run the OAuth flow once:
         python linkedin_mcp.py --auth
    6. Start as MCP server:
         python linkedin_mcp.py

Requirements:
    pip install requests python-dotenv

MCP integration (add to .claude/settings.json or claude_desktop_config.json):
    {
      "mcpServers": {
        "linkedin": {
          "command": "python",
          "args": ["linkedin_mcp.py"],
          "cwd": "<vault_path>"
        }
      }
    }
"""

import json
import logging
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import requests
from dotenv import load_dotenv

load_dotenv()

from security_config import audit_log, security

# ── Configuration ──────────────────────────────────────────────────

LINKEDIN_CLIENT_ID = security.get_credential("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = security.get_credential("LINKEDIN_CLIENT_SECRET")
LINKEDIN_ACCESS_TOKEN = security.get_credential("LINKEDIN_ACCESS_TOKEN")
LINKEDIN_TOKEN_PATH = Path(os.getenv(
    "LINKEDIN_TOKEN_PATH",
    Path(__file__).parent / "secrets" / "linkedin_token.json",
))

OAUTH_REDIRECT_URI = "http://localhost:8914/callback"
OAUTH_SCOPES = ["openid", "profile", "w_member_social"]

API_BASE = "https://api.linkedin.com/v2"
API_VERSION = "202402"

DRY_RUN = security.dry_run
VAULT_PATH = security.vault_path
LOGS_DIR = security.logs_dir

# ── Logging ────────────────────────────────────────────────────────

logger = logging.getLogger("LinkedInMCP")
logger.setLevel(logging.DEBUG)

_formatter = logging.Formatter(
    "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_console = logging.StreamHandler(sys.stderr)
_console.setLevel(logging.INFO)
_console.setFormatter(_formatter)
logger.addHandler(_console)


# ── Token Management ──────────────────────────────────────────────

def _load_token():
    """Load access token from file or env, preferring the file."""
    if LINKEDIN_TOKEN_PATH.exists():
        try:
            data = json.loads(LINKEDIN_TOKEN_PATH.read_text(encoding="utf-8"))
            token = data.get("access_token", "")
            expires_at = data.get("expires_at", 0)
            if token and time.time() < expires_at:
                return token
            if token and expires_at == 0:
                return token
            logger.warning("Stored LinkedIn token is expired.")
        except Exception as e:
            logger.warning(f"Failed to read token file: {e}")

    return LINKEDIN_ACCESS_TOKEN


def _save_token(token_data):
    """Save token data to the secrets file."""
    LINKEDIN_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LINKEDIN_TOKEN_PATH.write_text(
        json.dumps(token_data, indent=2), encoding="utf-8"
    )
    logger.info(f"Token saved to {LINKEDIN_TOKEN_PATH}")


# ── LinkedIn API Client ──────────────────────────────────────────

class LinkedInClient:
    """Thin wrapper around the LinkedIn REST API v2."""

    def __init__(self, access_token=None):
        self.access_token = access_token or _load_token()
        if not self.access_token:
            raise ValueError(
                "No LinkedIn access token found. Run `python linkedin_mcp.py --auth` "
                "to complete the OAuth flow, or set LINKEDIN_ACCESS_TOKEN in .env"
            )

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": API_VERSION,
        }

    def get_profile(self):
        """Fetch the authenticated user's profile (name, headline, URN)."""
        resp = requests.get(
            f"{API_BASE}/userinfo",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "sub": data.get("sub", ""),
            "name": data.get("name", ""),
            "given_name": data.get("given_name", ""),
            "family_name": data.get("family_name", ""),
            "email": data.get("email", ""),
            "picture": data.get("picture", ""),
        }

    def get_person_urn(self):
        """Get the person URN needed for posting."""
        profile = self.get_profile()
        sub = profile.get("sub", "")
        if not sub:
            raise ValueError("Could not determine LinkedIn person URN from profile.")
        return sub

    def create_post(self, text):
        """Publish a text post to LinkedIn. Returns the post response."""
        person_urn = self.get_person_urn()
        author = f"urn:li:person:{person_urn}"

        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        resp = requests.post(
            f"{API_BASE}/ugcPosts",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


# ── Vault Logging ─────────────────────────────────────────────────

def _log_to_vault(event_type, **details):
    """Append a structured event to today's daily log in the vault."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.md"
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")

    detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
    entry = f"- `{now}` | **{event_type}** | {detail_str}\n"

    if not log_file.exists():
        header = (
            f"---\ndate: {today}\ntype: daily_log\n---\n\n"
            f"# Daily Log — {today}\n\n"
        )
        log_file.write_text(header + entry, encoding="utf-8")
    else:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)


# ── MCP Tool Handlers ─────────────────────────────────────────────

def handle_get_profile():
    """MCP tool: get the authenticated user's LinkedIn profile."""
    try:
        client = LinkedInClient()
        profile = client.get_profile()
        _log_to_vault("linkedin_get_profile", status="success", name=profile.get("name", ""))
        audit_log("social_post", "linkedin_mcp", "get_profile", "success",
                  metadata={"name": profile.get("name", "")})
        return {
            "content": [{"type": "text", "text": json.dumps(profile, indent=2)}],
            "isError": False,
        }
    except requests.HTTPError as e:
        error_msg = f"LinkedIn API error: {e.response.status_code} — {e.response.text[:200]}"
        logger.error(error_msg)
        _log_to_vault("linkedin_get_profile", status="error", error=error_msg)
        audit_log("social_post", "linkedin_mcp", "get_profile", "failed",
                  metadata={"error": error_msg})
        return {
            "content": [{"type": "text", "text": error_msg}],
            "isError": True,
        }
    except Exception as e:
        error_msg = f"Error: {e}"
        logger.error(error_msg)
        audit_log("social_post", "linkedin_mcp", "get_profile", "failed",
                  metadata={"error": error_msg})
        return {
            "content": [{"type": "text", "text": error_msg}],
            "isError": True,
        }


def handle_create_post(text):
    """MCP tool: create a LinkedIn post. Respects DRY_RUN mode."""
    if not text or not text.strip():
        return {
            "content": [{"type": "text", "text": "Error: Post text cannot be empty."}],
            "isError": True,
        }

    if len(text) > 3000:
        return {
            "content": [{"type": "text", "text": f"Error: Post too long ({len(text)} chars). LinkedIn max is 3000."}],
            "isError": True,
        }

    if not security.check_rate_limit("social_post"):
        audit_log("social_post", "linkedin_mcp", "create_post", "rate_limited",
                  metadata={"chars": len(text)})
        return {
            "content": [{"type": "text", "text": "Error: Social post rate limit exceeded (max 1/day)."}],
            "isError": True,
        }

    if DRY_RUN:
        logger.info(f"DRY RUN — would post to LinkedIn ({len(text)} chars)")
        _log_to_vault(
            "linkedin_create_post",
            status="dry_run",
            chars=len(text),
            preview=text[:80].replace("\n", " "),
        )
        audit_log("social_post", "linkedin_mcp", "create_post", "dry_run",
                  metadata={"chars": len(text), "preview": text[:80]})
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "status": "dry_run",
                            "message": "DRY RUN — post was NOT published to LinkedIn.",
                            "post_preview": text[:200],
                            "character_count": len(text),
                        },
                        indent=2,
                    ),
                }
            ],
            "isError": False,
        }

    try:
        client = LinkedInClient()
        result = client.create_post(text)
        post_id = result.get("id", "unknown")
        logger.info(f"Post published to LinkedIn: {post_id}")
        _log_to_vault(
            "linkedin_create_post",
            status="published",
            post_id=post_id,
            chars=len(text),
        )
        audit_log("social_post", "linkedin_mcp", "create_post", "success",
                  dry_run=False, metadata={"post_id": post_id, "chars": len(text)})
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "status": "published",
                            "post_id": post_id,
                            "character_count": len(text),
                            "message": "Post successfully published to LinkedIn.",
                        },
                        indent=2,
                    ),
                }
            ],
            "isError": False,
        }
    except requests.HTTPError as e:
        error_msg = f"LinkedIn API error: {e.response.status_code} — {e.response.text[:200]}"
        logger.error(error_msg)
        _log_to_vault("linkedin_create_post", status="error", error=error_msg)
        audit_log("social_post", "linkedin_mcp", "create_post", "failed",
                  metadata={"error": error_msg})
        return {
            "content": [{"type": "text", "text": error_msg}],
            "isError": True,
        }
    except Exception as e:
        error_msg = f"Error publishing post: {e}"
        logger.error(error_msg)
        _log_to_vault("linkedin_create_post", status="error", error=str(e))
        audit_log("social_post", "linkedin_mcp", "create_post", "failed",
                  metadata={"error": str(e)})
        return {
            "content": [{"type": "text", "text": error_msg}],
            "isError": True,
        }


# ── OAuth Flow ────────────────────────────────────────────────────

class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth redirect callback to capture the auth code."""
    auth_code = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            _OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<h2>LinkedIn authorization successful!</h2>"
                b"<p>You can close this window and return to the terminal.</p>"
            )
        else:
            error = params.get("error", ["unknown"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<h2>Authorization failed: {error}</h2>".encode())

    def log_message(self, format, *args):
        pass  # Suppress default HTTP logging


def run_oauth_flow():
    """Interactive OAuth 2.0 flow for LinkedIn authorization."""
    if not LINKEDIN_CLIENT_ID or not LINKEDIN_CLIENT_SECRET:
        print("Error: LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET must be set in .env")
        print()
        print("Setup steps:")
        print("  1. Go to https://www.linkedin.com/developers/apps")
        print("  2. Create a new app (or use an existing one)")
        print("  3. Under 'Auth', add redirect URL: http://localhost:8914/callback")
        print("  4. Request products: 'Share on LinkedIn' and 'Sign In with LinkedIn using OpenID Connect'")
        print("  5. Copy Client ID and Client Secret to your .env file")
        sys.exit(1)

    scopes = " ".join(OAUTH_SCOPES)
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code"
        f"&client_id={LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(OAUTH_REDIRECT_URI)}"
        f"&scope={urllib.parse.quote(scopes)}"
    )

    print("Opening browser for LinkedIn authorization...")
    print(f"If the browser doesn't open, visit this URL manually:\n\n{auth_url}\n")

    import webbrowser
    webbrowser.open(auth_url)

    # Start local server to catch the callback
    server = HTTPServer(("localhost", 8914), _OAuthCallbackHandler)
    server.timeout = 120
    print("Waiting for authorization (timeout: 2 minutes)...")
    server.handle_request()

    auth_code = _OAuthCallbackHandler.auth_code
    if not auth_code:
        print("Error: No authorization code received.")
        sys.exit(1)

    print("Authorization code received. Exchanging for access token...")

    # Exchange code for token
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "client_id": LINKEDIN_CLIENT_ID,
            "client_secret": LINKEDIN_CLIENT_SECRET,
        },
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()

    access_token = token_data.get("access_token", "")
    expires_in = token_data.get("expires_in", 0)

    if not access_token:
        print(f"Error: No access token in response: {token_data}")
        sys.exit(1)

    # Save token
    save_data = {
        "access_token": access_token,
        "expires_in": expires_in,
        "expires_at": time.time() + expires_in if expires_in else 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_token(save_data)

    # Verify by fetching profile
    client = LinkedInClient(access_token)
    profile = client.get_profile()
    print(f"\nAuthenticated as: {profile.get('name', 'Unknown')}")
    print(f"Token saved to: {LINKEDIN_TOKEN_PATH}")
    print(f"Token expires in: {expires_in // 86400} days" if expires_in else "Token expiry: unknown")
    print("\nLinkedIn MCP server is ready to use.")


# ── MCP Protocol (stdio JSON-RPC) ────────────────────────────────

TOOLS = [
    {
        "name": "get_profile",
        "description": (
            "Fetch the authenticated user's LinkedIn profile. "
            "Returns name, email, and profile picture URL."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "create_post",
        "description": (
            "Publish a text post to LinkedIn. In DRY_RUN mode, the post is "
            "logged but NOT published. Always requires prior human approval "
            "via the vault approval workflow."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The post content text (max 3000 characters).",
                },
            },
            "required": ["text"],
        },
    },
]


def _handle_mcp_request(request):
    """Route an MCP JSON-RPC request to the appropriate handler."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "linkedin-mcp", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            },
        }

    if method == "notifications/initialized":
        return None  # No response for notifications

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "get_profile":
            result = handle_get_profile()
        elif tool_name == "create_post":
            result = handle_create_post(arguments.get("text", ""))
        else:
            result = {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True,
            }

        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def run_mcp_server():
    """Run the MCP server over stdio (JSON-RPC)."""
    logger.info("LinkedIn MCP server starting (stdio mode)...")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            error_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
            sys.stdout.write(json.dumps(error_resp) + "\n")
            sys.stdout.flush()
            continue

        response = _handle_mcp_request(request)

        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


# ── CLI Entry Point ───────────────────────────────────────────────

def main():
    if "--auth" in sys.argv:
        run_oauth_flow()
    elif "--test" in sys.argv:
        # Quick test: fetch profile
        print("Testing LinkedIn connection...")
        try:
            client = LinkedInClient()
            profile = client.get_profile()
            print(f"Connected as: {profile.get('name', 'Unknown')}")
            print(json.dumps(profile, indent=2))
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif "--dry-post" in sys.argv:
        # Test post generation without publishing
        text = " ".join(sys.argv[sys.argv.index("--dry-post") + 1:])
        if not text:
            text = "Test post from AI Employee LinkedIn MCP server."
        result = handle_create_post(text)
        print(json.dumps(result, indent=2))
    else:
        run_mcp_server()


if __name__ == "__main__":
    main()
