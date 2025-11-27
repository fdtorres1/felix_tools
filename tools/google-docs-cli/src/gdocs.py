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
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


def load_agents_env(path: Optional[str] = None) -> None:
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
                kv[k] = v
        for k, v in kv.items():
            if k not in os.environ or os.environ.get(k, "") == "":
                os.environ[k] = v
    except Exception as e:
        logging.debug("Failed to load AGENTS.env: %s", e)


def get_scopes() -> List[str]:
    env_scopes = os.environ.get("GDOCS_SCOPES", "").strip()
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


def docs_service(creds: Credentials):
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def drive_service(creds: Credentials):
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def get_document(creds: Credentials, doc_id: str) -> Dict[str, Any]:
    svc = docs_service(creds)
    return svc.documents().get(documentId=doc_id).execute()


def document_end_index(doc: Dict[str, Any]) -> int:
    body = doc.get("body", {})
    content = body.get("content", [])
    if not content:
        return 1
    end = content[-1].get("endIndex")
    if not isinstance(end, int):
        # Fallback: find last element with endIndex
        for elem in reversed(content):
            if isinstance(elem.get("endIndex"), int):
                return elem["endIndex"]
        return 1
    return end


def jitter_sleep(base: float, attempt: int, cap: float = 32.0) -> None:
    sleep = min(cap, base * (2 ** attempt))
    sleep = sleep * (0.5 + random.random())
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


def extract_text_from_element(elem: Dict[str, Any]) -> str:
    out = []
    if 'paragraph' in elem:
        for pe in elem['paragraph'].get('elements', []):
            tr = pe.get('textRun')
            if tr and 'content' in tr:
                out.append(tr['content'])
    if 'table' in elem:
        for row in elem['table'].get('tableRows', []):
            for cell in row.get('tableCells', []):
                for c in cell.get('content', []):
                    out.append(extract_text_from_element(c))
    if 'tableOfContents' in elem:
        for c in elem['tableOfContents'].get('content', []):
            out.append(extract_text_from_element(c))
    return ''.join(out)


def iter_heading_paragraphs(doc: Dict[str, Any]):
    body = doc.get('body', {})
    for elem in body.get('content', []):
        para = elem.get('paragraph')
        if not para:
            continue
        style = para.get('paragraphStyle', {})
        named = style.get('namedStyleType')
        if not named or not named.startswith('HEADING_'):
            continue
        level = int(named.split('_', 1)[1])
        text_parts: List[str] = []
        for pe in para.get('elements', []):
            tr = pe.get('textRun')
            if tr and 'content' in tr:
                text_parts.append(tr['content'])
        yield {
            'level': level,
            'text': ''.join(text_parts).rstrip('\n') if text_parts else '',
            'startIndex': elem.get('startIndex'),
            'endIndex': elem.get('endIndex'),
        }


def find_heading_end_index(doc: Dict[str, Any], match: str, level: Optional[int] = None, contains: bool = False, occurrence: int = 1) -> Optional[int]:
    occ = 0
    for h in iter_heading_paragraphs(doc):
        if level and h['level'] != level:
            continue
        ht = h['text'] or ''
        ok = (match in ht) if contains else (ht == match)
        if not ok:
            continue
        occ += 1
        if occ == occurrence:
            return h.get('endIndex')
    return None


def cmd_auth(args) -> int:
    load_agents_env(args.env)
    scopes = get_scopes()
    try:
        creds = do_auth(use_local_server=not args.no_local_server, scopes=scopes)
    except Exception as e:
        logging.error("Auth failed: %s", e)
        notify_telegram(f"gdocs auth failed: {e}")
        return 1
    refresh = creds.refresh_token
    if not refresh:
        logging.error("No refresh token received. Ensure Desktop client and offline access.")
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


def cmd_get(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    svc = docs_service(creds)
    doc_id = args.document
    if not doc_id:
        raise SystemExit("--document is required (Docs file ID)")

    def _call():
        return svc.documents().get(documentId=doc_id).execute()

    doc = with_retries(_call)
    if args.as_format == 'json':
        print(json.dumps(doc, indent=2))
    else:
        body = doc.get('body', {})
        content = body.get('content', [])
        chunks = [extract_text_from_element(e) for e in content]
        text = ''.join(chunks)
        print(text, end='')
    return 0


def cmd_find_replace(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    svc = docs_service(creds)

    requests_body = [{
        "replaceAllText": {
            "containsText": {"text": args.find, "matchCase": bool(args.match_case)},
            "replaceText": args.replace,
        }
    }]

    def _call():
        return svc.documents().batchUpdate(documentId=args.document, body={"requests": requests_body}).execute()

    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_append(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    svc = docs_service(creds)

    requests_body: List[Dict[str, Any]] = []
    if getattr(args, 'after_heading', None):
        doc = get_document(creds, args.document)
        idx = find_heading_end_index(doc, args.after_heading, level=getattr(args, 'heading_level', None), contains=bool(getattr(args, 'contains', False)), occurrence=getattr(args, 'occurrence', 1))
        if idx is None:
            raise SystemExit("Heading not found with given criteria")
        requests_body.append({
            "insertText": {"location": {"index": idx}, "text": args.text}
        })
    else:
        requests_body.append({
            "insertText": {"endOfSegmentLocation": {}, "text": args.text}
        })

    def _call():
        return svc.documents().batchUpdate(documentId=args.document, body={"requests": requests_body}).execute()

    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_create(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    svc = docs_service(creds)

    def _call():
        return svc.documents().create(body={"title": args.title}).execute()

    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_export(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    drv = drive_service(creds)

    def _call():
        return drv.files().export(fileId=args.document, mimeType=args.mime).execute()

    data = with_retries(_call)
    if args.out:
        out_path = os.path.expanduser(args.out)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        mode = 'wb'
        with open(out_path, mode) as f:
            if isinstance(data, bytes):
                f.write(data)
            else:
                f.write(data.encode('utf-8'))
        print(out_path)
    else:
        if isinstance(data, bytes):
            sys.stdout.buffer.write(data)
        else:
            print(data)
    return 0


def cmd_share(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    drv = drive_service(creds)
    perm = {"type": "user", "role": args.role, "emailAddress": args.email}

    def _call():
        return drv.permissions().create(fileId=args.file, body=perm, sendNotificationEmail=not args.no_email).execute()

    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_insert_heading(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    doc = get_document(creds, args.document)
    text = args.text.rstrip("\n") + "\n"
    if getattr(args, 'after_heading', None):
        start = find_heading_end_index(doc, args.after_heading, level=getattr(args, 'heading_level', None), contains=bool(getattr(args, 'contains', False)), occurrence=getattr(args, 'occurrence', 1))
        if start is None:
            raise SystemExit("Heading not found with given criteria")
    else:
        end_idx = document_end_index(doc)
        start = end_idx - 1
    end = start + len(text)
    requests_body = [
        {"insertText": {"location": {"index": start}, "text": text}},
        {
            "updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "paragraphStyle": {"namedStyleType": f"HEADING_{args.level}"},
                "fields": "namedStyleType",
            }
        },
    ]

    svc = docs_service(creds)
    def _call():
        return svc.documents().batchUpdate(documentId=args.document, body={"requests": requests_body}).execute()
    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_insert_table(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    svc = docs_service(creds)
    if getattr(args, 'after_heading', None):
        doc = get_document(creds, args.document)
        idx = find_heading_end_index(doc, args.after_heading, level=getattr(args, 'heading_level', None), contains=bool(getattr(args, 'contains', False)), occurrence=getattr(args, 'occurrence', 1))
        if idx is None:
            raise SystemExit("Heading not found with given criteria")
        requests_body = [{"insertTable": {"location": {"index": idx}, "rows": args.rows, "columns": args.cols}}]
    else:
        requests_body = [{"insertTable": {"endOfSegmentLocation": {}, "rows": args.rows, "columns": args.cols}}]
    def _call():
        return svc.documents().batchUpdate(documentId=args.document, body={"requests": requests_body}).execute()
    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_insert_image(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    doc = get_document(creds, args.document)
    if getattr(args, 'after_heading', None):
        anchor = find_heading_end_index(doc, args.after_heading, level=getattr(args, 'heading_level', None), contains=bool(getattr(args, 'contains', False)), occurrence=getattr(args, 'occurrence', 1))
        if anchor is None:
            raise SystemExit("Heading not found with given criteria")
        location = {"index": anchor}
    else:
        end_idx = document_end_index(doc)
        location = {"index": end_idx - 1}
    req = {
        "insertInlineImage": {
            "uri": args.uri,
            "location": location,
        }
    }
    if args.width or args.height:
        size: Dict[str, Any] = {}
        if args.width:
            size["width"] = {"magnitude": float(args.width), "unit": "PT"}
        if args.height:
            size["height"] = {"magnitude": float(args.height), "unit": "PT"}
        req["insertInlineImage"]["objectSize"] = size

    svc = docs_service(creds)
    def _call():
        return svc.documents().batchUpdate(documentId=args.document, body={"requests": [req]}).execute()
    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_insert_page_break(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    doc = get_document(creds, args.document)
    if getattr(args, 'after_heading', None):
        anchor = find_heading_end_index(doc, args.after_heading, level=getattr(args, 'heading_level', None), contains=bool(getattr(args, 'contains', False)), occurrence=getattr(args, 'occurrence', 1))
        if anchor is None:
            raise SystemExit("Heading not found with given criteria")
        loc = {"index": anchor}
    else:
        end_idx = document_end_index(doc)
        loc = {"index": end_idx - 1}
    req = {"insertPageBreak": {"location": loc}}
    svc = docs_service(creds)
    def _call():
        return svc.documents().batchUpdate(documentId=args.document, body={"requests": [req]}).execute()
    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_insert_section_break(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    doc = get_document(creds, args.document)
    if getattr(args, 'after_heading', None):
        anchor = find_heading_end_index(doc, args.after_heading, level=getattr(args, 'heading_level', None), contains=bool(getattr(args, 'contains', False)), occurrence=getattr(args, 'occurrence', 1))
        if anchor is None:
            raise SystemExit("Heading not found with given criteria")
        loc = {"index": anchor}
    else:
        end_idx = document_end_index(doc)
        loc = {"index": end_idx - 1}
    req = {"insertSectionBreak": {"sectionType": args.type, "location": loc}}
    svc = docs_service(creds)
    def _call():
        return svc.documents().batchUpdate(documentId=args.document, body={"requests": [req]}).execute()
    resp = with_retries(_call)
    print(json.dumps(resp, indent=2))
    return 0


def cmd_list_headings(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    doc = get_document(creds, args.document)
    body = doc.get('body', {})
    content = body.get('content', [])
    results: List[Dict[str, Any]] = []
    for elem in content:
        para = elem.get('paragraph')
        if not para:
            continue
        style = para.get('paragraphStyle', {})
        named = style.get('namedStyleType')
        if not named or not named.startswith('HEADING_'):
            continue
        level = int(named.split('_', 1)[1])
        text = []
        for pe in para.get('elements', []):
            tr = pe.get('textRun')
            if tr and 'content' in tr:
                text.append(tr['content'])
        results.append({"level": level, "text": ''.join(text).strip()})
    print(json.dumps(results, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Google Docs Ops (OAuth)")
    p.add_argument("--env", help="Path to AGENTS.env (default ~/AGENTS.env)")

    sp = p.add_subparsers(dest="cmd", required=True)

    pa = sp.add_parser("auth", help="Run OAuth flow and print refresh token export line")
    pa.add_argument("--no-local-server", action="store_true", help="Use console flow (no local server)")
    pa.add_argument("--write-env", action="store_true", help="Append refresh token to env file")
    pa.set_defaults(func=cmd_auth)

    pg = sp.add_parser("get", help="Fetch document; print as text or JSON")
    pg.add_argument("--document", required=True, help="Docs file ID")
    pg.add_argument("--as", dest="as_format", default="text", choices=["text", "json"], help="Output format")
    pg.set_defaults(func=cmd_get)

    pfr = sp.add_parser("find-replace", help="Replace all matching text in doc")
    pfr.add_argument("--document", required=True, help="Docs file ID")
    pfr.add_argument("--find", required=True, help="Find text (literal)")
    pfr.add_argument("--replace", required=True, help="Replacement text")
    pfr.add_argument("--match-case", action="store_true", help="Case-sensitive match")
    pfr.set_defaults(func=cmd_find_replace)

    pa = sp.add_parser("append", help="Append text at end of document")
    pa.add_argument("--document", required=True, help="Docs file ID")
    pa.add_argument("--text", required=True, help="Text to append (include newlines as needed)")
    pa.add_argument("--after-heading", help="Insert after the first matching heading text")
    pa.add_argument("--heading-level", type=int, choices=[1,2,3,4,5,6], help="Restrict match to heading level")
    pa.add_argument("--contains", action="store_true", help="Match heading by substring instead of exact")
    pa.add_argument("--occurrence", type=int, default=1, help="Nth occurrence to target (default 1)")
    pa.set_defaults(func=cmd_append)

    pc = sp.add_parser("create", help="Create a new Google Doc")
    pc.add_argument("--title", required=True, help="Document title")
    pc.set_defaults(func=cmd_create)

    pe = sp.add_parser("export", help="Export Google Doc via Drive API")
    pe.add_argument("--document", required=True, help="Docs file ID")
    pe.add_argument("--mime", required=True, help="MIME type (e.g., application/pdf, text/plain)")
    pe.add_argument("--out", help="Output file path; stdout if omitted")
    pe.set_defaults(func=cmd_export)

    psh = sp.add_parser("share", help="Share a Docs file (Drive)")
    psh.add_argument("--file", required=True, help="File (doc) ID")
    psh.add_argument("--email", required=True, help="User email")
    psh.add_argument("--role", default="writer", choices=["reader", "commenter", "writer", "owner"], help="Permission role")
    psh.add_argument("--no-email", action="store_true", help="Do not send email notification")
    psh.set_defaults(func=cmd_share)

    ph = sp.add_parser("insert-heading", help="Insert a heading at end of document")
    ph.add_argument("--document", required=True, help="Docs file ID")
    ph.add_argument("--text", required=True, help="Heading text")
    ph.add_argument("--level", type=int, default=1, choices=[1,2,3,4,5,6], help="Heading level (1-6)")
    ph.add_argument("--after-heading", help="Insert after the first matching heading text")
    ph.add_argument("--heading-level", type=int, choices=[1,2,3,4,5,6], help="Restrict match to heading level for anchor")
    ph.add_argument("--contains", action="store_true", help="Match heading by substring instead of exact")
    ph.add_argument("--occurrence", type=int, default=1, help="Nth occurrence to target (default 1)")
    ph.set_defaults(func=cmd_insert_heading)

    pt = sp.add_parser("insert-table", help="Insert a table at end of document")
    pt.add_argument("--document", required=True, help="Docs file ID")
    pt.add_argument("--rows", type=int, required=True, help="Row count")
    pt.add_argument("--cols", type=int, required=True, help="Column count")
    pt.add_argument("--after-heading", help="Insert after the first matching heading text")
    pt.add_argument("--heading-level", type=int, choices=[1,2,3,4,5,6], help="Restrict match to heading level for anchor")
    pt.add_argument("--contains", action="store_true", help="Match heading by substring instead of exact")
    pt.add_argument("--occurrence", type=int, default=1, help="Nth occurrence to target (default 1)")
    pt.set_defaults(func=cmd_insert_table)

    pi = sp.add_parser("insert-image", help="Insert an inline image at end of document")
    pi.add_argument("--document", required=True, help="Docs file ID")
    pi.add_argument("--uri", required=True, help="Public image URL")
    pi.add_argument("--width", type=float, help="Width in points (optional)")
    pi.add_argument("--height", type=float, help="Height in points (optional)")
    pi.add_argument("--after-heading", help="Insert after the first matching heading text")
    pi.add_argument("--heading-level", type=int, choices=[1,2,3,4,5,6], help="Restrict match to heading level for anchor")
    pi.add_argument("--contains", action="store_true", help="Match heading by substring instead of exact")
    pi.add_argument("--occurrence", type=int, default=1, help="Nth occurrence to target (default 1)")
    pi.set_defaults(func=cmd_insert_image)

    pp = sp.add_parser("insert-page-break", help="Insert a page break at end of document")
    pp.add_argument("--document", required=True, help="Docs file ID")
    pp.add_argument("--after-heading", help="Insert after the first matching heading text")
    pp.add_argument("--heading-level", type=int, choices=[1,2,3,4,5,6], help="Restrict match to heading level for anchor")
    pp.add_argument("--contains", action="store_true", help="Match heading by substring instead of exact")
    pp.add_argument("--occurrence", type=int, default=1, help="Nth occurrence to target (default 1)")
    pp.set_defaults(func=cmd_insert_page_break)

    psb = sp.add_parser("insert-section-break", help="Insert a section break at end")
    psb.add_argument("--document", required=True, help="Docs file ID")
    psb.add_argument("--type", default="NEXT_PAGE", choices=["NEXT_PAGE", "CONTINUOUS"], help="Section break type")
    psb.add_argument("--after-heading", help="Insert after the first matching heading text")
    psb.add_argument("--heading-level", type=int, choices=[1,2,3,4,5,6], help="Restrict match to heading level for anchor")
    psb.add_argument("--contains", action="store_true", help="Match heading by substring instead of exact")
    psb.add_argument("--occurrence", type=int, default=1, help="Nth occurrence to target (default 1)")
    psb.set_defaults(func=cmd_insert_section_break)

    pl = sp.add_parser("list-headings", help="List all headings in the document")
    pl.add_argument("--document", required=True, help="Docs file ID")
    pl.set_defaults(func=cmd_list_headings)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except SystemExit as e:
        raise e
    except Exception as e:
        logging.error("Error: %s", e)
        notify_telegram(f"gdocs {args.cmd} failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
