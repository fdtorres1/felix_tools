# AGENTS.md

This document defines how **all work** in this monorepo is organized and how **Cursor (and humans using Cursor)** should operate on it.

The goal: every tool is predictable to find, consistent to work on, fully documented, and safe to change.

---

## 1. Scope and principles

- **Monorepo for all tools**  
  This repository contains *all* tools (scripts, CLIs, integrations, migrations, etc.), regardless of area or domain.

- **One folder per tool**  
  Every tool lives in its own top-level folder under `tools/`.

- **Issue-first workflow**  
  All work begins with an issue. No feature or fix without a corresponding issue.

- **Branch-per-task**  
  Tools are created and modified only in dedicated branches. No direct commits to `main`.

- **PRs + squash merge only**  
  All changes go through pull requests and are merged via squash, never fast-forwarded directly.

- **Documentation and changelogs are mandatory**  
  Each tool must have clear documentation and its own changelog. Documentation is kept in sync with code.

- **Cursor is an assistant, not an authority**  
  Cursor can scaffold, refactor, and generate code/docs, but humans own decisions and reviews.

---

## 2. Repository layout

### 2.1 Root-level structure

The repository should follow this structure:

```text
.
AGENTS.md                 # This file – how agents (and humans) should work.
README.md                 # High-level overview of the monorepo.
CONTRIBUTING.md           # General contribution guidelines (referenced by this doc).
docs/
  architecture.md         # High-level architecture and conventions.
  tools-overview.md       # Catalog of all tools with short descriptions.
tools/
  <tool-name-1>/
  <tool-name-2>/
  ...
scripts/                  # Optional: shared helper scripts (bootstrap, lint, etc.).
```

### 2.2 Per-tool folder structure

Each tool lives at `tools/<tool-name>/` and follows this pattern:

```text
tools/<tool-name>/
  README.md               # What the tool does and how to use it.
  CHANGELOG.md            # History of changes for this tool.
  CONFIG.md               # Configuration & environment variables.
  DESIGN.md               # (Required for non-trivial tools) Design and rationale.
  .env.example            # Example env file; never contains real secrets.
  src/                    # Source code.
  tests/                  # Automated tests for the tool.
  docs/                   # Additional docs (API mappings, diagrams, examples).
  scripts/                # Entrypoints, CLI wrappers, migrations.
```

**Naming rule:**  
`tool-name` should be descriptive, lowercase, words separated by hyphens, e.g.:
- `givebutter-import`
- `donor-sync-salesforce`
- `data-export-finance-reports`

---

## 3. Branching and naming conventions

### 3.1 Default branches

- **`main`**  
  Always deployable / stable.  
  Only updated via squash merges from pull requests.

- **Feature branches**  
  Created from `main`.  
  Used for creating or modifying tools.

### 3.2 Branch naming

Use the following patterns:

- **New tool creation:**
  ```
  tool/<tool-name>/initial
  ```
  e.g. `tool/givebutter-import/initial`

- **Feature or improvement on existing tool:**
  ```
  tool/<tool-name>/<short-slug>
  ```
  e.g. `tool/givebutter-import/add-refunds-support`

- **Bug fix:**
  ```
  bugfix/<tool-name>/<issue-id-or-slug>
  ```
  e.g. `bugfix/givebutter-import/fix-date-parsing`

Branch names should reference the tool and ideally the issue ID in the PR title/description, even if not in the branch name itself.

---

## 4. Issue lifecycle

All work must have an associated issue in the chosen issue tracker (e.g., GitHub Issues).

### 4.1 Creating an issue

Every new tool or change must have an issue that includes:

- **Title:** Concise but descriptive
  - `Create tool: givebutter-import for historical donations`

- **Type/labels:**
  - `type:tool`, `type:feature`, `type:bug`, `tool:<tool-name>`, etc.

- **Summary:**
  - One or two paragraphs describing the problem and desired outcome.

- **Inputs & outputs:**
  - **Inputs:** where data comes from (e.g., CSV, API).
  - **Outputs:** what it creates (e.g., transactions in Givebutter).

- **Acceptance criteria:**
  - Clear, testable conditions like:
    - "Given a valid CSV row, the tool creates exactly one transaction in Givebutter."
    - "Errors are logged with row identifiers."

- **Risks / constraints:**
  - Rate limits, idempotency requirements, data sensitivity, etc.

### 4.2 Linking issues and branches

Reference the issue number in:
- Branch description (optional).
- PR title or body (required).

**Example PR title:**
```
Create givebutter-import tool for historical donations (Issue #42)
```

---

## 5. Workflow for a new tool

This is the canonical flow Cursor and humans should follow for creating a new tool in the monorepo.

### Step 1 – Create an issue

Create an issue with:
- **Title:** `Create tool: <tool-name>`
- Full description, inputs/outputs, and acceptance criteria.
- Assign an owner and (optionally) due date.

### Step 2 – Create a branch from main

From local machine:

```bash
git checkout main
git pull origin main
git checkout -b tool/<tool-name>/initial
```

### Step 3 – Bootstrap the tool folder

Under `tools/`, create the folder and skeleton:

```text
tools/<tool-name>/
  README.md
  CHANGELOG.md
  CONFIG.md
  DESIGN.md
  .env.example
  src/
  tests/
  docs/
  scripts/
```

**Minimum content:**

- **README.md:**
  - One-paragraph overview of what the tool does.
  - Quickstart commands (to be filled out as implementation proceeds).

- **CHANGELOG.md:**
  - Start with a template:

```md
# Changelog – <tool-name>

All notable changes to this tool are documented in this file.

## [Unreleased]

- Initial scaffold created (no functional behavior yet).
```

- **CONFIG.md:**
  - List expected environment variables (even if values unknown yet).
  - Example:

```md
# Config – <tool-name>

## Environment variables

- `GIVEBUTTER_API_KEY` (required): API key for Givebutter.
- `GIVEBUTTER_CAMPAIGN_ID` (required): ID of the target campaign for imports.
```

- **.env.example:**
  - Keys only, no secrets:

```bash
# tools/<tool-name>/.env.example
GIVEBUTTER_API_KEY=your-api-key-here
GIVEBUTTER_CAMPAIGN_ID=your-campaign-id-here
```

- **DESIGN.md:**
  - At minimum: problem statement, high-level approach, and planned architecture.
  - For complex tools, include sequence diagrams or pseudo-code.

### Step 4 – Implement the tool (with Cursor)

1. Open the repo root in Cursor.

2. In Cursor, open:
   - The issue description.
   - `tools/<tool-name>/README.md`
   - `tools/<tool-name>/DESIGN.md`

3. Ask Cursor to:
   - Generate a detailed implementation plan based on the issue and design.
   - Scaffold initial code in `src/` and basic tests in `tests/`.

4. Implement in small steps:
   - After each major change:
     - Run tests.
     - Update `README.md` usage section.
     - Update `CONFIG.md` if new env vars are introduced.

5. Ensure all external API interactions:
   - Use configuration from `.env` (loaded via a config module).
   - Are encapsulated in dedicated client modules (e.g., `src/givebutterClient.*`).

6. Use Cursor to:
   - Refactor repetitive logic.
   - Suggest edge cases and validations.
   - Generate test cases from acceptance criteria.

### Step 5 – Update documentation and changelog

Before opening a PR:

- **README.md:**
  - Finalize **Quickstart:**
    - How to install dependencies.
    - How to run the tool (commands).
    - Example usage (with realistic but fake data).

- **CONFIG.md:**
  - Confirm all required/optional settings are documented.

- **DESIGN.md:**
  - Update to reflect the actual implementation (note any deviations from original plan).

- **CHANGELOG.md:**
  - Replace the "Unreleased" placeholder line with a version entry, e.g.:

```md
## [0.1.0] – 2025-11-27

- Initial version of `<tool-name>` with:
  - CSV parsing for legacy donations.
  - Creation of transactions in Givebutter via API.
  - Basic error logging and dry-run mode.
```

For versioning, use SemVer per tool (MAJOR.MINOR.PATCH), incrementing as you make breaking or non-breaking changes.

---

## 6. Workflow for changes to existing tools

For any change (bug fix, feature, refactor):

1. **Create an issue** describing:
   - What's wrong or what needs to be added.
   - Expected behavior and acceptance criteria.

2. **Create a branch from main:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b tool/<tool-name>/<short-slug>
   ```

3. **Review existing docs** for that tool:
   - `README.md`, `CONFIG.md`, `DESIGN.md`.

4. **Implement the change:**
   - Update code in `src/`.
   - Add/modify tests in `tests/`.

5. **Update documentation:**
   - Adjust `README.md` and `CONFIG.md` to reflect new behavior/config.
   - Update `DESIGN.md` if architecture changed.

6. **Update CHANGELOG.md:**
   - Add a new entry with updated version.
   - Example entry:

```md
## [0.2.0] – 2025-12-05

- Added support for importing refunded donations.
- Improved error logging for network timeouts.
```

---

## 7. Pull requests and squash merges

### 7.1 Opening a PR

When the branch is ready:

```bash
git status          # Ensure clean
git add ...
git commit -m "Short, descriptive message"
git push -u origin <branch-name>
```

Then open a PR against `main`:

- **Title:**
  - Include the tool name and issue number.
  - Example: `Add historical donations import tool (Issue #42)`

- **Description:**
  - Summary of what changed.
  - Link to the issue.
  - Implementation notes (including any design deviations).
  - Testing performed (commands, environments).
  - Screenshots or logs for significant behavior, when helpful.

- **Checklist** (should be in PR template):
  - [ ] Linked issue.
  - [ ] Tool docs updated (`README.md`, `CONFIG.md`, `DESIGN.md`).
  - [ ] `CHANGELOG.md` updated with new version.
  - [ ] Tests added or updated.
  - [ ] Manual smoke test performed (describe).

### 7.2 Review process

- **Self-review first:**
  - Skim the diff in the PR.
  - Use Cursor to generate a summary of changes to catch anything missed.

- **Peer review (human):**
  - Reviewer checks:
    - Code correctness and clarity.
    - Tests and documentation coverage.
    - Compatibility with existing tools and repo standards.

- **Cursor assistance:**
  - It's fine to ask Cursor to:
    - Suggest improvements.
    - Explain complex sections.
    - Generate test cases.
  - But a human must make the final decision on correctness.

### 7.3 Squash merge

Once approved:
- Use squash merge into `main`.
- The squash commit message should:
  - Summarize the change.
  - Reference the issue.

**Example squash commit message:**
```
feat(givebutter-import): Add initial historical donation import (Issue #42)
```

After merge:
- Delete the feature branch (locally and remotely).
- Ensure `main` is up to date locally.

---

## 8. Documentation expectations

### 8.1 Required docs per tool

Each tool must maintain:

- **README.md:**
  - **Summary:** what the tool does, in one paragraph.
  - **Use cases:** when to use it and when not to.
  - **Quickstart:**
    - Install dependencies.
    - Run commands.
  - **Examples:**
    - At least one realistic example execution.

- **CONFIG.md:**
  - Environment variables.
  - External dependencies (APIs, databases, services).
  - Any required credentials or permissions (described, not actual secrets).

- **CHANGELOG.md:**
  - SemVer-style entries for every released change affecting behavior.

- **DESIGN.md** (for non-trivial tools):
  - Problem statement.
  - High-level architecture.
  - Key decisions and trade-offs.
  - Data flows and external API mappings.

- **.env.example:**
  - All required environment keys with fake/sample values.

### 8.2 Shared docs at the repo level

- **docs/tools-overview.md:**
  - Table listing:
    - Tool name.
    - Path.
    - Brief description.
    - Owner / contact.

- **docs/architecture.md:**
  - How tools are grouped.
  - Shared patterns (config loading, logging, error handling).
  - Conventions for languages, frameworks, and testing.

---

## 9. Cursor-specific guidance

When using Cursor with this monorepo:

1. **Always work at the repo root.**
   - Open the monorepo root folder so Cursor sees the full context (`AGENTS`, tool structure, docs).

2. **Feed Cursor the right context:**
   - When starting work on a tool, open:
     - The issue.
     - `tools/<tool-name>/README.md`
     - `tools/<tool-name>/CONFIG.md`
     - `tools/<tool-name>/DESIGN.md`
   - Then instruct Cursor explicitly which tool you're working on.

3. **Prefer small, incremental changes:**
   - Ask Cursor for a plan first.
   - Implement one step at a time (e.g., "add config loader", then "implement API client", then "hook up CLI").

4. **Keep docs in sync as part of the change:**
   - When code changes, prompt Cursor to update the relevant docs and changelog in the same branch.

5. **Never store secrets in code or docs:**
   - Cursor can help generate `.env.example` files, but must never be instructed to include real secrets.

---

## 10. Quick checklists

### 10.1 New tool checklist

- [ ] Issue created with clear acceptance criteria.
- [ ] Branch created from `main`: `tool/<tool-name>/initial`.
- [ ] `tools/<tool-name>/` folder created with:
  - [ ] `README.md`
  - [ ] `CHANGELOG.md`
  - [ ] `CONFIG.md`
  - [ ] `DESIGN.md`
  - [ ] `.env.example`
  - [ ] `src/`, `tests/`, `docs/`, `scripts/`
- [ ] Implementation done with tests.
- [ ] Docs (`README.md`, `CONFIG.md`, `DESIGN.md`) updated.
- [ ] `CHANGELOG.md` updated with version.
- [ ] PR opened and linked to issue.
- [ ] Squash merge into `main` after approval.

### 10.2 Existing tool change checklist

- [ ] Issue created and linked to tool.
- [ ] Branch created from `main`: `tool/<tool-name>/<slug>`.
- [ ] Code changes implemented in `src/`.
- [ ] Tests added/updated in `tests/`.
- [ ] `README.md`, `CONFIG.md`, `DESIGN.md` updated as needed.
- [ ] `CHANGELOG.md` version bumped with notes.
- [ ] PR opened, reviewed, and squash merged into `main`.

