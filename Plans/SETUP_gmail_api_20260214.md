---
created: 2026-02-14T00:00:00Z
type: setup_guide
status: pending
requires_approval: false
---

# Setup Guide: Gmail API Integration

## Prerequisites
- A Google account (the one whose inbox the AI Employee will monitor)
- A web browser for OAuth authorization
- Python 3.14 with the project's virtual environment active

---

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top left (next to "Google Cloud")
3. Click **"New Project"**
4. Enter:
   - **Project name**: `AI-Employee`
   - **Organization**: leave as default (or "No organization")
5. Click **"Create"**
6. Wait for the project to be created, then select it from the project dropdown

## Step 2: Enable the Gmail API

1. In the Google Cloud Console, go to **APIs & Services > Library**
   (or search for "Gmail API" in the top search bar)
2. Search for **"Gmail API"**
3. Click on **Gmail API** in the results
4. Click **"Enable"**
5. Wait for it to be enabled (you'll be redirected to the API overview page)

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services > OAuth consent screen**
2. Select **"External"** user type (unless you have a Google Workspace org)
3. Click **"Create"**
4. Fill in the required fields:
   - **App name**: `AI Employee`
   - **User support email**: your email
   - **Developer contact email**: your email
5. Click **"Save and Continue"**
6. On the **Scopes** page, click **"Add or Remove Scopes"**
7. Add these scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.modify`
8. Click **"Update"**, then **"Save and Continue"**
9. On the **Test users** page, click **"Add Users"**
10. Add your Gmail address
11. Click **"Save and Continue"**, then **"Back to Dashboard"**

## Step 4: Create OAuth 2.0 Credentials

1. Go to **APIs & Services > Credentials**
2. Click **"+ Create Credentials"** at the top
3. Select **"OAuth client ID"**
4. Set:
   - **Application type**: `Desktop app`
   - **Name**: `AI Employee Desktop`
5. Click **"Create"**
6. A dialog will show your **Client ID** and **Client Secret**
7. Click **"Download JSON"** — this downloads your `credentials.json`

## Step 5: Save Credentials Securely

1. Move the downloaded file to the secrets folder:
   ```
   D:\Hackathon-0 Q4\ai-employee-project\ai-employee-watchers\secrets\credentials.json
   ```
2. Verify it's in .gitignore (it is — the `secrets/` folder is excluded)
3. **NEVER commit this file to git**
4. **NEVER copy it into the Obsidian vault**

Your `.env` file is already configured to point here:
```
GMAIL_CREDENTIALS_PATH=D:\Hackathon-0 Q4\ai-employee-project\ai-employee-watchers\secrets\credentials.json
GMAIL_TOKEN_PATH=D:\Hackathon-0 Q4\ai-employee-project\ai-employee-watchers\secrets\gmail_token.json
```

## Step 6: Install Dependencies

Open a terminal in the project directory and run:
```bash
cd "D:\Hackathon-0 Q4\ai-employee-project\ai-employee-watchers"
.venv\Scripts\activate
pip install google-auth google-auth-oauthlib google-api-python-client
```

Or with uv (if using uv for package management):
```bash
uv pip install google-auth google-auth-oauthlib google-api-python-client
```

## Step 7: First Run — OAuth Authorization

1. Run the Gmail watcher:
   ```bash
   python gmail_watcher.py
   ```
2. A browser window will open asking you to sign in to Google
3. Select your Gmail account
4. You may see a "This app isn't verified" warning — click **"Advanced"** then **"Go to AI Employee (unsafe)"**
   (This is normal for development/testing apps)
5. Grant the requested permissions:
   - Read your email
   - Modify your email (needed to mark as read)
6. The browser will show "The authentication flow has completed"
7. The token is saved to `secrets/gmail_token.json` — it auto-refreshes, so you only do this once

## Step 8: Verify It Works

After authorization, the watcher will:
- Start polling Gmail every 2 minutes
- Log activity to `Logs/GmailWatcher.log` in the vault
- Create `.md` files in `Needs_Action/emails/` for each unread primary email
- Mark processed emails as read in Gmail

Check the log output:
```
2026-02-14 12:00:00 | GmailWatcher | INFO | Starting GmailWatcher (interval=120s, vault=D:\Hackathon-0 Q4\AI_Employee_Vault)
2026-02-14 12:00:01 | GmailWatcher | INFO | Token saved to D:\...\secrets\gmail_token.json
2026-02-14 12:00:02 | GmailWatcher | INFO | Found 3 new item(s)
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "credentials.json not found" | Verify the file path in `.env` matches where you saved it |
| "Token refresh failed" | Delete `secrets/gmail_token.json` and re-run to re-authorize |
| "This app is blocked" | Go to OAuth consent screen, make sure your email is in Test Users |
| "403 Forbidden" | Gmail API may not be enabled — check Step 2 |
| "429 Rate limit" | The watcher will auto-retry next cycle. Default: 10 emails per check, every 2 minutes |
| Browser doesn't open | Run from a terminal with GUI access, not a headless server |

## Security Notes
- `credentials.json` — contains your OAuth client ID/secret. Keep it in `secrets/`, never commit.
- `gmail_token.json` — contains your access/refresh token. Auto-generated, never commit.
- Both files are excluded by `.gitignore` entries for `secrets/` and `*_token.json`.
- The watcher uses **read + modify** scopes only — it cannot send emails or delete messages.
- Per Company Handbook: "Never store passwords or API keys in the vault."
