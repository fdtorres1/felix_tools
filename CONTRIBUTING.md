# Contributing to Felix Tools

This guide covers how to contribute to tools in this monorepo.

## Before You Start

1. **Read [AGENTS.md](AGENTS.md)** – It defines how all work is organized.
2. **Create an issue first** – All work begins with an issue.
3. **Work in a branch** – Never commit directly to `main`.

## Workflow Summary

### For New Tools

1. Create an issue: `Create tool: <tool-name>`
2. Create a branch: `git checkout -b tool/<tool-name>/initial`
3. Bootstrap the folder structure (see below)
4. Implement with tests
5. Update documentation
6. Open a PR and link the issue
7. Squash merge after approval

### For Changes to Existing Tools

1. Create an issue describing the change
2. Create a branch: `git checkout -b tool/<tool-name>/<short-slug>`
3. Implement changes and update tests
4. Update documentation and changelog
5. Open a PR and link the issue
6. Squash merge after approval

## Tool Folder Structure

Every tool must have:

```
tools/<tool-name>/
├── README.md        # What it does, quickstart, examples
├── CHANGELOG.md     # Version history
├── CONFIG.md        # Environment variables and config
├── DESIGN.md        # Architecture and design decisions
├── .env.example     # Example environment file
├── src/             # Source code
├── tests/           # Automated tests
├── docs/            # Additional documentation
└── scripts/         # CLI entrypoints, wrappers
```

## Documentation Standards

### README.md

- One-paragraph summary
- Use cases
- Quickstart with install + run commands
- At least one realistic example

### CONFIG.md

- List all environment variables
- Mark required vs optional
- Document external dependencies

### CHANGELOG.md

- Use [SemVer](https://semver.org/)
- Document every released change
- Include date with each version

### DESIGN.md

- Problem statement
- High-level architecture
- Key decisions and trade-offs

## Code Standards

### Python

- Use type hints
- Follow PEP 8
- Include docstrings for public functions
- Use `argparse` for CLI interfaces

### Bash/Shell

- Use `set -euo pipefail`
- Quote variables
- Provide usage help

### Swift

- Follow Swift API design guidelines
- Handle errors gracefully
- Support macOS 12+

## Environment Variables

- Never commit real secrets
- Use `~/AGENTS.env` as the standard location
- Tools auto-load from `~/AGENTS.env`
- Provide `.env.example` with placeholder values

## Testing

- Run tests before opening a PR
- Add tests for new functionality
- Use dry-run modes where applicable

## Pull Request Checklist

- [ ] Linked issue in PR description
- [ ] Tool docs updated (README, CONFIG, DESIGN)
- [ ] CHANGELOG.md updated with version
- [ ] Tests added or updated
- [ ] Manual smoke test performed
- [ ] No secrets in code or docs

## Questions?

Check [AGENTS.md](AGENTS.md) for detailed guidance on workflows, branching, and documentation expectations.

