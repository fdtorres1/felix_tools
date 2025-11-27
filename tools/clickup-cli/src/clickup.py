#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
import csv


BASE_URL = "https://api.clickup.com/api/v2"


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


def get_token() -> str:
    token = os.environ.get("CLICKUP_API_TOKEN") or os.environ.get("CLICKUP_TOKEN")
    if not token:
        raise SystemExit("Set CLICKUP_API_TOKEN (or CLICKUP_TOKEN) in ~/AGENTS.env")
    return token


def headers() -> Dict[str, str]:
    return {
        "Authorization": get_token(),
        "Content-Type": "application/json",
    }


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


def notify_macos(title: str, message: str) -> None:
    # best effort
    if os.system("command -v terminal-notifier >/dev/null 2>&1") == 0:
        try:
            os.system(f"terminal-notifier -title {json.dumps(title)} -message {json.dumps(message)} >/dev/null 2>&1")
        except Exception:
            pass


def iso_to_epoch_ms(val: Optional[str]) -> Optional[int]:
    if not val:
        return None
    s = val.strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        raise SystemExit("--due must be ISO8601, e.g., 2025-09-02T17:00:00-05:00 or 2025-09-02T22:00:00Z")


def http_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{BASE_URL}{path}"
    r = requests.get(url, headers=headers(), params=params, timeout=30)
    if not r.ok:
        notify_telegram(f"ClickUp GET {path} failed: {r.status_code} {r.text[:400]}")
        raise SystemExit(f"HTTP {r.status_code}: {r.text}")
    return r.json()


def http_post(path: str, body: Dict[str, Any]) -> Any:
    url = f"{BASE_URL}{path}"
    r = requests.post(url, headers=headers(), json=body, timeout=30)
    if not r.ok:
        notify_telegram(f"ClickUp POST {path} failed: {r.status_code} {r.text[:400]}")
        raise SystemExit(f"HTTP {r.status_code}: {r.text}")
    return r.json()


def http_put(path: str, body: Dict[str, Any]) -> Any:
    url = f"{BASE_URL}{path}"
    r = requests.put(url, headers=headers(), json=body, timeout=30)
    if not r.ok:
        notify_telegram(f"ClickUp PUT {path} failed: {r.status_code} {r.text[:400]}")
        raise SystemExit(f"HTTP {r.status_code}: {r.text}")
    return r.json()


def _expand_repeated(vals: Optional[List[str]]) -> Optional[List[str]]:
    if not vals:
        return None
    out: List[str] = []
    for v in vals:
        for t in str(v).split(','):
            t = t.strip()
            if t:
                out.append(t)
    return out


def map_priority_name(name: str) -> int:
    m = {
        'urgent': 1,
        'high': 2,
        'normal': 3,
        'medium': 3,
        'low': 4,
    }
    key = (name or '').strip().lower()
    if key in m:
        return m[key]
    raise SystemExit("Unknown priority name. Use one of: urgent, high, normal, low")


def list_status_names(list_id: str) -> List[str]:
    info = http_get(f"/list/{list_id}")
    out: List[str] = []
    for s in info.get('statuses', []) or []:
        nm = s.get('status') or s.get('name')
        if nm:
            out.append(nm)
    return out


def resolve_status_name(name: str, available: List[str]) -> str:
    if not name:
        return name
    if not available:
        return name
    wanted = name.strip().lower()
    for a in available:
        if (a or '').strip().lower() == wanted:
            return a
    # try substring
    matches = [a for a in available if wanted in (a or '').lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f"Status '{name}' not in list. Available: {', '.join(available)}")
    raise SystemExit(f"Ambiguous status '{name}'. Matches: {', '.join(matches)}")


def cmd_teams(args) -> int:
    load_agents_env(args.env)
    data = http_get("/team")
    print(json.dumps(data, indent=2))
    return 0


def cmd_spaces(args) -> int:
    load_agents_env(args.env)
    team = args.team or os.environ.get("CLICKUP_DEFAULT_TEAM_ID")
    if not team:
        raise SystemExit("--team or CLICKUP_DEFAULT_TEAM_ID required")
    data = http_get(f"/team/{team}/space", params={"archived": "false"})
    print(json.dumps(data, indent=2))
    return 0


def cmd_lists(args) -> int:
    load_agents_env(args.env)
    if args.space:
        data = http_get(f"/space/{args.space}/list", params={"archived": "false"})
    elif args.folder:
        data = http_get(f"/folder/{args.folder}/list", params={"archived": "false"})
    else:
        raise SystemExit("--space or --folder is required")
    print(json.dumps(data, indent=2))
    return 0


# --- Name-based resolution helpers ---
def fetch_spaces(team: str) -> List[Dict[str, Any]]:
    data = http_get(f"/team/{team}/space", params={"archived": "false"})
    return data.get("spaces", []) or []


def fetch_lists_in_space(space_id: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    # lists directly under space
    ls = http_get(f"/space/{space_id}/list", params={"archived": "false"})
    out.extend(ls.get("lists", []) or [])
    # lists under folders
    fs = http_get(f"/space/{space_id}/folder", params={"archived": "false"})
    for folder in fs.get("folders", []) or []:
        fl = http_get(f"/folder/{folder.get('id')}/list", params={"archived": "false"})
        out.extend(fl.get("lists", []) or [])
    return out


def resolve_list_id(team_spec: Optional[str], space_spec: Optional[str], list_spec: str) -> str:
    team = resolve_team_id(team_spec)
    # Load spaces: if team is known, use it; else search across all teams
    spaces = fetch_spaces(team) if team else sum((fetch_spaces(str(t.get('id'))) for t in fetch_teams()), [])
    # filter spaces by id or name if provided
    sel_spaces: List[Dict[str, Any]] = []
    if space_spec:
        # resolve space id if space_spec is a name
        space_id = space_spec
        if not any(s.get('id') == space_spec for s in spaces):
            space_id = resolve_space_id(team, space_spec)
        for s in spaces:
            if s.get('id') == space_id:
                sel_spaces.append(s)
        if not sel_spaces:
            raise SystemExit(f"No space matched: {space_spec}")
    else:
        sel_spaces = spaces
    # collect lists
    candidates: List[Dict[str, Any]] = []
    for sp in sel_spaces:
        for l in fetch_lists_in_space(sp.get('id')):
            # augment space name for display if present
            l.setdefault('space', {'id': sp.get('id'), 'name': sp.get('name')})
            candidates.append(l)
    # match by exact id or name substring
    ls_lower = (list_spec or '').lower()
    matches = [l for l in candidates if (l.get('id') == list_spec) or (ls_lower in (l.get('name', '').lower()))]
    if not matches:
        raise SystemExit(f"No list matched: {list_spec}")
    if len(matches) > 1:
        print(json.dumps([
            {"id": l.get('id'), "name": l.get('name'), "space": (l.get('space') or {}).get('name')}
            for l in matches
        ], indent=2))
        raise SystemExit("Ambiguous list name; please specify --space or use exact list id")
    return matches[0].get('id')


def cmd_tasks_search(args) -> int:
    load_agents_env(args.env)
    team = args.team or os.environ.get("CLICKUP_DEFAULT_TEAM_ID")
    if not team:
        raise SystemExit("--team or CLICKUP_DEFAULT_TEAM_ID required")
    page = args.page
    all_results: List[Dict[str, Any]] = []
    def build_params(page_num: int) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "archived": str(args.archived).lower(),
            "include_closed": str(args.include_closed).lower(),
            "order_by": args.order_by,
            "reverse": str(args.reverse).lower(),
            "limit": args.limit,
            "page": page_num,
            "query": args.query or None,
        }
        statuses = _expand_repeated(args.status) or []
        if args.status_name:
            # pass through as provided; ClickUp expects status names
            statuses += (_expand_repeated(args.status_name) or [])
        if statuses:
            params["statuses[]"] = statuses
        assignees = _expand_repeated(args.assignee)
        # Merge assignee IDs with names resolved to IDs
        if args.assignee_name:
            try:
                name_ids = resolve_user_ids(_expand_repeated(args.assignee_name) or [])
            except SystemExit as e:
                raise
            if name_ids:
                assignees = (assignees or []) + name_ids
        if assignees:
            params["assignees[]"] = assignees
        if args.tag:
            params["tags[]"] = _expand_repeated(args.tag)
        if args.due_after:
            params["due_date_gt"] = iso_to_epoch_ms(args.due_after)
        if args.due_before:
            params["due_date_lt"] = iso_to_epoch_ms(args.due_before)
        if args.created_after:
            params["date_created_gt"] = iso_to_epoch_ms(args.created_after)
        if args.created_before:
            params["date_created_lt"] = iso_to_epoch_ms(args.created_before)
        return params

    while True:
        resp = http_get(f"/team/{team}/task", params=build_params(page))
        tasks = resp.get("tasks", [])
        all_results.extend(tasks)
        if not args.all or len(tasks) < int(args.limit):
            break
        page += 1
    print(json.dumps({"tasks": all_results}, indent=2))
    return 0


def fetch_teams() -> List[Dict[str, Any]]:
    data = http_get("/team")
    return data.get("teams", []) or []


def resolve_team_id(team_spec: Optional[str]) -> Optional[str]:
    if team_spec is None:
        return os.environ.get("CLICKUP_DEFAULT_TEAM_ID")
    teams = fetch_teams()
    # exact id
    for t in teams:
        if str(t.get('id')) == str(team_spec):
            return str(t.get('id'))
    # exact name
    for t in teams:
        if (t.get('name') or '').lower() == team_spec.lower():
            return str(t.get('id'))
    # substring
    matches = [t for t in teams if team_spec.lower() in (t.get('name','').lower())]
    if len(matches) == 1:
        return str(matches[0].get('id'))
    if not matches:
        raise SystemExit(f"No team matched: {team_spec}")
    print(json.dumps([{"id": t.get('id'), "name": t.get('name')} for t in matches], indent=2))
    raise SystemExit("Ambiguous team; specify exact name or id")


def resolve_space_id(team_id: Optional[str], space_spec: str) -> str:
    teams = fetch_teams() if team_id is None else [{"id": team_id}]
    found = []
    for t in teams:
        spaces = fetch_spaces(str(t.get('id')))
        # exact id
        for s in spaces:
            if s.get('id') == space_spec:
                return s.get('id')
        for s in spaces:
            if (s.get('name') or '').lower() == space_spec.lower():
                found.append({"team": str(t.get('id')), **s})
        for s in spaces:
            if space_spec.lower() in (s.get('name','').lower()):
                found.append({"team": str(t.get('id')), **s})
    # dedupe by id (and prefer exact-name matches)
    if not found:
        raise SystemExit(f"No space matched: {space_spec}")
    # If any exact-name matches exist, restrict to those
    exact = [f for f in found if (f.get('name') or '').lower() == space_spec.lower()]
    pool = exact if exact else found
    seen = {}
    for f in pool:
        seen[f.get('id')] = f
    uniq = list(seen.values())
    if len(uniq) == 1:
        return uniq[0].get('id')
    print(json.dumps([{"team": f.get('team'), "id": f.get('id'), "name": f.get('name')} for f in uniq], indent=2))
    raise SystemExit("Ambiguous space; specify team or use exact id")


def resolve_user_ids(specs: List[str]) -> List[str]:
    teams = fetch_teams()
    # Build lookup maps
    by_id: Dict[str, Dict[str, Any]] = {}
    by_email: Dict[str, Dict[str, Any]] = {}
    by_name: Dict[str, Dict[str, Any]] = {}
    for t in teams:
        for m in (t.get('members') or []):
            u = m.get('user') or {}
            uid = str(u.get('id'))
            email = (u.get('email') or '').lower()
            name = (u.get('username') or '').lower()
            by_id[uid] = u
            if email:
                by_email[email] = u
            if name:
                by_name[name] = u
    resolved: List[str] = []
    for spec in specs:
        s = spec.strip()
        if not s:
            continue
        sl = s.lower()
        if s in by_id:
            resolved.append(s)
            continue
        if '@' in s and sl in by_email:
            resolved.append(str(by_email[sl].get('id')))
            continue
        if sl in by_name:
            resolved.append(str(by_name[sl].get('id')))
            continue
        # substring search on names and emails
        matches: List[Dict[str, Any]] = []
        for nm, u in by_name.items():
            if sl in nm:
                matches.append(u)
        for em, u in by_email.items():
            if sl in em and u not in matches:
                matches.append(u)
        if len(matches) == 1:
            resolved.append(str(matches[0].get('id')))
        elif len(matches) > 1:
            print(json.dumps([{"id": str(u.get('id')), "name": u.get('username'), "email": u.get('email')} for u in matches], indent=2))
            raise SystemExit(f"Ambiguous assignee: {s}")
        else:
            raise SystemExit(f"No user matched: {s}")
    # dedupe preserve order
    seen=set(); out=[]
    for r in resolved:
        if r not in seen:
            seen.add(r); out.append(r)
    return out


def cmd_tasks_list(args) -> int:
    load_agents_env(args.env)
    list_id = args.list or os.environ.get("CLICKUP_DEFAULT_LIST_ID")
    if (not list_id) and getattr(args, 'list_name', None):
        list_id = resolve_list_id(args.team, args.space, args.list_name)
    if not list_id:
        raise SystemExit("--list or CLICKUP_DEFAULT_LIST_ID required")
    resp = http_get(
        f"/list/{list_id}/task",
        params={
            "subtasks": str(args.subtasks).lower(),
            "include_closed": str(args.include_closed).lower(),
            "order_by": args.order_by,
            "reverse": str(args.reverse).lower(),
            "limit": args.limit,
        },
    )
    print(json.dumps(resp, indent=2))
    return 0


def cmd_task_get(args) -> int:
    load_agents_env(args.env)
    resp = http_get(f"/task/{args.id}", params={"include_subtasks": "true"})
    print(json.dumps(resp, indent=2))
    return 0


def build_task_body_from_args(args) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if getattr(args, "name", None) is not None:
        body["name"] = args.name
    if getattr(args, "description", None) is not None:
        body["description"] = args.description
    if getattr(args, "status", None) is not None:
        body["status"] = args.status
    if getattr(args, "priority", None) is not None:
        body["priority"] = int(args.priority)
    if getattr(args, "due", None) is not None:
        due_ms = iso_to_epoch_ms(args.due)
        if due_ms is not None:
            body["due_date"] = due_ms
    # assignees: accept IDs as comma list
    if getattr(args, "assignees", None):
        ids = [s.strip() for s in args.assignees.split(",") if s.strip()]
        body["assignees"] = ids
    # tags: ClickUp expects array of strings
    if getattr(args, "tags", None):
        body["tags"] = [s.strip() for s in args.tags.split(",") if s.strip()]
    return body


def cmd_task_create(args) -> int:
    load_agents_env(args.env)
    list_id = args.list or os.environ.get("CLICKUP_DEFAULT_LIST_ID")
    if (not list_id) and getattr(args, 'list_name', None):
        list_id = resolve_list_id(args.team, args.space, args.list_name)
    if not list_id:
        raise SystemExit("--list or CLICKUP_DEFAULT_LIST_ID required")
    body = build_task_body_from_args(args)
    # assignee resolution by name/email
    names = _expand_repeated(getattr(args, 'assignee_name', None))
    if names:
        ids = resolve_user_ids(names)
        if ids:
            existing = set(str(x) for x in body.get('assignees', []))
            body['assignees'] = list(existing.union(set(str(i) for i in ids)))
    # status by name (validate against list)
    if getattr(args, 'status_name', None):
        available = list_status_names(list_id)
        body['status'] = resolve_status_name(args.status_name, available)
    # priority by name
    if getattr(args, 'priority_name', None):
        body['priority'] = map_priority_name(args.priority_name)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "path": f"/list/{list_id}/task", "body": body}, indent=2))
        return 0
    resp = http_post(f"/list/{list_id}/task", body)
    print(json.dumps(resp, indent=2))
    notify_macos("ClickUp", f"Created task: {resp.get('id','?')}")
    return 0


def cmd_task_update(args) -> int:
    load_agents_env(args.env)
    body = build_task_body_from_args(args)
    names = _expand_repeated(getattr(args, 'assignee_name', None))
    if names:
        ids = resolve_user_ids(names)
        if ids:
            existing = set(str(x) for x in body.get('assignees', []))
            body['assignees'] = list(existing.union(set(str(i) for i in ids)))
    # status by name — resolve against the task's list when possible
    if getattr(args, 'status_name', None):
        try:
            t = http_get(f"/task/{args.id}")
            lst = (t.get('list') or {}).get('id')
        except Exception:
            lst = None
        if lst:
            available = list_status_names(lst)
            body['status'] = resolve_status_name(args.status_name, available)
        else:
            body['status'] = args.status_name
    # priority by name
    if getattr(args, 'priority_name', None):
        body['priority'] = map_priority_name(args.priority_name)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "path": f"/task/{args.id}", "body": body}, indent=2))
        return 0
    resp = http_put(f"/task/{args.id}", body)
    print(json.dumps(resp, indent=2))
    notify_macos("ClickUp", f"Updated task: {args.id}")
    return 0


def cmd_task_close(args) -> int:
    load_agents_env(args.env)
    status = args.status or "complete"
    body = {"status": status}
    if args.dry_run:
        print(json.dumps({"dry_run": True, "path": f"/task/{args.id}", "body": body}, indent=2))
        return 0
    resp = http_put(f"/task/{args.id}", body)
    print(json.dumps(resp, indent=2))
    notify_macos("ClickUp", f"Closed task: {args.id}")
    return 0


def cmd_tasks_bulk_create(args) -> int:
    load_agents_env(args.env)
    p = os.path.expanduser(args.file)
    if not os.path.exists(p):
        raise SystemExit("--file not found")
    txt = open(p, "r", encoding="utf-8").read()
    specs: List[Dict[str, Any]] = []
    try:
        data = json.loads(txt)
        if isinstance(data, list):
            specs = data
        else:
            raise ValueError
    except Exception:
        specs = []
        for line in txt.splitlines():
            line = line.strip()
            if not line:
                continue
            specs.append(json.loads(line))
    results = []
    for spec in specs:
        list_id = spec.get("list") or os.environ.get("CLICKUP_DEFAULT_LIST_ID")
        if not list_id:
            raise SystemExit("Each record needs 'list' or set CLICKUP_DEFAULT_LIST_ID")
        body = {}
        for k in ("name", "description", "status", "priority", "tags"):
            if k in spec:
                body[k] = spec[k]
        if spec.get("due"):
            body["due_date"] = iso_to_epoch_ms(spec["due"])
        if spec.get("assignees"):
            if isinstance(spec["assignees"], list):
                body["assignees"] = spec["assignees"]
            else:
                body["assignees"] = [s.strip() for s in str(spec["assignees"]).split(",") if s.strip()]
        if args.dry_run:
            results.append({"dry_run": True, "path": f"/list/{list_id}/task", "body": body})
        else:
            resp = http_post(f"/list/{list_id}/task", body)
            results.append({"id": resp.get("id"), "name": resp.get("name"), "list": list_id})
            time.sleep(0.2)
    print(json.dumps(results, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ClickUp Ops (Personal Token)")
    p.add_argument("--env", help="Path to AGENTS.env (default ~/AGENTS.env)")

    sp = p.add_subparsers(dest="cmd", required=True)

    pt = sp.add_parser("teams", help="List workspaces (teams)")
    pt.set_defaults(func=cmd_teams)

    ps = sp.add_parser("spaces", help="List spaces in a team")
    ps.add_argument("--team", help="Team (workspace) ID; else CLICKUP_DEFAULT_TEAM_ID")
    ps.set_defaults(func=cmd_spaces)

    pll = sp.add_parser("lists", help="List lists in a space or folder")
    pll.add_argument("--space", help="Space ID")
    pll.add_argument("--folder", help="Folder ID")
    pll.set_defaults(func=cmd_lists)

    pst = sp.add_parser("statuses", help="List statuses for a list")
    pst.add_argument("--list", help="List ID")
    pst.add_argument("--list-name", help="List name (use with --team/--space)")
    pst.add_argument("--team", help="Team ID or name for resolution")
    pst.add_argument("--space", help="Space ID or name for resolution")
    def _cmd_statuses(args):
        load_agents_env(args.env)
        lst = args.list
        if (not lst) and args.list_name:
            lst = resolve_list_id(args.team, args.space, args.list_name)
        if not lst:
            raise SystemExit("--list or --list-name required")
        print(json.dumps(list_status_names(lst), indent=2))
        return 0
    pst.set_defaults(func=_cmd_statuses)

    pu = sp.add_parser("users", help="List users (team members)")
    pu.add_argument("--team", help="Team ID or name; omit to list across all teams (deduped)")
    def _cmd_users(args):
        load_agents_env(args.env)
        team_id = resolve_team_id(args.team) if args.team else None
        teams = fetch_teams() if team_id is None else [t for t in fetch_teams() if str(t.get('id')) == str(team_id)]
        users = {}
        for t in teams:
            for m in (t.get('members') or []):
                u = m.get('user') or {}
                uid = str(u.get('id'))
                users[uid] = {"id": uid, "name": u.get('username'), "email": u.get('email')}
        print(json.dumps(sorted(users.values(), key=lambda x: (x.get('name') or '', x.get('email') or '')), indent=2))
        return 0
    pu.set_defaults(func=_cmd_users)

    pts = sp.add_parser("tasks", help="Task operations")
    sts = pts.add_subparsers(dest="tasks_cmd", required=True)

    psearch = sts.add_parser("search", help="Search tasks across a team")
    psearch.add_argument("--team", help="Team ID; else CLICKUP_DEFAULT_TEAM_ID")
    psearch.add_argument("--query", help="Free text query")
    psearch.add_argument("--include-closed", default="false")
    psearch.add_argument("--archived", default="false")
    psearch.add_argument("--order-by", default="created")
    psearch.add_argument("--reverse", default="true")
    psearch.add_argument("--limit", default="100")
    psearch.add_argument("--page", type=int, default=0)
    psearch.add_argument("--status", action='append', help="Filter by status (repeat or comma-separated)")
    psearch.add_argument("--status-name", action='append', help="Filter by status name (repeat or comma-separated)")
    psearch.add_argument("--assignee", action='append', help="Filter by ClickUp user ID (repeat or comma-separated)")
    psearch.add_argument("--assignee-name", action='append', help="Filter by user name/email (repeat or comma-separated)")
    psearch.add_argument("--tag", action='append', help="Filter by tag (repeat or comma-separated)")
    psearch.add_argument("--due-after", help="Due date >= (ISO8601)")
    psearch.add_argument("--due-before", help="Due date < (ISO8601)")
    psearch.add_argument("--created-after", help="Created >= (ISO8601)")
    psearch.add_argument("--created-before", help="Created < (ISO8601)")
    psearch.add_argument("--all", action="store_true", help="Fetch all pages")
    psearch.set_defaults(func=cmd_tasks_search)

    plist = sts.add_parser("list", help="List tasks in a list")
    plist.add_argument("--list", help="List ID; else CLICKUP_DEFAULT_LIST_ID")
    plist.add_argument("--list-name", help="List name substring (use with --team/--space)")
    plist.add_argument("--team", help="Team ID for name resolution")
    plist.add_argument("--space", help="Space ID or name for name resolution")
    plist.add_argument("--include-closed", default="false")
    plist.add_argument("--subtasks", default="true")
    plist.add_argument("--order-by", default="created")
    plist.add_argument("--reverse", default="true")
    plist.add_argument("--limit", default="100")
    plist.set_defaults(func=cmd_tasks_list)

    pexport = sts.add_parser("export", help="Export tasks (search) to JSONL")
    pexport.add_argument("--team", help="Team ID or name; else CLICKUP_DEFAULT_TEAM_ID")
    pexport.add_argument("--query", help="Free text query")
    pexport.add_argument("--include-closed", default="false")
    pexport.add_argument("--archived", default="false")
    pexport.add_argument("--order-by", default="created")
    pexport.add_argument("--reverse", default="true")
    pexport.add_argument("--limit", default="100")
    pexport.add_argument("--page", type=int, default=0)
    pexport.add_argument("--status", action='append', help="Filter by status (repeat or comma-separated)")
    pexport.add_argument("--status-name", action='append', help="Filter by status name (repeat or comma-separated)")
    pexport.add_argument("--assignee", action='append', help="Filter by ClickUp user ID (repeat or comma-separated)")
    pexport.add_argument("--assignee-name", action='append', help="Filter by user name/email (repeat or comma-separated)")
    pexport.add_argument("--tag", action='append', help="Filter by tag (repeat or comma-separated)")
    pexport.add_argument("--due-after", help="Due date >= (ISO8601)")
    pexport.add_argument("--due-before", help="Due date < (ISO8601)")
    pexport.add_argument("--created-after", help="Created >= (ISO8601)")
    pexport.add_argument("--created-before", help="Created < (ISO8601)")
    pexport.add_argument("--all", action="store_true", help="Fetch all pages")
    pexport.add_argument("--out", help="Output path (default stdout)")
    pexport.add_argument("--fields", help="Comma-separated top-level fields to include (e.g., id,name,status,due_date,assignees,tags,date_created,url)")
    # Export directly from a list
    pexport.add_argument("--list", help="List ID to export from")
    pexport.add_argument("--list-name", help="List name (use with --team/--space)")
    pexport.add_argument("--space", help="Space ID or name for list resolution")
    pexport.add_argument("--csv", help="Optional CSV output path instead of JSONL")
    def _cmd_tasks_export(args):
        load_agents_env(args.env)
        tasks: List[Dict[str, Any]] = []
        # If list specified, export from list; else use team search
        if args.list or args.list_name:
            lst = args.list
            if (not lst) and args.list_name:
                lst = resolve_list_id(args.team, args.space, args.list_name)
            if not lst:
                raise SystemExit("--list or --list-name required for list export")
            page = args.page
            while True:
                params = {
                    "include_closed": str(args.include_closed).lower(),
                    "subtasks": "true",
                    "order_by": args.order_by,
                    "reverse": str(args.reverse).lower(),
                    "limit": args.limit,
                    "page": page,
                }
                resp = http_get(f"/list/{lst}/task", params=params)
                batch = resp.get('tasks', []) if isinstance(resp, dict) else resp
                tasks.extend(batch)
                if not args.all or len(batch) < int(args.limit):
                    break
                page += 1
        else:
            team = resolve_team_id(args.team)
            if not team:
                raise SystemExit("--team or CLICKUP_DEFAULT_TEAM_ID required")
            page = args.page
            def build_params(page_num: int) -> Dict[str, Any]:
                params: Dict[str, Any] = {
                    "archived": str(args.archived).lower(),
                    "include_closed": str(args.include_closed).lower(),
                    "order_by": args.order_by,
                    "reverse": str(args.reverse).lower(),
                    "limit": args.limit,
                    "page": page_num,
                    "query": args.query or None,
                }
                statuses = _expand_repeated(args.status) or []
                if args.status_name:
                    statuses += (_expand_repeated(args.status_name) or [])
                if statuses:
                    params["statuses[]"] = statuses
                assignees = _expand_repeated(args.assignee)
                if args.assignee_name:
                    name_ids = resolve_user_ids(_expand_repeated(args.assignee_name) or [])
                    if name_ids:
                        assignees = (assignees or []) + name_ids
                if assignees:
                    params["assignees[]"] = assignees
                if args.tag:
                    params["tags[]"] = _expand_repeated(args.tag)
                if args.due_after:
                    params["due_date_gt"] = iso_to_epoch_ms(args.due_after)
                if args.due_before:
                    params["due_date_lt"] = iso_to_epoch_ms(args.due_before)
                if args.created_after:
                    params["date_created_gt"] = iso_to_epoch_ms(args.created_after)
                if args.created_before:
                    params["date_created_lt"] = iso_to_epoch_ms(args.created_before)
                return params
            while True:
                resp = http_get(f"/team/{team}/task", params=build_params(page))
                batch = resp.get('tasks', [])
                tasks.extend(batch)
                if not args.all or len(batch) < int(args.limit):
                    break
                page += 1
        # project fields if requested
        if args.fields:
            keep = [f.strip() for f in args.fields.split(',') if f.strip()]
            proj = []
            for t in tasks:
                proj.append({k: t.get(k) for k in keep})
            tasks = proj
        # write JSONL
        if args.csv:
            cols = [f.strip() for f in (args.fields or 'id,name,status,due_date').split(',') if f.strip()]
            outp = os.path.expanduser(args.csv)
            os.makedirs(os.path.dirname(outp) or '.', exist_ok=True)
            with open(outp, 'w', encoding='utf-8', newline='') as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                for t in tasks:
                    row = {k: t.get(k) for k in cols}
                    w.writerow(row)
            print(json.dumps({"ok": True, "count": len(tasks), "csv": outp}, indent=2))
        elif args.out:
            outp = os.path.expanduser(args.out)
            os.makedirs(os.path.dirname(outp) or '.', exist_ok=True)
            with open(outp, 'w', encoding='utf-8') as f:
                for t in tasks:
                    f.write(json.dumps(t, ensure_ascii=False) + '\n')
            print(json.dumps({"ok": True, "count": len(tasks), "out": outp}, indent=2))
        else:
            for t in tasks:
                sys.stdout.write(json.dumps(t, ensure_ascii=False) + '\n')
        return 0
    pexport.set_defaults(func=_cmd_tasks_export)

    # Cleanup test tasks (close by query)
    pcln = sts.add_parser("cleanup", help="Close test tasks by filters (non-destructive)")
    pcln.add_argument("--team", help="Team ID or name; else CLICKUP_DEFAULT_TEAM_ID")
    pcln.add_argument("--query", help="Free text filter for server-side search")
    pcln.add_argument("--name-contains", help="Client-side substring match on task name (case-insensitive)")
    pcln.add_argument("--limit", default="100")
    pcln.add_argument("--all", action='store_true', help="Fetch all pages")
    pcln.add_argument("--created-after", help="Created >= (ISO8601)")
    pcln.add_argument("--created-before", help="Created < (ISO8601)")
    pcln.add_argument("--due-after", help="Due >= (ISO8601)")
    pcln.add_argument("--due-before", help="Due < (ISO8601)")
    pcln.add_argument("--list", help="Restrict to a list ID")
    pcln.add_argument("--list-name", help="Restrict to a list name (use with --team/--space)")
    pcln.add_argument("--space", help="Space ID or name for list resolution")
    pcln.add_argument("--status-name", help="Status name to set (else heuristic complete)")
    pcln.add_argument("--only-status-name", action='append', help="Only close tasks currently in these statuses (repeat/comma)")
    pcln.add_argument("--exclude-status-name", action='append', help="Exclude tasks currently in these statuses (repeat/comma)")
    pcln.add_argument("--archive", action='store_true', help="Archive tasks instead of closing by status (best-effort)")
    pcln.add_argument("--confirm-threshold", type=int, default=10, help="Ask confirmation if more than N tasks matched")
    pcln.add_argument("--yes", action='store_true', help="Do not prompt for confirmation")
    pcln.add_argument("--dry-run", action='store_true')
    def _best_complete_status(list_id: Optional[str]) -> str:
        # heuristic: prefer 'complete', otherwise any that contains 'complete', 'done', or 'closed'
        if not list_id:
            return 'complete'
        try:
            names = list_status_names(list_id)
        except Exception:
            return 'complete'
        lowers = {n.lower(): n for n in names}
        if 'complete' in lowers:
            return lowers['complete']
        for key in ('complete','completed','done','closed','close'):
            for n in names:
                if key in (n or '').lower():
                    return n
        return names[-1] if names else 'complete'
    def _cmd_tasks_cleanup(args):
        load_agents_env(args.env)
        team = resolve_team_id(args.team)
        # Resolve list scope if provided
        list_scope = args.list
        if (not list_scope) and args.list_name:
            list_scope = resolve_list_id(team, args.space, args.list_name)
        page = 0
        closed = []
        preview = []
        def matches_filters(t: Dict[str, Any]) -> bool:
            nm = (t.get('name') or '')
            if args.name_contains and (args.name_contains.lower() not in nm.lower()):
                return False
            # current status filters
            st_obj = t.get('status')
            st = (st_obj.get('status') if isinstance(st_obj, dict) else st_obj) or ''
            st_l = st.lower()
            only = _expand_repeated(args.only_status_name) or []
            excl = _expand_repeated(args.exclude_status_name) or []
            if only:
                if st_l not in [x.lower() for x in only]:
                    return False
            if excl:
                if st_l in [x.lower() for x in excl]:
                    return False
            ca = t.get('date_created')
            if args.created_after:
                if not ca or int(ca) < (iso_to_epoch_ms(args.created_after) or 0):
                    return False
            if args.created_before:
                if not ca or int(ca) >= (iso_to_epoch_ms(args.created_before) or 0):
                    return False
            du = t.get('due_date')
            if args.due_after:
                if not du or int(du) < (iso_to_epoch_ms(args.due_after) or 0):
                    return False
            if args.due_before:
                if not du or int(du) >= (iso_to_epoch_ms(args.due_before) or 0):
                    return False
            return True

        # Helper to perform the action on a single task
        def _apply_action(t: Dict[str, Any]):
            tid = t.get('id')
            nm = t.get('name')
            lst = (t.get('list') or {}).get('id')
            target_status = args.status_name or _best_complete_status(lst)
            if args.dry_run:
                preview.append({'id': tid, 'name': nm, 'set_status': target_status, 'archive': bool(args.archive)})
            else:
                if args.archive:
                    # Try to archive; fallback to close by status
                    ok = False
                    try:
                        r = requests.put(f"{BASE_URL}/task/{tid}", headers=headers(), json={"archived": True}, timeout=30)
                        ok = r.ok
                    except Exception:
                        ok = False
                    if not ok:
                        http_put(f"/task/{tid}", {'status': target_status})
                else:
                    http_put(f"/task/{tid}", {'status': target_status})
                closed.append({'id': tid, 'name': nm, 'status': target_status, 'archived': bool(args.archive)})

        if list_scope:
            # iterate list tasks and filter client-side
            while True:
                resp = http_get(f"/list/{list_scope}/task", params={
                    'limit': args.limit, 'page': page, 'include_closed': 'false', 'subtasks': 'true', 'order_by': 'created', 'reverse': 'true'
                })
                tasks = resp.get('tasks', []) if isinstance(resp, dict) else resp
                for t in tasks:
                    if not matches_filters(t):
                        continue
                    _apply_action(t)
                if not args.all or len(tasks) < int(args.limit):
                    break
                page += 1
        else:
            # team-level search then client-side refine
            while True:
                resp = http_get(f"/team/{team}/task", params={
                    'limit': args.limit, 'page': page, 'include_closed': 'false', 'archived': 'false', 'query': args.query,
                    'order_by': 'created', 'reverse': 'true'
                })
                tasks = resp.get('tasks', [])
                candidates = [t for t in tasks if matches_filters(t)]
                # Confirm if exceeding threshold
                if (not args.dry_run) and candidates and (len(candidates) > args.confirm_threshold) and (not args.yes):
                    print(json.dumps({'count': len(candidates), 'threshold': args.confirm_threshold, 'note': 'Add --yes to proceed without prompt'}, indent=2))
                    try:
                        ans = input(f"Close {len(candidates)} tasks? [y/N]: ").strip().lower()
                    except EOFError:
                        ans = ''
                    if ans not in ('y','yes'):
                        print("Aborted.")
                        break
                for t in candidates:
                    _apply_action(t)
                if not args.all or len(tasks) < int(args.limit):
                    break
                page += 1
        print(json.dumps({'dry_run': bool(args.dry_run), 'closed': closed, 'preview': preview}, indent=2))
        return 0
    pcln.set_defaults(func=_cmd_tasks_cleanup)

    # Find tasks by name (preview) — JSONL output
    pfind = sts.add_parser("find", help="Find tasks by name substring for visual inspection")
    pfind.add_argument("--team", help="Team ID or name; else CLICKUP_DEFAULT_TEAM_ID")
    pfind.add_argument("--list", help="Restrict to a list ID")
    pfind.add_argument("--list-name", help="Restrict to a list name (use with --team/--space)")
    pfind.add_argument("--space", help="Space ID or name for list resolution")
    pfind.add_argument("--name-contains", required=True, help="Case-insensitive substring on task name")
    pfind.add_argument("--include-closed", default="false")
    pfind.add_argument("--limit", default="100")
    pfind.add_argument("--all", action='store_true')
    pfind.add_argument("--created-after", help="Created >= (ISO8601)")
    pfind.add_argument("--created-before", help="Created < (ISO8601)")
    pfind.add_argument("--due-after", help="Due >= (ISO8601)")
    pfind.add_argument("--due-before", help="Due < (ISO8601)")
    pfind.add_argument("--fields", help="Comma-separated fields to show (default id,name,status,due_date,url)")
    pfind.add_argument("--out", help="Output JSONL path (default stdout)")
    def _cmd_tasks_find(args):
        load_agents_env(args.env)
        # Build list scope if any
        list_scope = args.list
        team = resolve_team_id(args.team)
        if (not list_scope) and args.list_name:
            list_scope = resolve_list_id(team, args.space, args.list_name)
        # Helper matcher
        def match(t: Dict[str, Any]) -> bool:
            nm = (t.get('name') or '')
            if args.name_contains.lower() not in nm.lower():
                return False
            ca = t.get('date_created')
            if args.created_after and (not ca or int(ca) < (iso_to_epoch_ms(args.created_after) or 0)):
                return False
            if args.created_before and (not ca or int(ca) >= (iso_to_epoch_ms(args.created_before) or 0)):
                return False
            du = t.get('due_date')
            if args.due_after and (not du or int(du) < (iso_to_epoch_ms(args.due_after) or 0)):
                return False
            if args.due_before and (not du or int(du) >= (iso_to_epoch_ms(args.due_before) or 0)):
                return False
            return True
        # Collect
        tasks: List[Dict[str, Any]] = []
        page = 0
        if list_scope:
            while True:
                resp = http_get(f"/list/{list_scope}/task", params={
                    'limit': args.limit, 'page': page, 'include_closed': str(args.include_closed).lower(), 'subtasks': 'true', 'order_by': 'created', 'reverse': 'true'
                })
                batch = resp.get('tasks', []) if isinstance(resp, dict) else resp
                tasks.extend([t for t in batch if match(t)])
                if not args.all or len(batch) < int(args.limit):
                    break
                page += 1
        else:
            team_id = team
            if not team_id:
                raise SystemExit("--team or CLICKUP_DEFAULT_TEAM_ID required")
            while True:
                resp = http_get(f"/team/{team_id}/task", params={
                    'limit': args.limit, 'page': page, 'include_closed': str(args.include_closed).lower(), 'archived': 'false', 'query': args.name_contains,
                    'order_by': 'created', 'reverse': 'true'
                })
                batch = resp.get('tasks', [])
                tasks.extend([t for t in batch if match(t)])
                if not args.all or len(batch) < int(args.limit):
                    break
                page += 1
        # Project
        cols = [f.strip() for f in (args.fields or 'id,name,status,due_date,url').split(',') if f.strip()]
        def proj(t):
            row = {k: t.get(k) for k in cols if k != 'url'}
            if 'url' in cols:
                row['url'] = t.get('url') or f"https://app.clickup.com/t/{t.get('id')}"
            # flatten status object if needed
            if 'status' in row and isinstance(row['status'], dict):
                row['status'] = row['status'].get('status')
            return row
        out = [proj(t) for t in tasks]
        if args.out:
            outp = os.path.expanduser(args.out)
            os.makedirs(os.path.dirname(outp) or '.', exist_ok=True)
            with open(outp, 'w', encoding='utf-8') as f:
                for r in out:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
            print(json.dumps({'ok': True, 'count': len(out), 'out': outp}, indent=2))
        else:
            for r in out:
                sys.stdout.write(json.dumps(r, ensure_ascii=False) + '\n')
        return 0
    pfind.set_defaults(func=_cmd_tasks_find)

    pg = sp.add_parser("task", help="Single task operations")
    spt = pg.add_subparsers(dest="task_cmd", required=True)

    pget = spt.add_parser("get", help="Get a task")
    pget.add_argument("--id", required=True)
    pget.set_defaults(func=cmd_task_get)

    pcreate = spt.add_parser("create", help="Create a task in a list")
    pcreate.add_argument("--list", help="List ID; else CLICKUP_DEFAULT_LIST_ID")
    pcreate.add_argument("--list-name", help="List name substring (use with --team/--space for resolution)")
    pcreate.add_argument("--team", help="Team ID for name resolution")
    pcreate.add_argument("--space", help="Space ID or name for name resolution")
    pcreate.add_argument("--name", required=True)
    pcreate.add_argument("--description")
    pcreate.add_argument("--status")
    pcreate.add_argument("--status-name", help="Status by name (validated vs list)")
    pcreate.add_argument("--priority", type=int)
    pcreate.add_argument("--priority-name", help="Priority by name: urgent|high|normal|low")
    pcreate.add_argument("--due", help="ISO8601 due date/time")
    pcreate.add_argument("--assignees", help="Comma-separated ClickUp user IDs")
    pcreate.add_argument("--assignee-name", action='append', help="Assignee name/email (repeat or comma-separate)")
    pcreate.add_argument("--tags", help="Comma-separated tags")
    pcreate.add_argument("--dry-run", action="store_true")
    pcreate.set_defaults(func=cmd_task_create)

    pupd = spt.add_parser("update", help="Update fields on a task")
    pupd.add_argument("--id", required=True)
    pupd.add_argument("--name")
    pupd.add_argument("--description")
    pupd.add_argument("--status")
    pupd.add_argument("--status-name", help="Status by name (validated if possible)")
    pupd.add_argument("--priority", type=int)
    pupd.add_argument("--priority-name", help="Priority by name: urgent|high|normal|low")
    pupd.add_argument("--due", help="ISO8601 due date/time")
    pupd.add_argument("--assignees", help="Comma-separated ClickUp user IDs")
    pupd.add_argument("--assignee-name", action='append', help="Assignee name/email (repeat or comma-separate)")
    pupd.add_argument("--tags", help="Comma-separated tags")
    pupd.add_argument("--dry-run", action="store_true")
    pupd.set_defaults(func=cmd_task_update)

    pclose = spt.add_parser("close", help="Close a task (status → complete by default)")
    pclose.add_argument("--id", required=True)
    pclose.add_argument("--status", default="complete")
    pclose.add_argument("--dry-run", action="store_true")
    pclose.set_defaults(func=cmd_task_close)

    pbulk = sts.add_parser("bulk-create", help="Bulk create tasks from JSON/JSONL")
    pbulk.add_argument("--file", required=True)
    pbulk.add_argument("--dry-run", action="store_true")
    pbulk.set_defaults(func=cmd_tasks_bulk_create)

    pimp = sts.add_parser("import", help="Import tasks from JSON/JSONL (name-aware)")
    pimp.add_argument("--file", required=True)
    pimp.add_argument("--dry-run", action="store_true")
    def _cmd_tasks_import(args):
        load_agents_env(args.env)
        p = os.path.expanduser(args.file)
        if not os.path.exists(p):
            raise SystemExit("--file not found")
        txt = open(p, 'r', encoding='utf-8').read()
        try:
            data = json.loads(txt)
            specs = data if isinstance(data, list) else [data]
        except Exception:
            specs = [json.loads(line) for line in txt.splitlines() if line.strip()]
        results = []
        for spec in specs:
            # resolve list
            lst = spec.get('list')
            if not lst and spec.get('list_name'):
                lst = resolve_list_id(spec.get('team'), spec.get('space'), spec.get('list_name'))
            if not lst:
                lst = os.environ.get('CLICKUP_DEFAULT_LIST_ID')
            if not lst:
                raise SystemExit("Each record needs 'list' or 'list_name' (or set CLICKUP_DEFAULT_LIST_ID)")
            # build body
            body: Dict[str, Any] = {}
            for k in ('name','description','status','priority','tags'):
                if k in spec:
                    body[k] = spec[k]
            if 'status_name' in spec:
                body['status'] = resolve_status_name(spec['status_name'], list_status_names(lst))
            if 'priority_name' in spec:
                body['priority'] = map_priority_name(spec['priority_name'])
            if spec.get('due'):
                body['due_date'] = iso_to_epoch_ms(spec['due'])
            # assignees
            assignees = []
            if spec.get('assignees'):
                if isinstance(spec['assignees'], list):
                    assignees += [str(x) for x in spec['assignees']]
                else:
                    assignees += [s.strip() for s in str(spec['assignees']).split(',') if s.strip()]
            if spec.get('assignee_name'):
                names = spec['assignee_name']
                if not isinstance(names, list):
                    names = [n.strip() for n in str(names).split(',') if n.strip()]
                assignees += resolve_user_ids(names)
            if assignees:
                # de-dupe
                seen=set(); out=[]
                for a in assignees:
                    if a not in seen:
                        seen.add(a); out.append(a)
                body['assignees'] = out
            if args.dry_run:
                results.append({"dry_run": True, "path": f"/list/{lst}/task", "body": body})
            else:
                resp = http_post(f"/list/{lst}/task", body)
                results.append({"id": resp.get('id'), "name": resp.get('name'), "list": lst})
                time.sleep(0.2)
        print(json.dumps(results, indent=2))
        return 0
    pimp.set_defaults(func=_cmd_tasks_import)

    # Comments and tags
    pcmt = spt.add_parser("comment", help="Task comments")
    scmt = pcmt.add_subparsers(dest="comment_cmd", required=True)
    pcadd = scmt.add_parser("add", help="Add a comment to a task")
    pcadd.add_argument("--id", required=True, help="Task ID")
    pcadd.add_argument("--text", required=True, help="Comment text")
    pcadd.add_argument("--notify-all", action='store_true')
    def _cmd_comment_add(args):
        load_agents_env(args.env)
        body = {"comment_text": args.text, "notify_all": bool(args.notify_all)}
        if os.environ.get('DRY_RUN','').lower() == 'true':
            print(json.dumps({"dry_run": True, "path": f"/task/{args.id}/comment", "body": body}, indent=2))
            return 0
        resp = http_post(f"/task/{args.id}/comment", body)
        print(json.dumps(resp, indent=2))
        return 0
    pcadd.set_defaults(func=_cmd_comment_add)

    ptag = spt.add_parser("tag", help="Manage task tags")
    stag = ptag.add_subparsers(dest="tag_cmd", required=True)
    ptadd = stag.add_parser("add", help="Add a tag to a task")
    ptadd.add_argument("--id", required=True)
    ptadd.add_argument("--tag", required=True)
    def _cmd_tag_add(args):
        load_agents_env(args.env)
        if os.environ.get('DRY_RUN','').lower() == 'true':
            print(json.dumps({"dry_run": True, "path": f"/task/{args.id}/tag/{args.tag}"}, indent=2))
            return 0
        resp = http_post(f"/task/{args.id}/tag/{args.tag}", {})
        print(json.dumps(resp, indent=2))
        return 0
    ptadd.set_defaults(func=_cmd_tag_add)
    ptrem = stag.add_parser("remove", help="Remove a tag from a task")
    ptrem.add_argument("--id", required=True)
    ptrem.add_argument("--tag", required=True)
    def _cmd_tag_remove(args):
        load_agents_env(args.env)
        url = f"{BASE_URL}/task/{args.id}/tag/{args.tag}"
        if os.environ.get('DRY_RUN','').lower() == 'true':
            print(json.dumps({"dry_run": True, "path": f"/task/{args.id}/tag/{args.tag}", "method": "DELETE"}, indent=2))
            return 0
        r = requests.delete(url, headers=headers(), timeout=30)
        if not r.ok:
            notify_telegram(f"ClickUp DELETE /task/{{id}}/tag/{{tag}} failed: {r.status_code} {r.text[:400]}")
            raise SystemExit(f"HTTP {r.status_code}: {r.text}")
        print(json.dumps({"ok": True}, indent=2))
        return 0
    ptrem.set_defaults(func=_cmd_tag_remove)

    # Custom fields (read-only + dry-run set)
    pf = spt.add_parser("fields", help="Show a task's custom fields")
    pf.add_argument("--id", required=True)
    def _cmd_fields(args):
        load_agents_env(args.env)
        t = http_get(f"/task/{args.id}")
        print(json.dumps(t.get('custom_fields', []), indent=2))
        return 0
    pf.set_defaults(func=_cmd_fields)

    pfs = spt.add_parser("field", help="Set a custom field (dry-run)")
    sfs = pfs.add_subparsers(dest="field_cmd", required=True)
    pset = sfs.add_parser("set", help="Set a custom field value (dry-run)")
    pset.add_argument("--task", required=True)
    pset.add_argument("--field-id", required=True)
    pset.add_argument("--list", help="List ID (required by API for some field updates)")
    pset.add_argument("--value", required=True, help="Raw value (string/number/JSON)")
    def _cmd_field_set(args):
        load_agents_env(args.env)
        # Show both common API shapes; leave execution to a later step
        body = {"value": args.value}
        preview = {
            "dry_run": True,
            "options": [
                {"method": "POST", "path": f"/list/{args.list or 'LIST_ID'}/field/{args.field_id}/task/{args.task}", "body": body},
                {"method": "PUT", "path": f"/task/{args.task}/field/{args.field_id}", "body": body},
            ]
        }
        print(json.dumps(preview, indent=2))
        return 0
    pset.set_defaults(func=_cmd_field_set)

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
        notify_telegram(f"clickup {getattr(args,'cmd','?')} failed: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
