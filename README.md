# AI Directories

An AI-agent-powered pipeline to submit your product/startup to **100+ directories** — AI tool listings, startup databases, SaaS aggregators, and general web directories.

Built to work with **AI coding agents** (Claude Code, Cursor, Gemini, Windsurf, etc.) as an interactive submission assistant. The agent collects your product info, generates copy variations, discovers submission forms, auto-submits where possible, and guides you through manual submissions via browser automation.

## What It Does

1. **Database of 100+ directories** — Pre-catalogued with auth type, captcha detection, pricing signals, and site status
2. **Automated analysis pipeline** — HTTP-level scanning, browser verification, form field discovery
3. **30 unique copy variations** — Generated per product to avoid duplicate content across directories
4. **Auto-submission engine** — Heuristic field matching fills and submits forms across hundreds of sites
5. **Manual browser assistance** — Playwright MCP integration for captcha solving, Google login, complex forms
6. **GitHub PR submissions** — Automated fork + PR creation for awesome-lists and curated repos
7. **Progress tracking** — `checkpoint.md` tracks every submission with status and confirmation

## Quick Start

### Prerequisites

- Python 3.10+
- An AI coding agent (see [Supported Agents](#supported-agents))
- `gh` CLI (for GitHub PR submissions) — [Install](https://cli.github.com/)

### Setup

```bash
# Clone the repo
git clone https://github.com/man0l/ai-directories.git
cd ai-directories

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### Prepare Your Assets

Place these files in the project root:
- `logo.png` — Your product logo (used for directory uploads)
- `site-image.png` — A screenshot of your product (used for directory uploads)

### Start the Agent

Open the project in your AI IDE and tell the agent:

> "I want to submit my product to AI directories"

The agent will walk you through the process interactively. See the agent-specific instructions below.

## Supported Agents

### Cursor / Windsurf / Other AI IDEs

The agent reads `AGENTS.md` for instructions. It requires the **Playwright MCP server** for browser-based submissions.

**Cursor setup:**
1. Open the project in Cursor
2. Ensure the Playwright MCP server is configured (for browser submissions)
3. The agent will read `AGENTS.md` and `.cursor/skills/add-directories/SKILL.md` automatically
4. Start a conversation: "I want to submit my product to directories"

**Playwright MCP for Cursor:**

Add to your Cursor MCP settings (`.cursor/mcp.json` or IDE settings):

```json
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest"
      ]
    }
  }
```

### Claude Code / Claude Cowork

The agent reads `CLAUDE.md` for instructions.

**Claude Code setup:**
1. Open the project directory in Claude Code
2. Claude reads `CLAUDE.md` automatically for project context
3. Start: "I want to submit my product to directories"
4. For browser-based submissions, Claude Code uses shell commands with Playwright

**Claude Cowork setup:**
1. Open the project in Claude Cowork
2. Ensure Playwright MCP is available in the environment
3. The browser tools (`browser_navigate`, `browser_snapshot`, etc.) are used for manual submissions

### Gemini (Google AI Studio / IDX)

The agent reads `GEMINI.md` for instructions.

1. Open the project in your Gemini-powered IDE
2. Gemini reads `GEMINI.md` for project context
3. Start: "I want to submit my product to directories"

## How It Works

### The Pipeline

```
[1] Collect Product Info    →  User provides URL, name, description, credentials
         ↓
[2] Generate 30 Copies     →  Unique title/description pairs for SEO diversity
         ↓
[3] Analyze Directories     →  HTTP scan: auth type, captcha, pricing, dead domains
         ↓
[4] Browser Verify          →  Playwright confirms active sites, detects JS-rendered forms
         ↓
[5] Discover Forms          →  Playwright extracts form fields (name, type, label)
         ↓
[6] Auto-Submit             →  Heuristic field matching fills + submits forms
         ↓
[7] Manual Submit           →  Agent guides you through captcha/OAuth/complex forms
         ↓
[8] GitHub PRs              →  Fork + PR to awesome-lists and curated repos
         ↓
[9] Track Progress          →  checkpoint.md updated after each phase
```

### Directory Database

`directories.json` contains 100+ directories, each with:

```json
{
  "name": "FutureTools",
  "url": "https://www.futuretools.io",
  "submission_url": "https://www.futuretools.io/submit-a-tool",
  "site_status": "active",
  "auth_type": "none",
  "captcha_type": "none",
  "pricing_type": "free",
  "categories": ["AI Tools"]
}
```

**Auth types:** `none` (open form), `email_password`, `google_only`, `google_and_email`, `facebook`, `unknown`

**Site statuses:** `active`, `not_found`, `domain_dead`, `timeout`, `cloudflare_blocked`, `error`, `invalid_url`, `facebook_group`, `domain_parked`

### Submission Plan

`submission_plan.json` contains per-directory submission targets:

```json
{
  "directory_name": "FutureTools",
  "submission_url": "https://www.futuretools.io/submit-a-tool",
  "status": "pending",
  "copy": {
    "title": "Your Product — One-line tagline",
    "description": "2-3 sentence description for this specific directory."
  },
  "discovered_fields": [...],
  "credentials": {
    "email": "YOUR_EMAIL",
    "name": "YOUR_NAME",
    "username": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD"
  }
}
```

**Status values:** `pending`, `discovered`, `submitted`, `skipped`, `skipped_paid`, `skipped_login_required`, `timeout`, `no_form_found`, `no_fields_matched`, `captcha`, `cloudflare_blocked`, `domain_parked`, `submit_timeout`, `deferred`

## Scripts Reference

| Script | Purpose | Workers | Method |
|---|---|---|---|
| `analyze_directories.py` | HTTP-level analysis (auth, captcha, pricing) | ThreadPool | urllib |
| `cleanup_and_categorize.py` | Error triage + build browser check list | Single | JSON processing |
| `browser_verify.py` | Browser verification of active sites | 10 async | Playwright |
| `discover_forms.py` | Extract form fields from submission pages | 10 async | Playwright |
| `submit_directories.py` | Auto-fill and submit forms | 5 async | Playwright |
| `add_new_directories.py` | Parse and add new directories from text | Single | Text parsing |

### Running Scripts Manually

```bash
# Activate the virtual environment
source .venv/bin/activate

# Full pipeline
python analyze_directories.py
python cleanup_and_categorize.py
python browser_verify.py
python browser_verify.py --recheck-unknown
python discover_forms.py
python submit_directories.py
```

## Adding More Directories

### From a URL

Tell the agent: "Add directories from https://example.com/directory-list"

The agent follows the skill at `.cursor/skills/add-directories/SKILL.md` to:
1. Fetch and parse the page for directory links
2. Deduplicate against existing entries
3. Append new entries to `directories.json`
4. Run the analysis pipeline on new entries

### From Pasted Text

Paste a list of directories in any format:
- `Name - https://url.com`
- `[Name](https://url.com)` (Markdown)
- Plain URLs (one per line)
- CSV/TSV with Name and URL columns

### From GitHub Repos

Tell the agent: "Add directories from https://github.com/owner/repo"

The agent clones the repo, parses its directory listing, and adds new entries.

## Configuration

### Credentials

Before running submissions, replace `YOUR_*` placeholders in:
- `submit_directories.py` — the `PRODUCT` dict
- `submission_plan.json` — the `credentials` blocks

**Security warning:** Credentials are stored in plaintext. Use throwaway passwords, never your real ones. Always strip personal data before pushing to git (search for your email/name/password).

### Submission Preferences

The agent will ask about these during onboarding:
- **Google login directories** — Enable to access ~150 additional directories
- **Paid directories** — Skip or flag for manual review
- **Captcha directories** — Skip or attempt with manual captcha solving

## Common Issues

| Issue | Cause | Fix |
|---|---|---|
| `playwright` not found | Missing dependency | `pip install playwright && playwright install chromium` |
| Cloudflare blocks | Bot detection | Use manual browser submission via Playwright MCP |
| Google login popup closes | Cross-origin policy | Switch to the Google tab with `browser_tabs` before interacting |
| Form fields not matched | Unusual field names | Use manual browser submission for these directories |
| Business email required | Directory rejects gmail/yahoo | Use a custom domain email or skip |
| Reciprocal link required | Old web directory policy | Skip unless you want to add a backlink |
| "Invalid site key" on captcha | Directory's captcha is misconfigured | Skip — this is the directory's bug |

## Project Structure

```
ai-directories/
├── AGENTS.md                    # Cursor / Windsurf agent instructions
├── CLAUDE.md                    # Claude Code / Cowork instructions
├── GEMINI.md                    # Gemini instructions
├── README.md                    # This file
├── checkpoint.md                # Progress tracking (updated by agent)
├── directories.json             # Master directory database (100+ entries)
├── submission_plan.json         # Per-directory submission targets
├── browser_check_list.json      # Intermediate: browser verification queue
├── analyze_directories.py       # HTTP analysis pipeline
├── cleanup_and_categorize.py    # Error triage + browser check builder
├── browser_verify.py            # Playwright browser verification
├── discover_forms.py            # Playwright form field discovery
├── submit_directories.py        # Playwright auto-submission engine
├── add_new_directories.py       # Parse/add new directories
├── requirements.txt             # Python dependencies
├── logo.png                     # Your product logo (gitignored)
├── site-image.png               # Your product screenshot (gitignored)
├── .gitignore                   # Excludes .venv, logs, screenshots
└── .cursor/
    └── skills/
        └── add-directories/
            └── SKILL.md         # Cursor skill for adding directories
```

## License

MIT
