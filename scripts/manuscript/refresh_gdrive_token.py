"""Refresh Google OAuth token for review bridge without touching Drive/Docs files.

This script performs only the OAuth flow and writes a new token JSON to the
configured `token_file`. It does NOT call Google Drive or Docs APIs, so it
will not rename/move/archive any existing documents.

Usage (recommended):

    source venv/bin/activate
    python scripts/manuscript/refresh_gdrive_token.py

Optional overrides:

    python scripts/manuscript/refresh_gdrive_token.py --credentials secrets/google_credentials.json \
        --token secrets/google_token.json --open-browser false

When `open-browser` is false the script uses a console flow (prints an auth URL)
which is suitable for headless/WSL environments.
"""

from pathlib import Path
import json
import argparse
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except Exception as e:
    print("Missing dependency: google-auth-oauthlib is required.")
    print("Install with: pip install google-auth-oauthlib google-auth")
    raise

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "reports_ARCHIVE" / "manuscript" / "review" / "review_bridge_config.json"

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]


def load_config(cfg_path: Path) -> dict:
    if not cfg_path.exists():
        return {}
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    p = argparse.ArgumentParser(description="Refresh Google OAuth token without touching Drive/Docs content.")
    p.add_argument("--credentials", help="Path to OAuth client JSON (client_secrets)", default=None)
    p.add_argument("--token", help="Path to write token JSON", default=None)
    p.add_argument("--open-browser", help="If true, open a local browser for auth (default: use config)", choices=["true","false"], default=None)
    args = p.parse_args()

    cfg = load_config(DEFAULT_CONFIG)

    cred_path = Path(args.credentials) if args.credentials else Path(cfg.get("credentials_file", "secrets/google_credentials.json"))
    token_path = Path(args.token) if args.token else Path(cfg.get("token_file", "secrets/google_token.json"))
    oauth_open_browser_cfg = cfg.get("oauth_open_browser", False)
    if args.open_browser is not None:
        oauth_open_browser = True if args.open_browser == "true" else False
    else:
        oauth_open_browser = bool(oauth_open_browser_cfg)

    if not cred_path.exists():
        print(f"Credentials file not found: {cred_path}")
        print("Create OAuth client credentials and save to that path, or pass --credentials.")
        return 2

    token_path.parent.mkdir(parents=True, exist_ok=True)

    print("Starting OAuth flow. This script will NOT modify Drive/Docs files.")
    print(f"Credentials: {cred_path}")
    print(f"Token will be written to: {token_path}")
    print(f"Open browser for auth: {oauth_open_browser}")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
        if oauth_open_browser:
            # run_local_server opens browser and completes the flow; still safe because we do not call Drive.
            creds = flow.run_local_server(port=0)
        else:
            # For headless/WSL environments where open_browser=false
            flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
            auth_url, _ = flow.authorization_url(prompt='consent')
            print("\nPlease visit this URL to authorize the application:")
            print(f"\n{auth_url}\n")
            code = input("Enter the authorization code: ")
            flow.fetch_token(code=code)
            creds = flow.credentials

        # Persist credentials JSON
        token_path.write_text(creds.to_json(), encoding="utf-8")
        print("Saved new token to:", token_path)
        print("Done. You can now run manuscript_review_bridge commands (pull/push) as before.")
        return 0

    except Exception as e:
        print("OAuth flow failed:", str(e))
        return 3


if __name__ == "__main__":
    sys.exit(main())
