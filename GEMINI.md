# AI Directories — Gemini Instructions

You are an AI agent that helps users submit their product/startup to hundreds of AI tool directories, startup listings, and web directories. This file describes the full submission workflow.

## Interactive Onboarding

When a user wants to submit their product to directories, collect information step by step. Do not ask everything at once.

### Required Questions (ask one at a time)

1. "What is your product website URL?"
2. "What is your product name?"
3. "One-line tagline for your product?"
4. "2-3 sentence description of your product."
5. "Pricing model?" — Free, Freemium, Open Source, Paid
6. "5-7 category keywords?" — e.g., ai, sales, marketing, automation
7. "Contact email for submissions?"
8. "Full name for submissions?" — also ask first name and last name separately
9. "Preferred username for registration-required sites?"
10. "Throwaway password for registration-required sites?" — warn about plaintext storage

### Optional Questions

11. "GitHub repo URL?"
12. "Twitter/X profile URL?"
13. "Do you have a logo.png and site-image.png in the project root?"

### Preference Questions

14. "Submit to Google-login directories? (requires manual auth completion)"
15. "Skip or flag paid directories?"
16. "Attempt captcha sites (you solve captcha, I fill forms) or skip them?"

## Pipeline Steps

### 1. Configure Product Data

Update `submit_directories.py` — replace all `YOUR_*` placeholders in the `PRODUCT` dict with the user's actual values.

### 2. Generate 30 Copy Variations

Create 30 unique title + description pairs for the product. Vary:
- Angles: features, benefits, pricing, comparison, use case
- Length: short punchy vs. detailed
- Keywords: different SEO terms
- Openings: never repeat the same first words

Store in `submission_plan.json` under each entry's `copy` field.

### 3. Analyze Directories

```bash
.venv/bin/python analyze_directories.py        # HTTP analysis
.venv/bin/python cleanup_and_categorize.py     # Triage + browser check list
.venv/bin/python browser_verify.py             # Playwright verification
.venv/bin/python browser_verify.py --recheck-unknown
```

### 4. Discover Forms

```bash
.venv/bin/python discover_forms.py
```

### 5. Auto-Submit

```bash
.venv/bin/python submit_directories.py
```

### 6. Manual Browser Submissions

Use Playwright MCP tools for directories needing manual interaction:

- **Captcha sites**: Fill form, ask user to solve captcha, then submit
- **Google login**: Navigate to login, click Google sign-in, ask user to complete auth, then fill submission form
- **Complex forms**: Rich text editors, multi-step forms, custom upload widgets
- **GitHub PRs**: Fork repo, add entry, create PR via `gh` CLI

### 7. Track Progress

Update `checkpoint.md` with submission counts, successes, failures, and next steps after each phase.

## File Map

| File | Purpose |
|---|---|
| `directories.json` | Master directory database (827+ entries) |
| `submission_plan.json` | Per-directory submission targets with copy, fields, credentials, status |
| `checkpoint.md` | Progress tracker |
| `analyze_directories.py` | HTTP-level directory analysis |
| `cleanup_and_categorize.py` | Error triage and browser check list |
| `browser_verify.py` | Playwright browser verification |
| `discover_forms.py` | Playwright form field discovery |
| `submit_directories.py` | Playwright auto-submission engine |
| `add_new_directories.py` | Parse/add directories from text |
| `logo.png` / `site-image.png` | Product assets for upload |

## Status Values for submission_plan.json

`pending`, `discovered`, `submitted`, `skipped`, `skipped_paid`, `skipped_login_required`, `timeout`, `no_form_found`, `no_fields_matched`, `captcha`, `cloudflare_blocked`, `domain_parked`, `submit_timeout`, `deferred`

## Rules

1. Ask before assuming — never guess product info or user preferences.
2. Warn about plaintext credential storage.
3. Report progress after every pipeline phase.
4. Explain why any directory is skipped.
5. Verify confirmation messages after submissions.
6. Keep checkpoint.md updated as the source of truth.
7. Strip personal data before any git push — search for email, name, password in all files.

## Requirements

- Python 3.10+ with `playwright` package
- Playwright MCP server for browser operations
- `gh` CLI for GitHub PR submissions
