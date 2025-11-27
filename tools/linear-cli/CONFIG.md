# Config – linear-cli

## Environment Variables

### Required

- `LINEAR_AGENT_TOKEN`  
  OAuth token from Linear (format: `lin_oauth_...`).  
  Used as Bearer token in API requests.

## Configuration File

Environment variables are loaded from `~/AGENTS.env` or `./AGENTS.env`.

## Example ~/AGENTS.env

```bash
LINEAR_AGENT_TOKEN=lin_oauth_abc123def456...
```

## Getting a Token

1. Go to Linear Settings → API → Personal API keys
2. Create a new key
3. Copy to `~/AGENTS.env`

## External Dependencies

- **Linear GraphQL API**: `https://api.linear.app/graphql`
- **curl**: For HTTP requests
- **jq**: For JSON parsing

