#!/usr/bin/env python3
import argparse
import base64
import json
import os
import sys
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from email.utils import getaddresses

import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    # Needed for label create/apply/remove operations
    "https://www.googleapis.com/auth/gmail.modify",
    # Needed for alias (sendAs) settings
    "https://www.googleapis.com/auth/gmail.settings.basic",
    # Read Contacts (labels/people) for label-based recipients
    "https://www.googleapis.com/auth/contacts.readonly",
]


def load_agents_env(path: Optional[str] = None) -> None:
    env_path = path or os.environ.get("AGENTS_ENV_PATH", os.path.expanduser("~/AGENTS.env"))
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
            if k:
                kv[k] = v
    for k, v in kv.items():
        if k not in os.environ or os.environ.get(k, "") == "":
            os.environ[k] = v


def get_scopes() -> List[str]:
    env_scopes = os.environ.get("GMAIL_SCOPES", "").strip()
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
    # Do not request scopes during refresh; use what the refresh token is authorized for.
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


def gmail_service(creds: Credentials):
    return build('gmail', 'v1', credentials=creds, cache_discovery=False)


def people_service(creds: Credentials):
    return build('people', 'v1', credentials=creds, cache_discovery=False)


# Contacts label helpers
def _groups_map(psvc) -> Dict[str, str]:
    resp = psvc.contactGroups().list(pageSize=1000).execute()
    mp: Dict[str, str] = {}
    for g in resp.get('contactGroups', []) or []:
        rn = g.get('resourceName') or ''
        gid = rn.split('/', 1)[-1] if rn else ''
        name = g.get('name') or ''
        if rn:
            mp[rn] = rn
        if gid:
            mp[gid] = rn
        if name:
            mp[name] = rn
            mp[name.lower()] = rn
    mp.setdefault('myContacts', 'contactGroups/myContacts')
    return mp


def _resolve_group_resource(psvc, spec: str) -> str:
    spec = (spec or '').strip()
    if not spec:
        raise SystemExit('Contacts label is required')
    if spec.startswith('contactGroups/'):
        return spec
    mp = _groups_map(psvc)
    rn = mp.get(spec) or mp.get(spec.lower())
    if not rn:
        raise SystemExit(f'Unknown contact label: {spec}')
    return rn


def _emails_from_labels(creds: Credentials, labels: List[str]) -> List[str]:
    if not labels:
        return []
    psvc = people_service(creds)
    rns: List[str] = []
    for lab in labels:
        rn = _resolve_group_resource(psvc, lab)
        grp = psvc.contactGroups().get(resourceName=rn, maxMembers=1000).execute()
        rns.extend(grp.get('memberResourceNames', []) or [])
    emails: List[str] = []
    for i in range(0, len(rns), 200):
        chunk = rns[i:i+200]
        resp = psvc.people().getBatchGet(resourceNames=chunk, personFields='emailAddresses').execute()
        for e in resp.get('responses', []) or []:
            person = e.get('person') or {}
            for ea in person.get('emailAddresses', []) or []:
                val = (ea.get('value') or '').strip()
                if val:
                    emails.append(val)
    seen = set(); out: List[str] = []
    for em in emails:
        k = em.lower()
        if k not in seen:
            seen.add(k)
            out.append(em)
    return out


def _resolve_addrs(creds: Credentials, base: Optional[str], labels: Optional[List[str]]) -> List[str]:
    parts: List[str] = []
    if base:
        parts.extend([x.strip() for x in base.split(',') if x.strip()])
    if labels:
        labs: List[str] = []
        for l in labels:
            labs.extend([x.strip() for x in l.split(',') if x.strip()])
        parts.extend(_emails_from_labels(creds, labs))
    seen=set(); out=[]
    for p in parts:
        k=p.lower()
        if k and k not in seen:
            seen.add(k); out.append(p)
    return out


def cmd_resolve(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    result = {
        "to": _resolve_addrs(creds, args.to, getattr(args, 'to_label', None)),
        "cc": _resolve_addrs(creds, args.cc, getattr(args, 'cc_label', None)),
        "bcc": _resolve_addrs(creds, args.bcc, getattr(args, 'bcc_label', None)),
    }
    print(json.dumps(result, indent=2))
    return 0


def notify_telegram(msg: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": msg[:3900]}, timeout=10)
    except Exception:
        pass


def cmd_auth(args) -> int:
    load_agents_env(args.env)
    try:
        creds = do_auth(use_local_server=not args.no_local_server, scopes=get_scopes())
    except Exception as e:
        print(f"Auth failed: {e}", file=sys.stderr)
        return 1
    refresh = creds.refresh_token
    if not refresh:
        print("No refresh token received (ensure Desktop client and offline access).", file=sys.stderr)
        return 2
    line = f"export GOOGLE_OAUTH_REFRESH_TOKEN={refresh}"
    print(line)
    if args.write_env:
        env_path = args.env or os.path.expanduser("~/AGENTS.env")
        with open(env_path, 'a', encoding='utf-8') as f:
            f.write('\n' + line + '\n')
        print(f"Appended refresh token to {env_path}")
    return 0


def cmd_me(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    prof = svc.users().getProfile(userId='me').execute()
    print(json.dumps(prof, indent=2))
    return 0


def cmd_list(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    resp = svc.users().messages().list(userId='me', q=args.q, maxResults=args.max).execute()
    print(json.dumps(resp, indent=2))
    return 0


def cmd_get(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    msg = svc.users().messages().get(userId='me', id=args.id, format=args.format).execute()
    print(json.dumps(msg, indent=2))
    return 0


def build_message(args) -> bytes:
    msg = MIMEMultipart('alternative')
    # Headers are set by resolved args.to/cc/bcc prior to calling this
    msg['To'] = args.to or ""
    if args.cc:
        msg['Cc'] = args.cc
    if args.bcc:
        # Bcc not set in headers to recipients, but Gmail API allows including it here
        msg['Bcc'] = args.bcc
    msg['Subject'] = args.subject
    if args.sender:
        msg['From'] = args.sender
    if args.text:
        msg.attach(MIMEText(args.text, 'plain', 'utf-8'))
    if args.html:
        msg.attach(MIMEText(args.html, 'html', 'utf-8'))
    return msg.as_bytes()


def cmd_send(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh(get_scopes())
    # Expand Contacts labels if provided
    def merge_addrs(base: Optional[str], labels: Optional[List[str]]) -> str:
        parts: List[str] = []
        if base:
            parts.extend([x.strip() for x in base.split(',') if x.strip()])
        if labels:
            labs: List[str] = []
            for l in labels:
                labs.extend([x.strip() for x in l.split(',') if x.strip()])
            parts.extend(_emails_from_labels(creds, labs))
        # dedupe preserve order
        seen=set(); out=[]
        for p in parts:
            k=p.lower()
            if k and k not in seen:
                seen.add(k); out.append(p)
        return ', '.join(out)
    args.to = merge_addrs(args.to, getattr(args, 'to_label', None))
    args.cc = merge_addrs(args.cc, getattr(args, 'cc_label', None))
    args.bcc = merge_addrs(args.bcc, getattr(args, 'bcc_label', None))
    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "action": "send",
            "to": args.to or "",
            "cc": args.cc or "",
            "bcc": args.bcc or "",
            "subject": args.subject,
            "has_text": bool(args.text),
            "has_html": bool(args.html),
            "sender": args.sender or "",
        }, indent=2))
        return 0
    svc = gmail_service(creds)
    if not (args.text or args.html):
        print("Provide --text and/or --html", file=sys.stderr)
        return 2
    raw = base64.urlsafe_b64encode(build_message(args)).decode('ascii')
    body = {'raw': raw}
    sent = svc.users().messages().send(userId='me', body=body).execute()
    print(json.dumps(sent, indent=2))
    return 0


# --- Label helpers ---

def _labels_map(svc) -> Dict[str, Dict[str, Any]]:
    resp = svc.users().labels().list(userId='me').execute()
    by_id = {lbl['id']: lbl for lbl in resp.get('labels', [])}
    by_name = {lbl['name']: lbl for lbl in resp.get('labels', [])}
    # merge maps, prefer id lookups but allow name fallbacks
    return {**{k: v for k, v in by_id.items()}, **{k: v for k, v in by_name.items()}}


def _resolve_label_ids(svc, labels: List[str], create_missing: bool = False) -> List[str]:
    if not labels:
        return []
    mapping = _labels_map(svc)
    ids: List[str] = []
    for spec in labels:
        spec = spec.strip()
        if not spec:
            continue
        lbl = mapping.get(spec)
        if lbl:
            ids.append(lbl['id'])
            continue
        if create_missing:
            body: Dict[str, Any] = {"name": spec}
            created = svc.users().labels().create(userId='me', body=body).execute()
            ids.append(created['id'])
            # refresh mapping minimally
            mapping[created['id']] = created
            mapping[created['name']] = created
        else:
            raise SystemExit(f"Label not found: {spec} (use --create-missing to auto-create)")
    return ids


def cmd_labels_list(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    resp = svc.users().labels().list(userId='me').execute()
    labels = resp.get('labels', [])
    if args.kind == 'user':
        labels = [l for l in labels if l.get('type') == 'user']
    elif args.kind == 'system':
        labels = [l for l in labels if l.get('type') == 'system']
    print(json.dumps(labels, indent=2))
    return 0


# --- Alias (sendAs) helpers ---

def cmd_aliases_list(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    resp = svc.users().settings().sendAs().list(userId='me').execute()
    print(json.dumps(resp.get('sendAs', []), indent=2))
    return 0


def _smtp_security(mode: Optional[str]) -> Optional[str]:
    if not mode:
        return None
    m = mode.upper()
    if m == 'SSL':
        return 'SECURITY_MODE_SSL'
    if m == 'TLS':
        return 'SECURITY_MODE_STARTTLS'
    return 'SECURITY_MODE_NONE'


def cmd_aliases_create(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    body: Dict[str, Any] = {
        'sendAsEmail': args.email,
    }
    if args.display_name:
        body['displayName'] = args.display_name
    if args.reply_to:
        body['replyToAddress'] = args.reply_to
    if args.signature is not None:
        body['signature'] = args.signature
    if args.treat_as_alias:
        body['treatAsAlias'] = True
    # Optional external SMTP config
    if args.smtp_host:
        smtp: Dict[str, Any] = {'host': args.smtp_host}
        if args.smtp_port:
            smtp['port'] = int(args.smtp_port)
        if args.smtp_username:
            smtp['username'] = args.smtp_username
        if args.smtp_password:
            smtp['password'] = args.smtp_password
        sec = _smtp_security(args.smtp_security)
        if sec:
            smtp['securityMode'] = sec
        body['smtpMsa'] = smtp
    created = svc.users().settings().sendAs().create(userId='me', body=body).execute()
    print(json.dumps(created, indent=2))
    return 0


def cmd_aliases_update(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    body: Dict[str, Any] = {}
    if args.display_name is not None:
        body['displayName'] = args.display_name
    if args.reply_to is not None:
        body['replyToAddress'] = args.reply_to
    if args.signature is not None:
        body['signature'] = args.signature
    if args.treat_as_alias is not None:
        body['treatAsAlias'] = True if args.treat_as_alias == 'true' else False
    if args.is_default is not None:
        body['isDefault'] = True if args.is_default == 'true' else False
    updated = svc.users().settings().sendAs().patch(userId='me', sendAsEmail=args.email, body=body).execute()
    print(json.dumps(updated, indent=2))
    return 0


def cmd_aliases_set_default(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    updated = svc.users().settings().sendAs().patch(userId='me', sendAsEmail=args.email, body={'isDefault': True}).execute()
    print(json.dumps(updated, indent=2))
    return 0


def cmd_aliases_verify(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    resp = svc.users().settings().sendAs().verify(userId='me', sendAsEmail=args.email).execute()
    print(json.dumps(resp, indent=2))
    return 0


# --- Outbox queue helpers ---

OUTBOX_DIR = Path.home() / ".codex" / "tools" / "gmail_outbox"
QUEUE_PATH = OUTBOX_DIR / "queue.jsonl"
HISTORY_PATH = OUTBOX_DIR / "history.jsonl"
LOCK_PATH = OUTBOX_DIR / ".dispatch.lock"


def _ensure_outbox():
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    if not QUEUE_PATH.exists():
        QUEUE_PATH.write_text("")
    if not HISTORY_PATH.exists():
        HISTORY_PATH.write_text("")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_send_at(val: str) -> int:
    s = val.strip()
    s = s.replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        raise SystemExit("--send-at must be ISO8601, e.g. 2025-08-29T17:30:00-05:00 or 2025-08-29T22:30:00Z")
    if dt.tzinfo is None:
        # assume local time
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _read_jsonl(p: Path) -> List[Dict[str, Any]]:
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _write_jsonl(p: Path, rows: List[Dict[str, Any]]) -> None:
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def cmd_queue_add(args) -> int:
    load_agents_env(args.env)
    if not (args.text or args.html):
        print("Provide --text and/or --html", file=sys.stderr)
        return 2
    _ensure_outbox()
    now = int(time.time())
    send_at = _parse_send_at(args.send_at)
    if send_at < now - 30:
        print("--send-at is in the past; use a future time", file=sys.stderr)
        return 2
    item = {
        "id": str(uuid.uuid4()),
        "created_at": now,
        "created_at_iso": _iso(datetime.now(timezone.utc)),
        "send_at": send_at,
        "send_at_iso": _iso(datetime.fromtimestamp(send_at, tz=timezone.utc)),
        "attempts": 0,
        "last_error": None,
        "payload": {
            "to": args.to,
            "cc": args.cc or "",
            "bcc": args.bcc or "",
            "subject": args.subject,
            "text": args.text or "",
            "html": args.html or "",
            "sender": args.sender or "",
        },
    }
    if getattr(args, 'dry_run', False):
        print(json.dumps({"dry_run": True, "queued": False, "item": item}, indent=2))
        return 0
    with QUEUE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(json.dumps({"queued": True, "id": item["id"], "send_at": item["send_at_iso"]}, indent=2))
    return 0


def cmd_queue_list(args) -> int:
    _ensure_outbox()
    rows = _read_jsonl(QUEUE_PATH)
    rows.sort(key=lambda r: r.get("send_at", 0))
    print(json.dumps(rows[: args.limit], indent=2))
    return 0


def cmd_queue_history(args) -> int:
    _ensure_outbox()
    rows = _read_jsonl(HISTORY_PATH)
    print(json.dumps(rows[-args.limit :], indent=2))
    return 0


def _acquire_lock() -> bool:
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False


def _release_lock() -> None:
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def _send_scheduled(svc, payload: Dict[str, Any]) -> Dict[str, Any]:
    class A:
        pass

    a = A()
    a.to = payload.get("to", "")
    a.cc = payload.get("cc", "")
    a.bcc = payload.get("bcc", "")
    a.subject = payload.get("subject", "")
    a.text = payload.get("text", "")
    a.html = payload.get("html", "")
    a.sender = payload.get("sender") or None
    raw = base64.urlsafe_b64encode(build_message(a)).decode('ascii')
    body = {'raw': raw}
    return svc.users().messages().send(userId='me', body=body).execute()


def cmd_queue_dispatch(args) -> int:
    load_agents_env(args.env)
    _ensure_outbox()
    if getattr(args, 'dry_run', False):
        now = int(time.time())
        pending = _read_jsonl(QUEUE_PATH)
        due = [
            {
                "id": it.get('id'),
                "send_at": it.get('send_at_iso'),
                "subject": (it.get('payload',{}) or {}).get('subject',''),
                "to": (it.get('payload',{}) or {}).get('to',''),
            }
            for it in pending if int(it.get('send_at',0)) <= now
        ]
        print(json.dumps({"dry_run": True, "due_count": len(due), "due": due[: args.max]}, indent=2))
        return 0
    if not _acquire_lock():
        # Another dispatcher is running
        return 0
    try:
        svc = gmail_service(creds_from_refresh(get_scopes()))
        now = int(time.time())
        pending = _read_jsonl(QUEUE_PATH)
        remaining: List[Dict[str, Any]] = []
        sent_count = 0
        for item in pending:
            if sent_count >= args.max:
                remaining.append(item)
                continue
            due = int(item.get("send_at", 0)) <= now
            if not due:
                remaining.append(item)
                continue
            attempts = int(item.get("attempts", 0))
            try:
                result = _send_scheduled(svc, item.get("payload", {}))
                hist = {
                    "id": item.get("id"),
                    "status": "sent",
                    "attempts": attempts + 1,
                    "sent_at": _iso(datetime.now(timezone.utc)),
                    "result": result,
                    "payload": item.get("payload", {}),
                }
                with HISTORY_PATH.open("a", encoding="utf-8") as hf:
                    hf.write(json.dumps(hist, ensure_ascii=False) + "\n")
                sent_count += 1
            except HttpError as e:
                # Backoff and requeue unless attempts exceeded
                status = getattr(e, 'status_code', None) or getattr(e, 'resp', {}).get('status')
                try:
                    status = int(status)
                except Exception:
                    status = None
                attempts += 1
                if attempts >= 5 or (status and 400 <= status < 500 and status not in (429,)):
                    hist = {
                        "id": item.get("id"),
                        "status": "failed",
                        "attempts": attempts,
                        "failed_at": _iso(datetime.now(timezone.utc)),
                        "error": str(e),
                        "payload": item.get("payload", {}),
                    }
                    with HISTORY_PATH.open("a", encoding="utf-8") as hf:
                        hf.write(json.dumps(hist, ensure_ascii=False) + "\n")
                    # Telegram alert on failure (if configured)
                    p = item.get("payload", {})
                    subj = p.get("subject", "(no subject)")
                    notify_telegram(f"Gmail scheduled send failed:\nsubject: {subj}\nid: {item.get('id')}\nerror: {e}")
                else:
                    # requeue with backoff
                    backoff = min(3600, int(60 * (2 ** (attempts - 1))))
                    item["attempts"] = attempts
                    item["last_error"] = str(e)
                    item["send_at"] = now + backoff
                    item["send_at_iso"] = _iso(datetime.fromtimestamp(item["send_at"], tz=timezone.utc))
                    remaining.append(item)
        _write_jsonl(QUEUE_PATH, remaining)
        print(json.dumps({"dispatched": sent_count, "remaining": len(remaining)}, indent=2))
        return 0
    finally:
        _release_lock()


def cmd_queue_update(args) -> int:
    load_agents_env(args.env)
    _ensure_outbox()
    rows = _read_jsonl(QUEUE_PATH)
    updated = None
    for r in rows:
        if r.get('id') == args.id:
            p = r.get('payload', {})
            if args.to is not None:
                p['to'] = args.to
            if args.cc is not None:
                p['cc'] = args.cc
            if args.bcc is not None:
                p['bcc'] = args.bcc
            if args.subject is not None:
                p['subject'] = args.subject
            if args.text is not None:
                p['text'] = args.text
            if args.html is not None:
                p['html'] = args.html
            if args.sender is not None:
                p['sender'] = args.sender
            r['payload'] = p
            if args.send_at is not None:
                send_at = _parse_send_at(args.send_at)
                r['send_at'] = send_at
                r['send_at_iso'] = _iso(datetime.fromtimestamp(send_at, tz=timezone.utc))
            updated = r
            break
    if not updated:
        print(json.dumps({"updated": False, "error": "not_found"}, indent=2))
        return 1
    _write_jsonl(QUEUE_PATH, rows)
    print(json.dumps({"updated": True, "item": updated}, indent=2))
    return 0


def cmd_queue_cancel(args) -> int:
    load_agents_env(args.env)
    _ensure_outbox()
    rows = _read_jsonl(QUEUE_PATH)
    new_rows = [r for r in rows if r.get('id') != args.id]
    canceled = len(new_rows) != len(rows)
    if canceled:
        _write_jsonl(QUEUE_PATH, new_rows)
    print(json.dumps({"canceled": canceled, "id": args.id}, indent=2))
    return 0


def cmd_labels_create(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    body: Dict[str, Any] = {"name": args.name}
    if args.bg_color or args.fg_color:
        body["color"] = {}
        if args.bg_color:
            body["color"]["backgroundColor"] = args.bg_color
        if args.fg_color:
            body["color"]["textColor"] = args.fg_color
    created = svc.users().labels().create(userId='me', body=body).execute()
    print(json.dumps(created, indent=2))
    return 0


def cmd_labels_apply(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    add = []
    rem = []
    if args.add:
        add = _resolve_label_ids(svc, sum([a.split(',') for a in args.add], []), create_missing=args.create_missing)
    if args.remove:
        rem = _resolve_label_ids(svc, sum([r.split(',') for r in args.remove], []), create_missing=False)
    body = {"addLabelIds": add, "removeLabelIds": rem}
    if args.message and args.thread:
        raise SystemExit("Use either --message or --thread, not both")
    if not args.message and not args.thread:
        raise SystemExit("Specify --message <ID> or --thread <ID>")
    if args.message:
        resp = svc.users().messages().modify(userId='me', id=args.message, body=body).execute()
    else:
        resp = svc.users().threads().modify(userId='me', id=args.thread, body=body).execute()
    print(json.dumps(resp, indent=2))
    return 0


def headers_map(payload: Dict[str, Any]) -> Dict[str, str]:
    hdrs = {}
    for h in payload.get('headers', []) or []:
        name = h.get('name')
        value = h.get('value')
        if name and value is not None:
            hdrs[name.lower()] = value
    return hdrs


def unique_recipients(*lists: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for lst in lists:
        for addr in lst:
            key = addr.lower()
            if key and key not in seen:
                seen.add(key)
                out.append(addr)
    return out


def cmd_reply(args) -> int:
    load_agents_env(args.env)
    if not (args.text or args.html):
        print("Provide --text and/or --html", file=sys.stderr)
        return 2
    creds = creds_from_refresh(get_scopes())
    svc = gmail_service(creds)
    orig = svc.users().messages().get(userId='me', id=args.id, format='full').execute()
    profile = svc.users().getProfile(userId='me').execute()
    me_email = (profile.get('emailAddress') or '').lower()
    payload = orig.get('payload', {})
    hdrs = headers_map(payload)
    subj = hdrs.get('subject', '')
    msg_id = hdrs.get('message-id')
    refs = hdrs.get('references')
    from_addrs = [a for _, a in getaddresses([hdrs.get('from', '')]) if a]
    to_addrs = [a for _, a in getaddresses([hdrs.get('to', '')]) if a]
    cc_addrs = [a for _, a in getaddresses([hdrs.get('cc', '')]) if a]

    if args.reply_all:
        to_list = unique_recipients(from_addrs, [x for x in to_addrs if x.lower() != me_email])
        cc_list = [x for x in unique_recipients(cc_addrs) if x.lower() != me_email]
    else:
        to_list = from_addrs or to_addrs[:1]
        cc_list = []

    if args.subject:
        subject = args.subject
    else:
        subject = subj if subj.lower().startswith('re:') else f"Re: {subj}"

    # Merge Contacts labels into To/Cc/Bcc if provided
    def merge_with_labels(lst: List[str], labels: Optional[List[str]]) -> List[str]:
        parts = lst[:]
        if labels:
            labs=[]
            for l in labels:
                labs.extend([x.strip() for x in l.split(',') if x.strip()])
            parts.extend(_emails_from_labels(creds, labs))
        seen=set(); out=[]
        for p in parts:
            k=p.lower()
            if k and k not in seen:
                seen.add(k); out.append(p)
        return out
    to_list = merge_with_labels(to_list, getattr(args,'to_label',None))
    cc_list = merge_with_labels(cc_list, getattr(args,'cc_label',None))
    bcc_list = merge_with_labels([], getattr(args,'bcc_label',None))

    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "action": "reply",
            "to": to_list,
            "cc": cc_list,
            "bcc": bcc_list,
            "subject": subject,
            "has_text": bool(args.text),
            "has_html": bool(args.html),
            "sender": args.sender or "",
            "threadId": orig.get('threadId')
        }, indent=2))
        return 0
    msg = MIMEMultipart('alternative')
    msg['To'] = ', '.join(to_list)
    if cc_list:
        msg['Cc'] = ', '.join(cc_list)
    if bcc_list:
        msg['Bcc'] = ', '.join(bcc_list)
    msg['Subject'] = subject
    if args.sender:
        msg['From'] = args.sender
    if msg_id:
        msg['In-Reply-To'] = msg_id
        msg['References'] = f"{refs} {msg_id}" if refs else msg_id
    if args.text:
        msg.attach(MIMEText(args.text, 'plain', 'utf-8'))
    if args.html:
        msg.attach(MIMEText(args.html, 'html', 'utf-8'))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('ascii')
    body = {'raw': raw, 'threadId': orig.get('threadId')}
    sent = svc.users().messages().send(userId='me', body=body).execute()
    print(json.dumps(sent, indent=2))
    return 0


def cmd_draft_create(args) -> int:
    load_agents_env(args.env)
    if not (args.text or args.html):
        print("Provide --text and/or --html", file=sys.stderr)
        return 2
    creds = creds_from_refresh(get_scopes())
    # Expand Contacts labels for To/Cc/Bcc
    def merge_addrs(base: Optional[str], labels: Optional[List[str]]) -> str:
        parts: List[str] = []
        if base:
            parts.extend([x.strip() for x in base.split(',') if x.strip()])
        if labels:
            labs=[]
            for l in labels:
                labs.extend([x.strip() for x in l.split(',') if x.strip()])
            parts.extend(_emails_from_labels(creds, labs))
        seen=set(); out=[]
        for p in parts:
            k=p.lower()
            if k and k not in seen:
                seen.add(k); out.append(p)
        return ', '.join(out)
    args.to = merge_addrs(args.to, getattr(args,'to_label',None))
    args.cc = merge_addrs(args.cc, getattr(args,'cc_label',None))
    args.bcc = merge_addrs(args.bcc, getattr(args,'bcc_label',None))
    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "action": "draft_create",
            "to": args.to or "",
            "cc": args.cc or "",
            "bcc": args.bcc or "",
            "subject": args.subject or "",
            "has_text": bool(args.text),
            "has_html": bool(args.html),
            "sender": args.sender or "",
            "thread": args.thread or "",
        }, indent=2))
        return 0
    svc = gmail_service(creds)
    # Build a temporary args-like object for build_message compatibility
    class A: pass
    a = A()
    a.to = args.to or ''
    a.cc = args.cc or ''
    a.bcc = args.bcc or ''
    a.subject = args.subject or ''
    a.sender = args.sender or None
    a.text = args.text
    a.html = args.html
    raw = base64.urlsafe_b64encode(build_message(a)).decode('ascii')
    msg: Dict[str, Any] = {'raw': raw}
    if args.thread:
        msg['threadId'] = args.thread
    draft = svc.users().drafts().create(userId='me', body={'message': msg}).execute()
    print(json.dumps(draft, indent=2))
    return 0


def cmd_draft_send(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    sent = svc.users().drafts().send(userId='me', body={'id': args.id}).execute()
    print(json.dumps(sent, indent=2))
    return 0


def cmd_draft_delete(args) -> int:
    load_agents_env(args.env)
    svc = gmail_service(creds_from_refresh(get_scopes()))
    resp = svc.users().drafts().delete(userId='me', id=args.id).execute()
    print(json.dumps(resp, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Gmail Ops (OAuth)')
    p.add_argument('--env', help='Path to AGENTS.env (default ~/AGENTS.env)')

    sp = p.add_subparsers(dest='cmd', required=True)

    pa = sp.add_parser('auth', help='Run OAuth flow and print refresh token export line')
    pa.add_argument('--no-local-server', action='store_true', help='Use console flow (no local server)')
    pa.add_argument('--write-env', action='store_true', help='Append refresh token to env file')
    pa.set_defaults(func=cmd_auth)

    pm = sp.add_parser('me', help='Show Gmail profile for the authorized user')
    pm.set_defaults(func=cmd_me)

    pl = sp.add_parser('list', help='List messages by Gmail query')
    pl.add_argument('--q', default='in:inbox newer_than:7d', help='Gmail search query')
    pl.add_argument('--max', type=int, default=10, help='Max results')
    pl.set_defaults(func=cmd_list)

    pg = sp.add_parser('get', help='Get one message')
    pg.add_argument('--id', required=True, help='Message ID')
    pg.add_argument('--format', default='metadata', choices=['minimal', 'full', 'metadata', 'raw'], help='Message format')
    pg.set_defaults(func=cmd_get)

    prc = sp.add_parser('resolve', help='Resolve recipients from direct emails and Contacts labels')
    prc.add_argument('--to', help='To recipients (comma-separated)')
    prc.add_argument('--cc', help='Cc recipients (comma-separated)')
    prc.add_argument('--bcc', help='Bcc recipients (comma-separated)')
    prc.add_argument('--to-label', action='append', help='Contacts label(s) for To')
    prc.add_argument('--cc-label', action='append', help='Contacts label(s) for Cc')
    prc.add_argument('--bcc-label', action='append', help='Contacts label(s) for Bcc')
    prc.set_defaults(func=cmd_resolve)

    ps = sp.add_parser('send', help='Send an email')
    ps.add_argument('--to', required=True, help='To recipients (comma-separated)')
    ps.add_argument('--cc', help='Cc recipients (comma-separated)')
    ps.add_argument('--bcc', help='Bcc recipients (comma-separated)')
    ps.add_argument('--to-label', action='append', help='Contacts label(s) for To')
    ps.add_argument('--cc-label', action='append', help='Contacts label(s) for Cc')
    ps.add_argument('--bcc-label', action='append', help='Contacts label(s) for Bcc')
    ps.add_argument('--subject', required=True, help='Subject line')
    ps.add_argument('--text', help='Plain text body')
    ps.add_argument('--html', help='HTML body')
    ps.add_argument('--sender', help='From address (optional)')
    ps.add_argument('--dry-run', action='store_true', help='Resolve recipients and show summary without sending')
    ps.set_defaults(func=cmd_send)

    pr = sp.add_parser('reply', help='Reply to a message')
    pr.add_argument('--id', required=True, help='Message ID to reply to')
    pr.add_argument('--reply-all', action='store_true', help='Include original To/Cc (excluding yourself)')
    pr.add_argument('--to-label', action='append', help='Contacts label(s) to add to To')
    pr.add_argument('--cc-label', action='append', help='Contacts label(s) to add to Cc')
    pr.add_argument('--bcc-label', action='append', help='Contacts label(s) to add to Bcc')
    pr.add_argument('--subject', help='Override subject; defaults to Re: <original>')
    pr.add_argument('--text', help='Plain text body')
    pr.add_argument('--html', help='HTML body')
    pr.add_argument('--sender', help='From address (optional)')
    pr.add_argument('--dry-run', action='store_true', help='Resolve recipients and show summary without sending')
    pr.set_defaults(func=cmd_reply)

    pd = sp.add_parser('draft', help='Manage drafts')
    sd = pd.add_subparsers(dest='draft_cmd', required=True)
    pdc = sd.add_parser('create', help='Create a draft')
    pdc.add_argument('--to', help='To recipients (comma-separated)')
    pdc.add_argument('--cc', help='Cc recipients (comma-separated)')
    pdc.add_argument('--bcc', help='Bcc recipients (comma-separated)')
    pdc.add_argument('--to-label', action='append', help='Contacts label(s) for To')
    pdc.add_argument('--cc-label', action='append', help='Contacts label(s) for Cc')
    pdc.add_argument('--bcc-label', action='append', help='Contacts label(s) for Bcc')
    pdc.add_argument('--subject', help='Subject line')
    pdc.add_argument('--text', help='Plain text body')
    pdc.add_argument('--html', help='HTML body')
    pdc.add_argument('--sender', help='From address (optional)')
    pdc.add_argument('--thread', help='Optional threadId to file under')
    pdc.add_argument('--dry-run', action='store_true', help='Resolve recipients and show summary without creating')
    pdc.set_defaults(func=cmd_draft_create)
    pds = sd.add_parser('send', help='Send a draft by ID')
    pds.add_argument('--id', required=True, help='Draft ID')
    pds.set_defaults(func=cmd_draft_send)
    pdd = sd.add_parser('delete', help='Delete a draft by ID')
    pdd.add_argument('--id', required=True, help='Draft ID')
    pdd.set_defaults(func=cmd_draft_delete)

    plb = sp.add_parser('labels', help='Manage Gmail labels')
    slb = plb.add_subparsers(dest='labels_cmd', required=True)
    pll = slb.add_parser('list', help='List labels')
    pll.add_argument('--kind', default='user', choices=['user', 'system', 'all'], help='Which labels to list')
    pll.set_defaults(func=cmd_labels_list)
    plc = slb.add_parser('create', help='Create a user label')
    plc.add_argument('--name', required=True, help='Label display name')
    plc.add_argument('--bg-color', help='Background color hex, e.g., #000000')
    plc.add_argument('--fg-color', help='Text color hex, e.g., #ffffff')
    plc.set_defaults(func=cmd_labels_create)
    pla = slb.add_parser('apply', help='Apply/remove labels on a message/thread')
    grp = pla.add_mutually_exclusive_group(required=True)
    grp.add_argument('--message', help='Target message ID')
    grp.add_argument('--thread', help='Target thread ID')
    pla.add_argument('--add', action='append', help='Label IDs or names to add (comma-separated or repeated)')
    pla.add_argument('--remove', action='append', help='Label IDs or names to remove (comma-separated or repeated)')
    pla.add_argument('--create-missing', action='store_true', help='Auto-create missing user labels for --add')
    pla.set_defaults(func=cmd_labels_apply)

    # Aliases (sendAs)
    pal = sp.add_parser('aliases', help='Manage Gmail aliases (sendAs)')
    sal = pal.add_subparsers(dest='aliases_cmd', required=True)
    pall = sal.add_parser('list', help='List sendAs aliases')
    pall.set_defaults(func=cmd_aliases_list)
    palc = sal.add_parser('create', help='Create a sendAs alias (triggers verification email)')
    palc.add_argument('--email', required=True, help='Alias email address')
    palc.add_argument('--display-name', help='Display name')
    palc.add_argument('--reply-to', help='Reply-To address')
    palc.add_argument('--signature', help='Signature HTML')
    palc.add_argument('--treat-as-alias', action='store_true', help='Treat as alias (recommended)')
    palc.add_argument('--smtp-host', help='SMTP host for external alias (optional)')
    palc.add_argument('--smtp-port', type=int, help='SMTP port')
    palc.add_argument('--smtp-username', help='SMTP username')
    palc.add_argument('--smtp-password', help='SMTP password')
    palc.add_argument('--smtp-security', choices=['NONE','SSL','TLS'], help='SMTP security mode')
    palc.set_defaults(func=cmd_aliases_create)
    palu = sal.add_parser('update', help='Update a sendAs alias settings')
    palu.add_argument('--email', required=True, help='Alias email address to update')
    palu.add_argument('--display-name', help='New display name')
    palu.add_argument('--reply-to', help='New reply-to')
    palu.add_argument('--signature', help='New signature HTML')
    palu.add_argument('--treat-as-alias', type=str, choices=['true','false'], help='Set treatAsAlias')
    palu.add_argument('--is-default', type=str, choices=['true','false'], help='Set alias as default or not')
    palu.set_defaults(func=cmd_aliases_update)
    pals = sal.add_parser('set-default', help='Set default From alias')
    pals.add_argument('--email', required=True, help='Alias email to set as default')
    pals.set_defaults(func=cmd_aliases_set_default)
    palv = sal.add_parser('verify', help='Trigger verification email for alias')
    palv.add_argument('--email', required=True, help='Alias email to verify')
    palv.set_defaults(func=cmd_aliases_verify)

    # Outbox queue (scheduled sends)
    pq = sp.add_parser('queue', help='Outbox queue for scheduled sends')
    sq = pq.add_subparsers(dest='queue_cmd', required=True)
    pqa = sq.add_parser('add', help='Queue a scheduled email send')
    pqa.add_argument('--to', required=True, help='To recipients (comma-separated)')
    pqa.add_argument('--cc', help='Cc recipients')
    pqa.add_argument('--bcc', help='Bcc recipients')
    pqa.add_argument('--subject', required=True, help='Subject line')
    pqa.add_argument('--text', help='Plain text body')
    pqa.add_argument('--html', help='HTML body')
    pqa.add_argument('--sender', help='From address (optional)')
    pqa.add_argument('--send-at', required=True, help='ISO8601 datetime, e.g. 2025-08-29T17:30:00-05:00 or 2025-08-29T22:30:00Z')
    pqa.add_argument('--dry-run', action='store_true', help='Preview without writing to queue')
    pqa.set_defaults(func=cmd_queue_add)

    pql = sq.add_parser('list', help='List pending scheduled emails')
    pql.add_argument('--limit', type=int, default=50, help='Limit rows shown')
    pql.set_defaults(func=cmd_queue_list)

    pqh = sq.add_parser('history', help='Show recent dispatch history')
    pqh.add_argument('--limit', type=int, default=50, help='Limit rows shown')
    pqh.set_defaults(func=cmd_queue_history)

    pqd = sq.add_parser('dispatch', help='Process due emails (intended for LaunchAgent)')
    pqd.add_argument('--max', type=int, default=20, help='Max messages to send per run')
    pqd.add_argument('--dry-run', action='store_true', help='List due items without sending or modifying queue')
    pqd.set_defaults(func=cmd_queue_dispatch)

    pqu = sq.add_parser('update', help='Update a queued email by ID')
    pqu.add_argument('--id', required=True, help='Queue item ID')
    pqu.add_argument('--to', help='To recipients (comma-separated)')
    pqu.add_argument('--cc', help='Cc recipients')
    pqu.add_argument('--bcc', help='Bcc recipients')
    pqu.add_argument('--subject', help='Subject line')
    pqu.add_argument('--text', help='Plain text body')
    pqu.add_argument('--html', help='HTML body')
    pqu.add_argument('--sender', help='From address')
    pqu.add_argument('--send-at', help='New ISO8601 datetime to reschedule')
    pqu.set_defaults(func=cmd_queue_update)

    pqc = sq.add_parser('cancel', help='Cancel a queued email by ID')
    pqc.add_argument('--id', required=True, help='Queue item ID')
    pqc.set_defaults(func=cmd_queue_cancel)

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
    except HttpError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
