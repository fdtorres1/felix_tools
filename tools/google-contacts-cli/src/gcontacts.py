#!/usr/bin/env python3
import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/contacts",
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
    env_scopes = os.environ.get("GCONTACTS_SCOPES", "").strip()
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


def creds_from_refresh(scopes: Optional[List[str]] = None) -> Credentials:
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


def with_retries(func, *, max_attempts: int = 5):
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
                attempt += 1
                continue
            raise


def normalize_resource(s: str) -> str:
    s = (s or "").strip()
    if not s:
        raise SystemExit("--resource is required")
    return s if s.startswith("people/") else f"people/{s}"


def emails_list(val: Optional[str]) -> List[Dict[str, Any]]:
    if not val:
        return []
    return [{"value": v.strip()} for v in val.split(",") if v.strip()]


def phones_list(val: Optional[str]) -> List[Dict[str, Any]]:
    if not val:
        return []
    return [{"value": v.strip()} for v in val.split(",") if v.strip()]


def cmd_auth(args) -> int:
    load_agents_env(args.env)
    try:
        creds = do_auth(use_local_server=not args.no_local_server, scopes=get_scopes())
    except Exception as e:
        logging.error("Auth failed: %s", e)
        notify_telegram(f"gcontacts auth failed: {e}")
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


def cmd_list(args) -> int:
    load_agents_env(args.env)
    svc = people_service(creds_from_refresh())
    resp = with_retries(lambda: svc.people().connections().list(
        resourceName="people/me",
        pageSize=args.page_size,
        personFields=args.fields,
    ).execute())
    print(json.dumps(resp, indent=2))
    return 0


def cmd_search(args) -> int:
    load_agents_env(args.env)
    svc = people_service(creds_from_refresh())
    resp = with_retries(lambda: svc.people().searchContacts(
        query=args.query,
        pageSize=args.page_size,
        readMask=args.fields,
    ).execute())
    print(json.dumps(resp, indent=2))
    return 0


def cmd_get(args) -> int:
    load_agents_env(args.env)
    svc = people_service(creds_from_refresh())
    resource = normalize_resource(args.resource)
    resp = with_retries(lambda: svc.people().get(resourceName=resource, personFields=args.fields).execute())
    print(json.dumps(resp, indent=2))
    return 0


def cmd_create(args) -> int:
    load_agents_env(args.env)
    svc = people_service(creds_from_refresh())
    if args.json:
        with open(os.path.expanduser(args.json), "r", encoding="utf-8") as f:
            body = json.load(f)
    else:
        names = []
        if args.given_name or args.family_name or args.full_name:
            d: Dict[str, Any] = {}
            if args.given_name:
                d["givenName"] = args.given_name
            if args.family_name:
                d["familyName"] = args.family_name
            if args.full_name:
                d["displayName"] = args.full_name
            names = [d]
        body = {
            "names": names,
            "emailAddresses": emails_list(args.email),
            "phoneNumbers": phones_list(args.phone),
        }
        if args.org or args.title:
            body["organizations"] = [{"name": args.org or "", "title": args.title or ""}]
    resp = with_retries(lambda: svc.people().createContact(body=body).execute())
    print(json.dumps(resp, indent=2))
    return 0


ALLOWED_UPDATE_FIELDS = {"names", "emailAddresses", "phoneNumbers", "organizations", "addresses", "birthdays", "biographies"}


def cmd_update(args) -> int:
    load_agents_env(args.env)
    svc = people_service(creds_from_refresh())
    resource = normalize_resource(args.resource)
    current = with_retries(lambda: svc.people().get(resourceName=resource, personFields=",".join(ALLOWED_UPDATE_FIELDS)).execute())

    if args.json:
        with open(os.path.expanduser(args.json), "r", encoding="utf-8") as f:
            person = json.load(f)
        person["resourceName"] = resource
        person["etag"] = current.get("etag")
        if args.update_fields:
            update_fields = args.update_fields
        else:
            update_fields = ",".join(sorted(set(person.keys()) & ALLOWED_UPDATE_FIELDS)) or "names,emailAddresses,phoneNumbers"
    else:
        person = {"resourceName": resource, "etag": current.get("etag")}
        uf: List[str] = []
        if any([args.given_name, args.family_name, args.full_name]):
            d: Dict[str, Any] = {}
            if args.given_name:
                d["givenName"] = args.given_name
            if args.family_name:
                d["familyName"] = args.family_name
            if args.full_name:
                d["displayName"] = args.full_name
            person["names"] = [d]
            uf.append("names")
        if args.email is not None:
            person["emailAddresses"] = emails_list(args.email)
            uf.append("emailAddresses")
        if args.phone is not None:
            person["phoneNumbers"] = phones_list(args.phone)
            uf.append("phoneNumbers")
        if args.org is not None or args.title is not None:
            person["organizations"] = [{"name": args.org or "", "title": args.title or ""}]
            uf.append("organizations")
        update_fields = ",".join(uf) or "names,emailAddresses,phoneNumbers"

    resp = with_retries(lambda: svc.people().updateContact(
        resourceName=resource,
        body=person,
        updatePersonFields=update_fields,
    ).execute())
    print(json.dumps(resp, indent=2))
    return 0


def cmd_delete(args) -> int:
    load_agents_env(args.env)
    svc = people_service(creds_from_refresh())
    resource = normalize_resource(args.resource)
    resp = with_retries(lambda: svc.people().deleteContact(resourceName=resource).execute())
    print(json.dumps(resp, indent=2))
    return 0


def cmd_groups_list(args) -> int:
    load_agents_env(args.env)
    svc = people_service(creds_from_refresh())
    resp = with_retries(lambda: svc.contactGroups().list(pageSize=args.page_size).execute())
    print(json.dumps(resp, indent=2))
    return 0


def cmd_groups_create(args) -> int:
    load_agents_env(args.env)
    svc = people_service(creds_from_refresh())
    body = {"contactGroup": {"name": args.name}}
    resp = with_retries(lambda: svc.contactGroups().create(body=body).execute())
    print(json.dumps(resp, indent=2))
    return 0


def _groups_map(svc) -> Dict[str, str]:
    resp = with_retries(lambda: svc.contactGroups().list(pageSize=1000).execute())
    mp: Dict[str, str] = {}
    for g in resp.get('contactGroups', []) or []:
        rn = g.get('resourceName') or ''  # e.g., contactGroups/XXXXXXXX
        gid = g.get('resourceName', '').split('/', 1)[-1]
        name = g.get('name') or ''
        if rn:
            mp[rn] = rn
        if gid:
            mp[gid] = rn
        if name:
            mp[name] = rn
    # Always include myContacts
    mp.setdefault('myContacts', 'contactGroups/myContacts')
    return mp


def _resolve_group_resource(svc, spec: str) -> str:
    spec = (spec or '').strip()
    if not spec:
        raise SystemExit('--group is required')
    if spec.startswith('contactGroups/'):
        return spec
    mp = _groups_map(svc)
    rn = mp.get(spec)
    if not rn:
        raise SystemExit(f'Unknown contact group: {spec}')
    return rn


def cmd_groups_add_member(args) -> int:
    load_agents_env(args.env)
    svc = people_service(creds_from_refresh())
    person = normalize_resource(args.resource)
    group_rn = _resolve_group_resource(svc, args.group)
    body = {"resourceNamesToAdd": [person]}
    resp = with_retries(lambda: svc.contactGroups().members().modify(resourceName=group_rn, body=body).execute())
    print(json.dumps(resp, indent=2))
    return 0


def cmd_groups_remove_member(args) -> int:
    load_agents_env(args.env)
    svc = people_service(creds_from_refresh())
    person = normalize_resource(args.resource)
    group_rn = _resolve_group_resource(svc, args.group)
    body = {"resourceNamesToRemove": [person]}
    resp = with_retries(lambda: svc.contactGroups().members().modify(resourceName=group_rn, body=body).execute())
    print(json.dumps(resp, indent=2))
    return 0


def cmd_groups_emails(args) -> int:
    load_agents_env(args.env)
    svc = people_service(creds_from_refresh())
    specs = args.group or []
    # Resolve to resource names
    def _groups_map(psvc):
        resp = with_retries(lambda: psvc.contactGroups().list(pageSize=1000).execute())
        mp = {}
        for g in resp.get('contactGroups',[]) or []:
            rn = g.get('resourceName') or ''
            gid = rn.split('/',1)[-1] if rn else ''
            name = g.get('name') or ''
            if rn: mp[rn]=rn
            if gid: mp[gid]=rn
            if name:
                mp[name]=rn
                mp[name.lower()]=rn
        mp.setdefault('myContacts','contactGroups/myContacts')
        return mp
    mp = _groups_map(svc)
    rns = []
    for s in specs:
        s = s.strip()
        if s.startswith('contactGroups/'):
            rns.append(s)
        else:
            rn = mp.get(s) or mp.get(s.lower())
            if rn:
                rns.append(rn)
            else:
                print(json.dumps({"error": f"Unknown label/group: {s}"}))
                return 1
    members = []
    for rn in rns:
        grp = with_retries(lambda: svc.contactGroups().get(resourceName=rn, maxMembers=1000).execute())
        members.extend(grp.get('memberResourceNames', []) or [])
    emails = []
    for i in range(0, len(members), 200):
        chunk = members[i:i+200]
        resp = with_retries(lambda: svc.people().getBatchGet(resourceNames=chunk, personFields='emailAddresses').execute())
        for e in resp.get('responses', []) or []:
            person = e.get('person') or {}
            for ea in person.get('emailAddresses', []) or []:
                val = (ea.get('value') or '').strip()
                if val:
                    emails.append(val)
    # dedupe
    seen=set(); out=[]
    for em in emails:
        k=em.lower()
        if k not in seen:
            seen.add(k); out.append(em)
    print(json.dumps(out, indent=2))
    return 0


def cmd_groups_delete(args) -> int:
    load_agents_env(args.env)
    svc = people_service(creds_from_refresh())
    rn = _resolve_group_resource(svc, args.group)
    resp = with_retries(lambda: svc.contactGroups().delete(resourceName=rn).execute())
    print(json.dumps(resp, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Google Contacts (People API) Ops")
    p.add_argument("--env", help="Path to AGENTS.env (default ~/AGENTS.env)")

    sp = p.add_subparsers(dest="cmd", required=True)

    pa = sp.add_parser("auth", help="Run OAuth flow and print refresh token export line")
    pa.add_argument("--no-local-server", action="store_true", help="Use console flow (no local server)")
    pa.add_argument("--write-env", action="store_true", help="Append refresh token to env file")
    pa.set_defaults(func=cmd_auth)

    pl = sp.add_parser("list", help="List connections (people/me)")
    pl.add_argument("--fields", default="names,emailAddresses,phoneNumbers,organizations", help="personFields mask")
    pl.add_argument("--page-size", type=int, default=100)
    pl.set_defaults(func=cmd_list)

    ps = sp.add_parser("search", help="Search contacts by query")
    ps.add_argument("--query", required=True)
    ps.add_argument("--fields", default="names,emailAddresses,phoneNumbers,organizations", help="readMask for returned fields")
    ps.add_argument("--page-size", type=int, default=50)
    ps.set_defaults(func=cmd_search)

    pg = sp.add_parser("get", help="Get one contact by resource name")
    pg.add_argument("--resource", required=True)
    pg.add_argument("--fields", default="names,emailAddresses,phoneNumbers,organizations")
    pg.set_defaults(func=cmd_get)

    pc = sp.add_parser("create", help="Create a new contact")
    pc.add_argument("--given-name")
    pc.add_argument("--family-name")
    pc.add_argument("--full-name")
    pc.add_argument("--email")
    pc.add_argument("--phone")
    pc.add_argument("--org")
    pc.add_argument("--title")
    pc.add_argument("--json", help="Path to JSON person body (overrides flags)")
    pc.set_defaults(func=cmd_create)

    pu = sp.add_parser("update", help="Update an existing contact (auto-etag)")
    pu.add_argument("--resource", required=True)
    pu.add_argument("--given-name")
    pu.add_argument("--family-name")
    pu.add_argument("--full-name")
    pu.add_argument("--email")
    pu.add_argument("--phone")
    pu.add_argument("--org")
    pu.add_argument("--title")
    pu.add_argument("--json", help="Path to JSON person body")
    pu.add_argument("--update-fields", help="Comma-separated fields to update (e.g., names,emailAddresses)")
    pu.set_defaults(func=cmd_update)

    pd = sp.add_parser("delete", help="Delete a contact")
    pd.add_argument("--resource", required=True)
    pd.set_defaults(func=cmd_delete)

    pgl = sp.add_parser("groups", help="Manage contact groups")
    sgl = pgl.add_subparsers(dest="groups_cmd", required=True)
    pgl1 = sgl.add_parser("list", help="List groups")
    pgl1.add_argument("--page-size", type=int, default=200)
    pgl1.set_defaults(func=cmd_groups_list)
    pgls = sgl.add_parser("search", help="Search groups by name substring")
    pgls.add_argument("--q", required=True, help="Substring (case-insensitive)")
    def _search_groups(args):
        load_agents_env(args.env)
        svc = people_service(creds_from_refresh())
        resp = cmd_groups_list.__wrapped__(args) if hasattr(cmd_groups_list, '__wrapped__') else None
        # Fallback: list then filter
        lst = with_retries(lambda: svc.contactGroups().list(pageSize=1000).execute())
        q = args.q.lower()
        out = [g for g in lst.get('contactGroups',[]) if q in (g.get('name','').lower())]
        print(json.dumps(out, indent=2))
        return 0
    pgls.set_defaults(func=_search_groups)
    pgl2 = sgl.add_parser("create", help="Create a group")
    pgl2.add_argument("--name", required=True)
    pgl2.set_defaults(func=cmd_groups_create)
    pgl3 = sgl.add_parser("add", help="Add a contact to a group")
    pgl3.add_argument("--resource", required=True, help="Person resource (people/...) or ID")
    pgl3.add_argument("--group", required=True, help="Group resource/name/id (e.g., myContacts or contactGroups/XYZ)")
    pgl3.set_defaults(func=cmd_groups_add_member)
    pgl4 = sgl.add_parser("remove", help="Remove a contact from a group")
    pgl4.add_argument("--resource", required=True, help="Person resource (people/...) or ID")
    pgl4.add_argument("--group", required=True, help="Group resource/name/id")
    pgl4.set_defaults(func=cmd_groups_remove_member)
    pgl5 = sgl.add_parser("delete", help="Delete a contact group")
    pgl5.add_argument("--group", required=True, help="Group resource/name/id")
    pgl5.set_defaults(func=cmd_groups_delete)
    pgl6 = sgl.add_parser("emails", help="Resolve a contact label/group to email list")
    pgl6.add_argument("--group", action='append', required=True, help="Label/group name, ID, or resource; repeat or comma-separate")
    pgl6.set_defaults(func=cmd_groups_emails)

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
        notify_telegram(f"gcontacts {getattr(args,'cmd','?')} failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
