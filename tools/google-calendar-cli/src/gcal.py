#!/usr/bin/env python3
import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
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
        os.environ[k] = v


def get_scopes() -> List[str]:
    env_scopes = os.environ.get("GCAL_SCOPES", "").strip()
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
        creds = flow.run_local_server(open_browser=True, port=0)
    else:
        creds = flow.run_console()
    return creds


def creds_from_refresh() -> Credentials:
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


def cal_service(creds: Credentials):
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def people_service(creds: Credentials):
    return build("people", "v1", credentials=creds, cache_discovery=False)


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


def parse_dt_or_date(val: str, tz: Optional[str]) -> Dict[str, str]:
    s = (val or "").strip()
    if not s:
        raise SystemExit("Datetime or date value required")
    if len(s) == 10 and s[4] == '-' and s[7] == '-':
        return {"date": s}
    # Assume ISO8601; pass through
    out = {"dateTime": s}
    if tz:
        out["timeZone"] = tz
    return out


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cmd_auth(args) -> int:
    load_agents_env(args.env)
    try:
        creds = do_auth(use_local_server=not args.no_local_server, scopes=get_scopes())
    except Exception as e:
        logging.error("Auth failed: %s", e)
        notify_telegram(f"gcal auth failed: {e}")
        return 1
    refresh = creds.refresh_token
    if not refresh:
        logging.error("No refresh token received. Ensure Desktop client and offline access.")
        return 2
    line = f"export GOOGLE_OAUTH_REFRESH_TOKEN={refresh}"
    print(line)
    if args.write_env:
        env_path = args.env or os.path.expanduser("~/AGENTS.env")
        with open(env_path, "a", encoding="utf-8") as f:
            f.write("\n" + line + "\n")
        print(f"Appended refresh token to {env_path}")
    return 0


def cmd_calendars(args) -> int:
    load_agents_env(args.env)
    svc = cal_service(creds_from_refresh())
    resp = svc.calendarList().list().execute()
    print(json.dumps(resp, indent=2))
    return 0


def cmd_events_list(args) -> int:
    load_agents_env(args.env)
    svc = cal_service(creds_from_refresh())
    cal_id = args.calendar
    time_min = args.time_from or iso_now()
    time_max = args.time_to or (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    resp = svc.events().list(
        calendarId=cal_id,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime',
        maxResults=args.max,
    ).execute()
    print(json.dumps(resp, indent=2))
    return 0


def parse_attendees(val: Optional[str]) -> Optional[List[Dict[str, str]]]:
    if not val:
        return None
    out = []
    for e in val.split(','):
        e = e.strip()
        if e:
            out.append({"email": e})
    return out


def groups_map(psvc) -> Dict[str, str]:
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
    mp.setdefault('myContacts', 'contactGroups/myContacts')
    return mp


def resolve_group_resource(psvc, spec: str) -> str:
    spec = (spec or '').strip()
    if not spec:
        raise SystemExit('--attendees-group requires a group spec')
    if spec.startswith('contactGroups/'):
        return spec
    mp = groups_map(psvc)
    rn = mp.get(spec) or mp.get(spec.lower())
    if not rn:
        raise SystemExit(f'Unknown contact group: {spec}')
    return rn


def emails_from_groups(creds: Credentials, groups: List[str]) -> List[Dict[str, str]]:
    if not groups:
        return []
    psvc = people_service(creds)
    rns: List[str] = []
    for g in groups:
        rn = resolve_group_resource(psvc, g)
        grp = psvc.contactGroups().get(resourceName=rn, maxMembers=1000).execute()
        rns.extend(grp.get('memberResourceNames', []) or [])
    # batch get in chunks of 200
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
    # dedupe, preserve order
    seen = set()
    out: List[Dict[str, str]] = []
    for em in emails:
        key = em.lower()
        if key not in seen:
            seen.add(key)
            out.append({'email': em})
    return out


def build_rrule(args) -> Optional[str]:
    # Prefer explicit --recurrence if provided
    if getattr(args, 'recurrence', None):
        return args.recurrence
    freq = getattr(args, 'repeat', None)
    if not freq:
        return None
    parts = [f'FREQ={freq.upper()}']
    if getattr(args, 'interval', None):
        parts.append(f'INTERVAL={int(args.interval)}')
    if getattr(args, 'by_day', None):
        # normalize tokens like MO,TU,WE
        days = ','.join([d.strip().upper() for d in args.by_day.split(',') if d.strip()])
        if days:
            parts.append(f'BYDAY={days}')
    if getattr(args, 'by_month_day', None):
        nums = ','.join([n.strip() for n in args.by_month_day.split(',') if n.strip()])
        if nums:
            parts.append(f'BYMONTHDAY={nums}')
    if getattr(args, 'count', None):
        parts.append(f'COUNT={int(args.count)}')
    elif getattr(args, 'until', None):
        # UNTIL must be in UTC in YYYYMMDDTHHMMSSZ or YYYYMMDD format
        u = args.until.strip()
        if len(u) == 10 and u[4] == '-' and u[7] == '-':
            u = u.replace('-', '')  # YYYYMMDD
        else:
            # attempt to keep as-is; user can pass e.g., 20251201T230000Z
            u = u
        parts.append(f'UNTIL={u}')
    return 'RRULE:' + ';'.join(parts)


def cmd_events_create(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh()
    svc = cal_service(creds)
    body: Dict[str, Any] = {"summary": args.summary}
    if args.description:
        body["description"] = args.description
    if args.location:
        body["location"] = args.location
    if args.start:
        body["start"] = parse_dt_or_date(args.start, args.timezone)
    if args.end:
        body["end"] = parse_dt_or_date(args.end, args.timezone)
    if args.attendees:
        body["attendees"] = parse_attendees(args.attendees)
    rrule = build_rrule(args)
    if rrule:
        body["recurrence"] = [rrule]
    # attendees from groups
    # collect attendees from labels/groups
    label_specs: List[str] = []
    if args.attendees_group:
        label_specs += sum([g.split(',') for g in args.attendees_group], [])
    if getattr(args, 'attendees_label', None):
        label_specs += sum([g.split(',') for g in args.attendees_label], [])
    if label_specs:
        group_attendees = emails_from_groups(creds, label_specs)
        if group_attendees:
            body.setdefault('attendees', [])
            # merge attendees
            existing = {a['email'].lower() for a in body['attendees']}
            for a in group_attendees:
                if a['email'].lower() not in existing:
                    body['attendees'].append(a)
    conferenceDataVersion = None
    if args.meet:
        body.setdefault("conferenceData", {"createRequest": {"requestId": uuid.uuid4().hex}})
        conferenceDataVersion = 1
    params = {"sendUpdates": args.send_updates}
    if conferenceDataVersion:
        params["conferenceDataVersion"] = conferenceDataVersion
    if getattr(args, 'dry_run', False):
        print(json.dumps({
            "dry_run": True,
            "action": "events.create",
            "calendar": args.calendar,
            "body": body,
            "params": params,
        }, indent=2))
        return 0
    resp = svc.events().insert(calendarId=args.calendar, body=body, **params).execute()
    print(json.dumps(resp, indent=2))
    return 0


def cmd_events_update(args) -> int:
    load_agents_env(args.env)
    creds = creds_from_refresh()
    svc = cal_service(creds)
    body: Dict[str, Any] = {}
    if args.summary is not None:
        body["summary"] = args.summary
    if args.description is not None:
        body["description"] = args.description
    if args.location is not None:
        body["location"] = args.location
    if args.start is not None:
        body["start"] = parse_dt_or_date(args.start, args.timezone)
    if args.end is not None:
        body["end"] = parse_dt_or_date(args.end, args.timezone)
    if args.attendees is not None:
        body["attendees"] = parse_attendees(args.attendees)
    rrule = build_rrule(args)
    if rrule is not None:
        body['recurrence'] = [rrule]
    if (args.attendees_group is not None) or (getattr(args, 'attendees_label', None) is not None):
        label_specs: List[str] = []
        if args.attendees_group:
            label_specs += sum([g.split(',') for g in (args.attendees_group or [])], [])
        if getattr(args, 'attendees_label', None):
            label_specs += sum([g.split(',') for g in (args.attendees_label or [])], [])
        group_attendees = emails_from_groups(creds, label_specs)
        body['attendees'] = group_attendees
    params = {"sendUpdates": args.send_updates}
    if getattr(args, 'dry_run', False):
        print(json.dumps({
            "dry_run": True,
            "action": "events.update",
            "calendar": args.calendar,
            "event": args.event,
            "body": body,
            "params": params,
        }, indent=2))
        return 0
    resp = svc.events().patch(calendarId=args.calendar, eventId=args.event, body=body, **params).execute()
    print(json.dumps(resp, indent=2))
    return 0


def cmd_events_delete(args) -> int:
    load_agents_env(args.env)
    svc = cal_service(creds_from_refresh())
    resp = svc.events().delete(calendarId=args.calendar, eventId=args.event, sendUpdates=args.send_updates).execute()
    print(json.dumps(resp, indent=2))
    return 0


def cmd_events_quick_add(args) -> int:
    load_agents_env(args.env)
    svc = cal_service(creds_from_refresh())
    resp = svc.events().quickAdd(calendarId=args.calendar, text=args.text).execute()
    print(json.dumps(resp, indent=2))
    return 0


def cmd_freebusy(args) -> int:
    load_agents_env(args.env)
    svc = cal_service(creds_from_refresh())
    body = {
        "timeMin": args.time_from,
        "timeMax": args.time_to,
        "items": [{"id": args.calendar}],
    }
    resp = svc.freebusy().query(body=body).execute()
    print(json.dumps(resp, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Google Calendar Ops (OAuth)")
    p.add_argument("--env", help="Path to AGENTS.env (default ~/AGENTS.env)")

    sp = p.add_subparsers(dest="cmd", required=True)

    pa = sp.add_parser("auth", help="Run OAuth flow and print refresh token export line")
    pa.add_argument("--no-local-server", action="store_true", help="Use console flow (no local server)")
    pa.add_argument("--write-env", action="store_true", help="Append refresh token to env file")
    pa.set_defaults(func=cmd_auth)

    pc = sp.add_parser("calendars", help="List calendars")
    pc.set_defaults(func=cmd_calendars)

    pe = sp.add_parser("events", help="Manage events")
    se = pe.add_subparsers(dest="events_cmd", required=True)

    pel = se.add_parser("list", help="List events in a time window")
    pel.add_argument("--calendar", default="primary")
    pel.add_argument("--from", dest="time_from", help="ISO8601 start (default now)")
    pel.add_argument("--to", dest="time_to", help="ISO8601 end (default +7d)")
    pel.add_argument("--max", type=int, default=50)
    pel.set_defaults(func=cmd_events_list)

    pec = se.add_parser("create", help="Create an event")
    pec.add_argument("--calendar", default="primary")
    pec.add_argument("--summary", required=True)
    pec.add_argument("--description")
    pec.add_argument("--location")
    pec.add_argument("--start", required=True, help="ISO8601 datetime or YYYY-MM-DD for all-day")
    pec.add_argument("--end", required=True, help="ISO8601 datetime or YYYY-MM-DD for all-day")
    pec.add_argument("--timezone", help="IANA tz (e.g., America/Chicago)")
    pec.add_argument("--attendees", help="Comma-separated emails")
    pec.add_argument("--attendees-group", action='append', help="Contact label/group spec(s); repeat or comma-separate")
    pec.add_argument("--attendees-label", action='append', help="Alias of --attendees-group (People label)")
    pec.add_argument("--recurrence", help="RRULE string (e.g., FREQ=WEEKLY;BYDAY=FR)")
    pec.add_argument("--repeat", choices=["DAILY","WEEKLY","MONTHLY","YEARLY"], help="Recurrence preset (builds RRULE)")
    pec.add_argument("--interval", type=int, help="Recurrence interval (default 1)")
    pec.add_argument("--by-day", help="BYDAY list, e.g., MO,WE,FR")
    pec.add_argument("--by-month-day", help="BYMONTHDAY list, e.g., 1,15")
    pec.add_argument("--count", type=int, help="Number of occurrences")
    pec.add_argument("--until", help="End date/time, e.g., 2025-12-01 or 20251201T230000Z")
    pec.add_argument("--send-updates", default="none", choices=["all", "externalOnly", "none"])
    pec.add_argument("--meet", action="store_true", help="Add Google Meet link")
    pec.set_defaults(func=cmd_events_create)

    peu = se.add_parser("update", help="Update an event (patch)")
    peu.add_argument("--calendar", default="primary")
    peu.add_argument("--event", required=True)
    peu.add_argument("--summary")
    peu.add_argument("--description")
    peu.add_argument("--location")
    peu.add_argument("--start", help="ISO8601 or YYYY-MM-DD")
    peu.add_argument("--end", help="ISO8601 or YYYY-MM-DD")
    peu.add_argument("--timezone", help="IANA tz for start/end")
    peu.add_argument("--attendees", help="Comma-separated emails")
    peu.add_argument("--attendees-group", action='append', help="Contact label/group spec(s)")
    peu.add_argument("--attendees-label", action='append', help="Alias of --attendees-group")
    peu.add_argument("--send-updates", default="none", choices=["all", "externalOnly", "none"])
    peu.add_argument("--recurrence", help="RRULE string to replace")
    peu.add_argument("--repeat", choices=["DAILY","WEEKLY","MONTHLY","YEARLY"], help="Recurrence preset")
    peu.add_argument("--interval", type=int, help="Recurrence interval")
    peu.add_argument("--by-day", help="BYDAY list")
    peu.add_argument("--by-month-day", help="BYMONTHDAY list")
    peu.add_argument("--count", type=int, help="Occurrences count")
    peu.add_argument("--until", help="End date/time")
    peu.set_defaults(func=cmd_events_update)

    ped = se.add_parser("delete", help="Delete an event")
    ped.add_argument("--calendar", default="primary")
    ped.add_argument("--event", required=True)
    ped.add_argument("--send-updates", default="none", choices=["all", "externalOnly", "none"])
    ped.set_defaults(func=cmd_events_delete)

    peq = se.add_parser("quick-add", help="Quick add via natural language")
    peq.add_argument("--calendar", default="primary")
    peq.add_argument("--text", required=True)
    peq.set_defaults(func=cmd_events_quick_add)

    peb = se.add_parser("bulk-create", help="Create many events from a JSON/JSONL file")
    peb.add_argument("--file", required=True, help="Path to JSON Lines or JSON array of event specs")
    peb.add_argument("--dry-run", action="store_true", help="Show what would be created")
    def _bulk_create(args):
        load_agents_env(args.env)
        creds = creds_from_refresh()
        svc = cal_service(creds)
        # Read file
        import json, os
        p = os.path.expanduser(args.file)
        with open(p, 'r', encoding='utf-8') as f:
            txt = f.read()
        specs: List[Dict[str, Any]] = []
        try:
            data = json.loads(txt)
            if isinstance(data, list):
                specs = data
            else:
                raise ValueError('Top-level JSON must be an array')
        except Exception:
            # try JSONL
            specs = []
            for line in txt.splitlines():
                line=line.strip()
                if not line: continue
                specs.append(json.loads(line))
        results = []
        for spec in specs:
            calendar = spec.get('calendar', 'primary')
            body: Dict[str, Any] = {"summary": spec.get('summary','')}
            if spec.get('description'): body['description'] = spec['description']
            if spec.get('location'): body['location'] = spec['location']
            tz = spec.get('timezone')
            if spec.get('start'): body['start'] = parse_dt_or_date(spec['start'], tz)
            if spec.get('end'): body['end'] = parse_dt_or_date(spec['end'], tz)
            if spec.get('attendees'): body['attendees'] = parse_attendees(spec.get('attendees'))
            # label attendees
            label_specs: List[str] = []
            for key in ('attendees_label','attendees_group'):
                val = spec.get(key)
                if isinstance(val, str):
                    label_specs.extend([x.strip() for x in val.split(',') if x.strip()])
                elif isinstance(val, list):
                    for v in val:
                        label_specs.extend([x.strip() for x in str(v).split(',') if x.strip()])
            if label_specs:
                group_attendees = emails_from_groups(creds, label_specs)
                if group_attendees:
                    body.setdefault('attendees', [])
                    existing = {a['email'].lower() for a in body['attendees']}
                    for a in group_attendees:
                        if a['email'].lower() not in existing:
                            body['attendees'].append(a)
            # recurrence
            class A: pass
            a = A()
            a.recurrence = spec.get('recurrence')
            a.repeat = spec.get('repeat')
            a.interval = spec.get('interval')
            a.by_day = spec.get('by_day')
            a.by_month_day = spec.get('by_month_day')
            a.count = spec.get('count')
            a.until = spec.get('until')
            rr = build_rrule(a)
            if rr: body['recurrence'] = [rr]
            params = {"sendUpdates": spec.get('send_updates','none')}
            if spec.get('meet'):
                body.setdefault('conferenceData', {"createRequest": {"requestId": uuid.uuid4().hex}})
                params['conferenceDataVersion'] = 1
            if args.dry_run:
                results.append({"calendar": calendar, "body": body, "params": params})
            else:
                ev = svc.events().insert(calendarId=calendar, body=body, **params).execute()
                results.append({"calendar": calendar, "id": ev.get('id'), "htmlLink": ev.get('htmlLink')})
        print(json.dumps(results, indent=2))
        return 0
    peb.set_defaults(func=_bulk_create)

    pf = sp.add_parser("freebusy", help="Free/Busy query for a calendar")
    pf.add_argument("--calendar", default="primary")
    pf.add_argument("--from", dest="time_from", required=True)
    pf.add_argument("--to", dest="time_to", required=True)
    pf.set_defaults(func=cmd_freebusy)

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
        logging.error("HTTP error: %s", e)
        notify_telegram(f"gcal {getattr(args,'cmd','?')} failed: {e}")
        return 1
    except Exception as e:
        logging.error("Error: %s", e)
        notify_telegram(f"gcal {getattr(args,'cmd','?')} failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
