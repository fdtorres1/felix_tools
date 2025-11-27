#!/usr/bin/env bash
# linear.sh — tiny Linear GraphQL helper
#
# Usage (recommended):
#   source ~/.codex/tools/linear.sh   # defines li()
#   li '{"query":"query{ teams(first:5){ nodes { id key name } } }"}' | jq .
#
# Or run directly with a GraphQL JSON payload:
#   ~/.codex/tools/linear.sh '{"query":"query{ users(first:5){ nodes { id name } } }"}'

set -euo pipefail

__linear_load_env() {
  if [[ -z "${LINEAR_AGENT_TOKEN:-}" ]]; then
    local f
    for f in "./AGENTS.env" "$HOME/AGENTS.env"; do
      [[ -f "$f" ]] || continue
      while IFS= read -r raw; do
        [[ -z "$raw" || "$raw" == \#* ]] && continue
        raw="${raw#export }"
        case "$raw" in
          LINEAR_AGENT_TOKEN=*)
            local v="${raw#LINEAR_AGENT_TOKEN=}"
            v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
            export LINEAR_AGENT_TOKEN="$v"
            ;;
        esac
      done < "$f"
      [[ -n "${LINEAR_AGENT_TOKEN:-}" ]] && break
    done
  fi
}

li() {
  __linear_load_env
  if [[ -z "${LINEAR_AGENT_TOKEN:-}" ]]; then
    echo "LINEAR_AGENT_TOKEN not set; define it in ./AGENTS.env or ~/AGENTS.env" >&2
    return 1
  fi
  local payload="${1:-}"
  if [[ -z "$payload" ]]; then
    echo "Usage: li '<graphql-json>'" >&2
    return 2
  fi
  curl -sS https://api.linear.app/graphql \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${LINEAR_AGENT_TOKEN}" \
    --data "$payload"
}

# If invoked directly, pass through to li()
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  li "${1:-}"
fi

# --- Convenience helpers (source this file) ---

# Print teams as: KEY\tID\tNAME
li_teams() {
  li '{"query":"query{ teams(first:100){ nodes{ id key name } } }"}' \
    | jq -r '.data.teams.nodes[] | "\(.key)\t\(.id)\t\(.name)"'
}

# Resolve team id by key (echoes id)
li_team_id() {
  local key="${1:-}"
  [[ -n "$key" ]] || { echo "Usage: li_team_id <TEAM_KEY>" >&2; return 2; }
  li_teams | awk -v k="$key" -F '\t' '$1==k{print $2; found=1} END{if(!found) exit 1}'
}

# List first 200 labels; optional filter by team key via second arg
li_labels() {
  local team_key="${1:-}"
  li '{"query":"query{ issueLabels(first:200){ nodes{ id name color team{ id key name } } } }"}' \
    | if [[ -n "$team_key" ]]; then jq --arg k "$team_key" -r '.data.issueLabels.nodes[] | select((.team.key // "") == $k) | "\(.name)\t\(.id)\t\((.team.key // "-") )"'; else jq -r '.data.issueLabels.nodes[] | "\(.name)\t\(.id)\t\((.team.key // "-") )"'; fi
}

# Find user id by email substring or exact email; falls back to name contains
li_user_id() {
  local q="${1:-}"
  [[ -n "$q" ]] || { echo "Usage: li_user_id <email-or-name-fragment>" >&2; return 2; }
  li '{"query":"query{ users(first:200){ nodes{ id name email } } }"}' \
    | jq -r --arg q "$q" '
      .data.users.nodes
      | ( map(select((.email//"") == $q))
          + map(select((.email//"") | test($q; "i")))
          + map(select((.name//"") | test($q; "i"))) )[0] // empty
      | .id'
}

# Search issues by title substring; optional team key filter
li_issues_find() {
  local title_contains="" team_key="" team_id=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --title-contains) title_contains="$2"; shift 2;;
      --team) team_key="$2"; shift 2;;
      *) echo "Unknown arg: $1" >&2; return 2;;
    esac
  done
  [[ -n "$title_contains" ]] || { echo "Usage: li_issues_find --title-contains <text> [--team <TEAM_KEY>]" >&2; return 2; }
  if [[ -n "$team_key" ]]; then
    team_id=$(li_team_id "$team_key") || { echo "Team not found: $team_key" >&2; return 1; }
    local req resp
    req=$(jq -n --arg t "$title_contains" --arg id "$team_id" '{
      query: "query($t:String!,$id:ID!){ issues(first:50, filter:{ title:{ contains:$t }, team:{ id:{ eq:$id } } }){ nodes{ id identifier title url } } }",
      variables: { t: $t, id: $id }
    }')
    resp=$(li "$req")
    printf '%s' "$resp" | jq -r '(.data.issues.nodes // [])[] | "\(.identifier)\t\(.id)\t\(.title)\t\(.url)"'
  else
    local req resp
    req=$(jq -n --arg t "$title_contains" '{
      query: "query($t:String!){ issues(first:50, filter:{ title:{ contains:$t } }){ nodes{ id identifier title url } } }",
      variables: { t: $t }
    }')
    resp=$(li "$req")
    printf '%s' "$resp" | jq -r '(.data.issues.nodes // [])[] | "\(.identifier)\t\(.id)\t\(.title)\t\(.url)"'
  fi
}

# Create an issue (dry-run by default). Set LI_APPLY=1 to apply.
# Args: --team-id <ID> --title "Title" [--description "Text"] [--label-ids id1,id2] [--assignee-id <UID>]
li_issue_create() {
  local team_id="" title="" desc="" label_ids="" assignee_id="" apply="${LI_APPLY:-}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --team-id) team_id="$2"; shift 2;;
      --title) title="$2"; shift 2;;
      --description) desc="$2"; shift 2;;
      --label-ids) label_ids="$2"; shift 2;;
      --assignee-id) assignee_id="$2"; shift 2;;
      --apply) apply=1; shift;;
      *) echo "Unknown arg: $1" >&2; return 2;;
    esac
  done
  [[ -n "$team_id" && -n "$title" ]] || { echo "Usage: li_issue_create --team-id <ID> --title 'Title' [--description 'Text'] [--label-ids id1,id2] [--assignee-id UID] [--apply]" >&2; return 2; }
  local req
  req=$(jq -n \
    --arg teamId "$team_id" --arg title "$title" --arg desc "$desc" \
    --arg labels "$label_ids" --arg assignee "$assignee_id" '
    def csv_to_array($s): ( $s | split(",") | map(select(length>0)) );
    { query: "mutation($input:IssueCreateInput!){ issueCreate(input:$input){ success issue{ id identifier title url } } }",
      variables: { input: {
        teamId: $teamId,
        title: $title
      } } } 
    | if ($desc|length)>0 then (.variables.input.description=$desc) else . end
    | if ($labels|length)>0 then (.variables.input.labelIds=(csv_to_array($labels))) else . end
    | if ($assignee|length)>0 then (.variables.input.assigneeId=$assignee) else . end
  ')
  if [[ -n "$apply" ]]; then
    li "$req" | jq .
  else
    echo "DRY-RUN li_issue_create" >&2
    echo "$req"
  fi
}

# Update an issue by id (dry-run by default). Set LI_APPLY=1 or pass --apply.
# Args: --id <ISSUE_ID> [--title t] [--description d] [--add-label-ids a,b] [--remove-label-ids c,d] [--assignee-id uid]
li_issue_update() {
  local id="" title="" desc="" add_labels="" remove_labels="" assignee_id="" apply="${LI_APPLY:-}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id) id="$2"; shift 2;;
      --title) title="$2"; shift 2;;
      --description) desc="$2"; shift 2;;
      --add-label-ids) add_labels="$2"; shift 2;;
      --remove-label-ids) remove_labels="$2"; shift 2;;
      --assignee-id) assignee_id="$2"; shift 2;;
      --apply) apply=1; shift;;
      *) echo "Unknown arg: $1" >&2; return 2;;
    esac
  done
  [[ -n "$id" ]] || { echo "Usage: li_issue_update --id <ISSUE_ID> [--title t] [--description d] [--add-label-ids a,b] [--remove-label-ids c,d] [--assignee-id uid] [--apply]" >&2; return 2; }
  local req
  req=$(jq -n \
    --arg id "$id" --arg title "$title" --arg desc "$desc" \
    --arg add "$add_labels" --arg rm "$remove_labels" --arg assignee "$assignee_id" '
    def csv_to_array($s): ( $s | split(",") | map(select(length>0)) );
    { query: "mutation($id:String!,$input:IssueUpdateInput!){ issueUpdate(id:$id,input:$input){ success issue{ id identifier title url } } }",
      variables: { id: $id, input: {} } }
    | if ($title|length)>0 then (.variables.input.title=$title) else . end
    | if ($desc|length)>0 then (.variables.input.description=$desc) else . end
    | if ($add|length)>0 then (.variables.input.addedLabelIds=(csv_to_array($add))) else . end
    | if ($rm|length)>0 then (.variables.input.removedLabelIds=(csv_to_array($rm))) else . end
    | if ($assignee|length)>0 then (.variables.input.assigneeId=$assignee) else . end
  ')
  if [[ -n "$apply" ]]; then
    li "$req" | jq .
  else
    echo "DRY-RUN li_issue_update" >&2
    echo "$req"
  fi
}

# Add a comment to an issue (dry-run by default). Set LI_APPLY=1 or pass --apply.
# Args: --issue-id <ID> --body "Text"
li_comment_create() {
  local issue_id="" body="" apply="${LI_APPLY:-}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --issue-id) issue_id="$2"; shift 2;;
      --body) body="$2"; shift 2;;
      --apply) apply=1; shift;;
      *) echo "Unknown arg: $1" >&2; return 2;;
    esac
  done
  [[ -n "$issue_id" && -n "$body" ]] || { echo "Usage: li_comment_create --issue-id <ID> --body 'Text' [--apply]" >&2; return 2; }
  local req
  req=$(jq -n --arg issueId "$issue_id" --arg b "$body" '{
    query: "mutation($input:CommentCreateInput!){ commentCreate(input:$input){ success } }",
    variables: { input: { issueId: $issueId, body: $b } }
  }')
  if [[ -n "$apply" ]]; then
    li "$req" | jq .
  else
    echo "DRY-RUN li_comment_create" >&2
    echo "$req"
  fi
}
