---
name: submit-directories
description: Use when submitting a product to AI/startup directories - covers the full pipeline from collecting product info, analyzing directories, discovering forms, auto-submitting, handling captchas/OAuth/GitHub PRs, and tracking progress in checkpoint.md.
---

# Submit Directories

## Overview

Full lifecycle for submitting a product to 800+ AI tool directories: collect product info → analyze directories → build submission plan → discover forms → auto-submit → manual browser submissions → track progress.

## Setup

### Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### Configure credentials via environment variables

Never hardcode credentials in scripts. Set these before running any pipeline step:

```bash
# Required
export SUBMIT_PRODUCT_URL="https://yourproduct.com"
export SUBMIT_PRODUCT_NAME="Your Product Name"
export SUBMIT_TAGLINE="Your one-line tagline"
export SUBMIT_EMAIL="you@throwaway.com"        # use throwaway email
export SUBMIT_AUTHOR_NAME="Jane Doe"

# Recommended
export SUBMIT_AUTHOR_FIRST="Jane"
export SUBMIT_AUTHOR_LAST="Doe"
export SUBMIT_USERNAME="youruser"
export SUBMIT_PASSWORD="throwaway-pass"        # use throwaway password

# Optional
export SUBMIT_GITHUB_URL="https://github.com/you/repo"
export SUBMIT_TWITTER_URL="https://twitter.com/yourhandle"
export SUBMIT_KEYWORDS="ai,saas,marketing,automation"
export SUBMIT_LOGO="logo.png"                  # relative to script dir
export SUBMIT_SCREENSHOT="site-image.png"      # relative to script dir
```

Tip: save these to a local `.env` file (already in `.gitignore`) and load with:
```bash
set -a && source .env && set +a
```

### Place assets

- `logo.png` — product logo (used for file upload fields)
- `site-image.png` — product screenshot (used for file upload fields)

Both should be in the same directory as the scripts.

## Phase 0: Collect Product Info

Ask **one at a time** (never dump all at once):

| # | Field | Question |
|---|-------|----------|
| 1 | Product URL | "What is your product/startup website URL?" |
| 2 | Product Name | "What is your product name?" |
| 3 | Tagline | "Give me a one-line tagline." |
| 4 | Description | "Write 2-3 sentences: what it does, who it's for, what makes it different." |
| 5 | Pricing | "What is your pricing model?" (Free / Freemium / Open Source / Paid) |
| 6 | Keywords | "List 5-7 category keywords." |
| 7 | Email | "What email for submissions?" |
| 8 | Name | "What name on submissions?" (get first + last separately too) |
| 9 | Username | "Preferred username for sites requiring registration?" |
| 10 | Password | "Throwaway password for sites requiring registration?" ⚠️ Use a throwaway — never a real password. Set via `SUBMIT_PASSWORD` env var; passwords are stripped from `submission_plan.json` before saving. |
| 11 | GitHub URL | (optional) |
| 12 | Twitter/X | (optional) |

Then ask submission preferences:
- "Submit to Google-login directories? (You complete auth manually)"
- "Skip all paid directories, or flag for review?"
- "Fill forms on captcha sites and pause for you to solve, or skip?"

**Assets:** Tell user to place `logo.png` and `site-image.png` in project root.

## Phase 1: Configure

1. Set all required environment variables (see Setup section above)
2. Generate **30 unique copy variations** (title + description pairs):
   - Different angles: features, benefits, pricing, use case, comparison
   - Vary length: short punchy vs. detailed
   - Different keywords, never same opening
3. Store in `submission_plan.json`
4. Update `checkpoint.md` with product info (omit passwords)

## Phase 2: Analyze & Classify

```bash
.venv/bin/python analyze_directories.py         # HTTP-level: auth, captcha, pricing, dead domains
.venv/bin/python cleanup_and_categorize.py      # Triage errors, build browser_check_list.json
.venv/bin/python browser_verify.py              # Playwright verification (10 concurrent workers)
.venv/bin/python browser_verify.py --recheck-unknown  # Deep recheck unknowns
```

Report auth type breakdown when done.

## Phase 3: Build Submission Plan

Filter `directories.json`:
- `site_status = active`
- `auth_type = none` OR `auth_type = email_password`
- Include `google_only` / `google_and_email` only if user opted in

Create `submission_plan.json` entries with copy variation (rotate evenly), credentials, `status: pending`.

## Phase 4: Discover Forms

```bash
.venv/bin/python discover_forms.py
```

Visits each submission URL, extracts form field metadata, updates `submission_plan.json`. Report: discovered / not found / timeout counts.

## Phase 5: Auto-Submit

```bash
.venv/bin/python submit_directories.py
```

Report: submitted / no matching fields / timed out / needs manual attention.

## Phase 6: Manual Browser Submissions

Use Playwright MCP (`mcp__playwright` namespace) for sites needing manual interaction.

### Captcha sites
1. `browser_navigate` → submission URL
2. `browser_snapshot` → understand page
3. `browser_fill_form` / `browser_type` → fill all fields
4. Ask user to solve captcha
5. `browser_click` submit → verify confirmation

### Google login sites
1. `browser_navigate` → login page
2. Click "Sign in with Google"
3. Ask user to complete Google auth
4. After login, proceed to submission form
5. Use `browser_tabs` to switch between OAuth popup and main tab

### Rich text / complex forms
- **TinyMCE/Quill**: use `browser_evaluate` to set content directly
- **Combobox/select**: `browser_click` dropdown → click option
- **Multi-step forms**: `browser_snapshot` after each step for new fields
- **Custom upload widgets**: use `browser_file_upload` for logo/screenshot

## Phase 7: GitHub PR Submissions

**Requirements:** `gh` CLI installed and authenticated (`gh auth login`). Set `SUBMIT_GITHUB_URL` if you want your repo linked in entries.

For awesome-list directories:

```bash
gh repo fork <owner>/<repo>
# Create branch, add product entry following repo format
gh pr create
```

Record PR URL in `checkpoint.md`.

## Tracking

Update `checkpoint.md` after each phase with: counts by status, successful list, failed list with reasons, next steps.

### Status Values

| Status | Meaning |
|--------|---------|
| `submitted` | Confirmed submitted |
| `skipped_paid` | Requires payment |
| `skipped_login_required` | Requires account creation |
| `captcha` | Needs manual captcha solve |
| `no_form_found` | No submission form on page |
| `no_fields_matched` | Form exists, no fields matched |
| `timeout` / `submit_timeout` | Page/submit timed out |
| `cloudflare_blocked` | Cloudflare challenge |
| `domain_parked` | Dead domain |

## Rules

1. **Never assume** — unclear about product/preferences? Ask.
2. **Never commit real passwords** — use env vars only; passwords are stripped from `submission_plan.json` automatically before each save.
3. **Report after every phase** — never run pipeline silently.
4. **Explain every skip** — tell user why a directory was skipped.
5. **Verify submissions** — check for confirmation or error states.
6. **Rate limit** — max 5 concurrent submissions to avoid IP blocks.
7. **Strip personal data before git push** — search for email, name, password in all files.

## Common Submission Blockers

| Blocker | Frequency | Detection |
|---------|-----------|-----------|
| Paid listing | ~20% | Pricing page, Stripe links, "$" on submit page |
| reCAPTCHA / Turnstile | ~10% | `iframe[src*=recaptcha]` or `[data-turnstile]` |
| Login required | ~15% | Redirect to `/login` on submit URL |
| Newsletter-only forms | ~10% | Looks like submit but is email signup |
| Domain parked/dead | ~8% | No content, DNS failure |
| Cloudflare blocked | ~3% | Challenge page, 403 |
| Reciprocal link required | ~5% | Old web directories requiring backlink |

## Best ROI Directory Types

1. AI tool directories with simple HTML forms
2. Startup directories using Google Forms
3. GitHub awesome-lists accepting PRs (free, high-quality backlinks)
4. NoCode/SaaS aggregators
5. General web directories with DA≥30

## File Reference

| File | Purpose |
|------|---------|
| `directories.json` | Master database (827+ directories) |
| `submission_plan.json` | Targets with copy, fields, status (no credentials stored) |
| `checkpoint.md` | Progress tracking — source of truth |
| `analyze_directories.py` | HTTP-level analysis |
| `cleanup_and_categorize.py` | Triage + browser check list |
| `browser_verify.py` | Playwright browser verification |
| `discover_forms.py` | Form field discovery |
| `submit_directories.py` | Auto-submission engine |
