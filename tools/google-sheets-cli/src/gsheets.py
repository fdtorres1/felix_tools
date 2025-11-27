#!/usr/bin/env python3
import argparse
import json
import logging
import os
import sys
import time
import random
from typing import Any, Dict, List, Optional

import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def load_agents_env(path: Optional[str] = None) -> None:
    """Load key=value lines from ~/AGENTS.env into os.environ if not already set."""
    env_path = path or os.environ.get("AGENTS_ENV_PATH", os.path.expanduser("~/AGENTS.env"))
    try:
        if not os.path.exists(env_path):
            return
        kv: Dict[str, str] = {}
        with open(env_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].lstrip()
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip().strip('"').strip("'")
                v = v.strip().strip('"').strip("'")
                if not k:
                    continue
                kv[k] = v  # last one wins within file
        for k, v in kv.items():
            if k not in os.environ or os.environ.get(k, "") == "":
                os.environ[k] = v
    except Exception as e:
        logging.debug("Failed to load AGENTS.env: %s", e)


def get_scopes() -> List[str]:
    env_scopes = os.environ.get("GSHEETS_SCOPES", "").strip()
    if env_scopes:
        return [s for s in env_scopes.split() if s]
    return DEFAULT_SCOPES


def _client_config_from_env() -> Dict[str, Any]:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are required in env.")
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [
                "http://localhost",
                "http://localhost:8080",
                "urn:ietf:wg:oauth:2.0:oob",
            ],
        }
    }


def do_auth(use_local_server: bool = True, scopes: Optional[List[str]] = None) -> Credentials:
    scopes = scopes or get_scopes()
    flow = InstalledAppFlow.from_client_config(_client_config_from_env(), scopes=scopes)
    if use_local_server:
        # Use ephemeral port by default to avoid collisions with 8080.
        port = 0
        try:
            port = int(os.environ.get("GOOGLE_OAUTH_LOCAL_PORT", "0"))
        except Exception:
            port = 0
        creds = flow.run_local_server(open_browser=True, port=port)
    else:
        creds = flow.run_console()
    return creds


def creds_from_refresh(scopes: Optional[List[str]] = None) -> Credentials:
    # Use scopes authorized by the refresh token; do not request new scopes here.
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        raise SystemExit("Missing one of GOOGLE_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN in env.")
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=None,
    )
    creds.refresh(GoogleRequest())
    return creds


def sheets_service(creds: Credentials):
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def drive_service(creds: Credentials):
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def jitter_sleep(base: float, attempt: int, cap: float = 32.0) -> None:
    sleep = min(cap, base * (2 ** attempt))
    sleep = sleep * (0.5 + random.random())  # jitter 0.5x–1.5x
    time.sleep(sleep)


def with_retries(func, *, max_attempts: int = 5, base_delay: float = 0.5):
    attempt = 0
    while True:
        try:
            return func()
        except HttpError as e:
            status = getattr(e, "status_code", None) or getattr(e, "resp", {}).get("status")
            try:
                status = int(status)
            except Exception:
                status = None
            if status in (429, 500, 502, 503, 504) and attempt < max_attempts - 1:
                logging.warning("HTTP %s; retrying (attempt %d/%d)...", status, attempt + 1, max_attempts)
                jitter_sleep(base_delay, attempt)
                attempt += 1
                continue
            raise


def notify_telegram(msg: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": msg[:3900]}, timeout=10)
    except Exception as e:
        logging.debug("Telegram notify failed: %s", e)


def cmd_auth(args) -> int:
    load_agents_env(args.env)
    scopes = get_scopes()
    try:
        creds = do_auth(use_local_server=not args.no_local_server, scopes=scopes)
    except Exception as e:
        logging.error("Auth failed: %s", e)
        notify_telegram(f"gsheets auth failed: {e}")
        return 1
    refresh = creds.refresh_token
    if not refresh:
        logging.error("No refresh token received. Ensure you approved offline access and used a Desktop app client.")
        return 2
    line = f"export GOOGLE_OAUTH_REFRESH_TOKEN={refresh}"
    print(line)
    if args.write_env:
        env_path = args.env or os.path.expanduser("~/AGENTS.env")
        try:
            with open(env_path, "a", encoding="utf-8") as f:
                f.write("\n" + line + "\n")
            print(f"Appended refresh token to {env_path}")
        except Exception as e:
            logging.error("Failed to append to env file: %s", e)
            return 3
    return 0


def cmd_read(args) -> int:
    load_agents_env(args.env)
    scopes = get_scopes()
    creds = creds_from_refresh(scopes)
    svc = sheets_service(creds)

    spreadsheet_id = args.spreadsheet or os.environ.get("SHEETS_DEFAULT_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise SystemExit("--spreadsheet or SHEETS_DEFAULT_SPREADSHEET_ID required")
    rng = args.range
    if not rng:
        raise SystemExit("--range is required (e.g., 'Sheet1!A1:C10')")

    def _call():
        return (
            svc.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=rng, majorDimension=args.major)
            .execute()
        )

    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def _parse_values_arg(values_arg: Optional[str]) -> List[List[Any]]:
    if not values_arg:
        raise SystemExit("--values is required; pass JSON array (one row) or array of arrays (multiple rows)")
    try:
        parsed = json.loads(values_arg)
    except json.JSONDecodeError as e:
        raise SystemExit(f"--values must be valid JSON: {e}")
    if isinstance(parsed, list) and (not parsed or not isinstance(parsed[0], list)):
        return [parsed]
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], list):
        return parsed
    raise SystemExit("--values must be a JSON array or array of arrays")


def cmd_append(args) -> int:
    load_agents_env(args.env)
    scopes = get_scopes()
    creds = creds_from_refresh(scopes)
    svc = sheets_service(creds)

    spreadsheet_id = args.spreadsheet or os.environ.get("SHEETS_DEFAULT_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise SystemExit("--spreadsheet or SHEETS_DEFAULT_SPREADSHEET_ID required")
    rng = args.range
    if not rng:
        raise SystemExit("--range is required (e.g., 'Sheet1!A:Z')")
    values = _parse_values_arg(args.values)

    body = {"values": values}

    def _call():
        return (
            svc.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=rng,
                valueInputOption=args.input,
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )

    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_update(args) -> int:
    load_agents_env(args.env)
    scopes = get_scopes()
    creds = creds_from_refresh(scopes)
    svc = sheets_service(creds)

    spreadsheet_id = args.spreadsheet or os.environ.get("SHEETS_DEFAULT_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise SystemExit("--spreadsheet or SHEETS_DEFAULT_SPREADSHEET_ID required")
    rng = args.range
    if not rng:
        raise SystemExit("--range is required (e.g., 'Sheet1!B2')")
    values = _parse_values_arg(args.values)

    body = {"range": rng, "majorDimension": args.major, "values": values}

    def _call():
        return (
            svc.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=rng,
                valueInputOption=args.input,
                body=body,
            )
            .execute()
        )

    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_create_tab(args) -> int:
    load_agents_env(args.env)
    scopes = get_scopes()
    creds = creds_from_refresh(scopes)
    svc = sheets_service(creds)

    spreadsheet_id = args.spreadsheet or os.environ.get("SHEETS_DEFAULT_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise SystemExit("--spreadsheet or SHEETS_DEFAULT_SPREADSHEET_ID required")

    add_sheet = {
        "addSheet": {
            "properties": {
                "title": args.title,
                "gridProperties": {"rowCount": args.rows, "columnCount": args.cols},
            }
        }
    }
    if args.tab_color:
        try:
            r, g, b = [int(x) for x in args.tab_color.split(",")]
            add_sheet["addSheet"]["properties"]["tabColor"] = {"red": r / 255, "green": g / 255, "blue": b / 255}
        except Exception:
            raise SystemExit("--tab-color must be 'R,G,B' (0-255)")

    def _call():
        return (
            svc.spreadsheets()
            .batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": [add_sheet]})
            .execute()
        )

    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_create_sheet(args) -> int:
    load_agents_env(args.env)
    scopes = get_scopes()
    creds = creds_from_refresh(scopes)
    drv = drive_service(creds)

    metadata = {"name": args.title, "mimeType": "application/vnd.google-apps.spreadsheet"}

    def _call():
        return drv.files().create(body=metadata, fields="id").execute()

    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_share(args) -> int:
    load_agents_env(args.env)
    scopes = get_scopes()
    creds = creds_from_refresh(scopes)
    drv = drive_service(creds)

    perm = {"type": "user", "role": args.role, "emailAddress": args.email}

    def _call():
        return (
            drv.permissions()
            .create(fileId=args.file, body=perm, sendNotificationEmail=not args.no_email)
            .execute()
        )

    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Google Sheets Ops (OAuth)")
    p.add_argument("--env", help="Path to AGENTS.env (default ~/AGENTS.env)")
    p.add_argument("--verbose", action="store_true", help="Enable debug logging")

    sp = p.add_subparsers(dest="cmd", required=True)

    pa = sp.add_parser("auth", help="Run OAuth flow and print refresh token export line")
    pa.add_argument("--no-local-server", action="store_true", help="Use console flow (no local server)")
    pa.add_argument("--write-env", action="store_true", help="Append refresh token to env file")
    pa.set_defaults(func=cmd_auth)

    pr = sp.add_parser("read", help="Read range values")
    pr.add_argument("--spreadsheet", help="Spreadsheet ID; else SHEETS_DEFAULT_SPREADSHEET_ID")
    pr.add_argument("--range", required=True, help="A1 notation, e.g., 'Sheet1!A1:C10'")
    pr.add_argument("--major", default="ROWS", choices=["ROWS", "COLUMNS"], help="Major dimension")
    pr.set_defaults(func=cmd_read)

    pa = sp.add_parser("append", help="Append rows to a range")
    pa.add_argument("--spreadsheet", help="Spreadsheet ID; else SHEETS_DEFAULT_SPREADSHEET_ID")
    pa.add_argument("--range", required=True, help="Target range, e.g., 'Sheet1!A:Z'")
    pa.add_argument("--values", required=True, help="JSON array (one row) or array of arrays")
    pa.add_argument("--input", default="USER_ENTERED", choices=["RAW", "USER_ENTERED"], help="Value input option")
    pa.set_defaults(func=cmd_append)

    pu = sp.add_parser("update", help="Update cells in a range")
    pu.add_argument("--spreadsheet", help="Spreadsheet ID; else SHEETS_DEFAULT_SPREADSHEET_ID")
    pu.add_argument("--range", required=True, help="A1 notation, e.g., 'Sheet1!B2' or 'Sheet1!A2:C2'")
    pu.add_argument("--values", required=True, help="JSON array (one row) or array of arrays")
    pu.add_argument("--major", default="ROWS", choices=["ROWS", "COLUMNS"], help="Major dimension")
    pu.add_argument("--input", default="USER_ENTERED", choices=["RAW", "USER_ENTERED"], help="Value input option")
    pu.set_defaults(func=cmd_update)

    pct = sp.add_parser("create-tab", help="Create a new worksheet (tab)")
    pct.add_argument("--spreadsheet", help="Spreadsheet ID; else SHEETS_DEFAULT_SPREADSHEET_ID")
    pct.add_argument("--title", required=True, help="Tab title")
    pct.add_argument("--rows", type=int, default=1000)
    pct.add_argument("--cols", type=int, default=26)
    pct.add_argument("--tab-color", help="Optional tab color 'R,G,B' 0-255")
    pct.set_defaults(func=cmd_create_tab)

    pcs = sp.add_parser("create-sheet", help="Create a new spreadsheet (Drive)")
    pcs.add_argument("--title", required=True, help="Spreadsheet name")
    pcs.set_defaults(func=cmd_create_sheet)

    psh = sp.add_parser("share", help="Share a file (Drive)")
    psh.add_argument("--file", required=True, help="File (spreadsheet) ID")
    psh.add_argument("--email", required=True, help="User email to grant access")
    psh.add_argument("--role", default="writer", choices=["reader", "commenter", "writer", "owner"], help="Permission role")
    psh.add_argument("--no-email", action="store_true", help="Do not send email notification")
    psh.set_defaults(func=cmd_share)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s")
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except SystemExit as e:
        # pass through SystemExit with message already printed
        raise e
    except Exception as e:
        logging.error("Error: %s", e)
        notify_telegram(f"gsheets {args.cmd} failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
