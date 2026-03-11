#!/usr/bin/env python3
"""
Auto-submit a product to discovered directories using Playwright.
Reads submission_plan.json, fills forms using native Playwright locator fills
(credentials are never passed to page JavaScript), and submits.

Configure credentials via environment variables before running:

    export SUBMIT_PRODUCT_URL="https://yourproduct.com"
    export SUBMIT_PRODUCT_NAME="Your Product"
    export SUBMIT_TAGLINE="Your one-line tagline"
    export SUBMIT_EMAIL="you@example.com"
    export SUBMIT_AUTHOR_NAME="Jane Doe"
    export SUBMIT_AUTHOR_FIRST="Jane"
    export SUBMIT_AUTHOR_LAST="Doe"
    export SUBMIT_USERNAME="youruser"
    export SUBMIT_PASSWORD="throwaway-password"
    export SUBMIT_GITHUB_URL="https://github.com/you/repo"   # optional
    export SUBMIT_TWITTER_URL="https://twitter.com/you"      # optional
    export SUBMIT_KEYWORDS="ai,saas,marketing,automation"    # optional
    export SUBMIT_LOGO="logo.png"                            # optional, relative to script dir
    export SUBMIT_SCREENSHOT="site-image.png"                # optional, relative to script dir
"""
import asyncio
import json
import os
import re
import sys
import time

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
except ImportError:
    sys.exit(
        "Playwright is not installed.\n"
        "Run: pip install -r requirements.txt && playwright install chromium"
    )

WORKERS = 5
NAV_TIMEOUT_MS = 15000
JS_WAIT_MS = 3000
HARD_LIMIT_S = 30
BLOCKED_RESOURCE_TYPES = {"media", "font"}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _env(key, default=""):
    return os.environ.get(key, default)


def _require_env(key, hint):
    val = os.environ.get(key, "")
    if not val:
        sys.exit(
            f"Error: environment variable {key} is not set ({hint}).\n"
            f"  export {key}='...'"
        )
    return val


PRODUCT = {
    "url":            _require_env("SUBMIT_PRODUCT_URL",  "your product homepage URL"),
    "app_url":        _env("SUBMIT_APP_URL"),
    "github":         _env("SUBMIT_GITHUB_URL"),
    "name":           _require_env("SUBMIT_PRODUCT_NAME", "your product name"),
    "tagline":        _require_env("SUBMIT_TAGLINE",      "one-line tagline"),
    "email":          _require_env("SUBMIT_EMAIL",        "submission email address"),
    "author_name":    _require_env("SUBMIT_AUTHOR_NAME",  "full name for submissions"),
    "author_first":   _env("SUBMIT_AUTHOR_FIRST"),
    "author_last":    _env("SUBMIT_AUTHOR_LAST"),
    "username":       _env("SUBMIT_USERNAME"),
    "password":       _env("SUBMIT_PASSWORD"),
    "twitter":        _env("SUBMIT_TWITTER_URL"),
    "category_keywords": _env("SUBMIT_KEYWORDS", "ai,saas,marketing,automation").split(","),
    "logo_path":      os.path.join(SCRIPT_DIR, _env("SUBMIT_LOGO",       "logo.png")),
    "screenshot_path": os.path.join(SCRIPT_DIR, _env("SUBMIT_SCREENSHOT", "site-image.png")),
}


async def get_field_metadata(page):
    """Extract form field metadata via page.evaluate — no credentials passed to page JS."""
    return await page.evaluate('''() => {
        const els = document.querySelectorAll('input, textarea, select');
        return [...els].map(el => ({
            tag:         el.tagName.toLowerCase(),
            type:        (el.type || '').toLowerCase(),
            name:        el.name  || '',
            id:          el.id    || '',
            placeholder: (el.placeholder || '').substring(0, 100),
            label:       (el.labels?.[0]?.textContent?.trim() ||
                          el.getAttribute('aria-label') || '').substring(0, 100),
            visible:     el.offsetParent !== null,
        }));
    }''')


def resolve_value(meta, title, desc):
    """
    Map a field's metadata to the value that should be filled.
    Returns a string to fill, '' to skip intentionally, or None to leave untouched.
    Credentials come from PRODUCT (Python scope) — never passed to page JavaScript.
    """
    ftype = meta.get('type', '')
    tag   = meta.get('tag', '')

    if not meta.get('visible', True):
        return None
    if ftype in ('hidden', 'submit', 'checkbox', 'radio', 'file', 'image', 'search', 'button'):
        return None

    name  = (meta.get('name', '')        or '').lower()
    label = (meta.get('label', '')       or '').lower()
    ph    = (meta.get('placeholder', '') or '').lower()
    fid   = (meta.get('id', '')          or '').lower()
    c = f"{name} {label} {ph} {fid}"

    if ftype == 'password':
        return PRODUCT['password']
    if ftype == 'email' or re.search(r'e-?mail|e_mail', c):
        return PRODUCT['email']
    if ftype == 'url' or re.search(
            r'\burl\b|website|web.?site|homepage|web.?address|'
            r'tool.?url|product.?url|tool-tool-website|\blink\b|\bsite\b', c):
        if 'github'  in c: return PRODUCT['github']
        if 'twitter' in c: return PRODUCT['twitter']
        if re.search(r'facebook|instagram|linkedin|discord|youtube|product.?hunt|social', c):
            return ''
        return PRODUCT['url']
    if 'github'  in c: return PRODUCT['github']
    if 'twitter' in c: return PRODUCT['twitter']
    if re.search(r'facebook|instagram|linkedin|discord|youtube|product.?hunt|social', c):
        return ''
    if ftype == 'tel' or re.search(r'\bphone\b|\btel\b', c):
        return ''
    if re.search(r'captcha|\bplus\b', c):
        return None
    if re.search(r'last.?name|nachname', c):
        return PRODUCT['author_last']
    if re.search(r'first.?name|vorname', c):
        return PRODUCT['author_first']
    if re.search(r'your.?name|full.?name|contact.?name|listcontact|\bauthor\b', c):
        return PRODUCT['author_name']
    if re.search(r'user.?name', c):
        return PRODUCT['username']
    if re.search(
            r'tool.?name|product.?name|company.?name|startup.?name|'
            r'app.?name|project.?name|\btitle\b|name.?of|listorgname|ai.?tool.?name', c):
        return title
    if re.search(r'\bsubject\b', c):
        return title
    if re.search(r'\bjob\b|\bposition\b|\bindustry\b|\brole\b', c):
        return 'Founder'
    if 'company' in c:
        return PRODUCT['name']
    if re.search(r'location|city|state|\bzip\b|country|\baddress\b|\baddr\b', c):
        return ''
    if ftype == 'date' or re.search(r'\bdate\b|\blaunch\b', c):
        return '2025-01-01'
    if tag == 'textarea' or re.search(
            r'description|message|comment|content|overview|about|'
            r'details|summary|pitch|what.?does|tell.?us|statement|promo|\bbio\b', c):
        return desc
    return None


async def fill_and_submit(page, title, desc):
    """
    Fill form fields using native Playwright locator.fill() (CDP-level, not JS injection).
    Credentials are resolved in Python and sent directly over CDP — the page's own
    JavaScript cannot intercept them via synthetic event listeners.
    """
    try:
        fields = await get_field_metadata(page)
    except Exception as e:
        return {'filled': 0, 'submitted': False, 'submitButtonText': '', 'error': str(e)[:100]}

    filled_log = []

    for meta in fields:
        value = resolve_value(meta, title, desc)
        if value is None or value == '':
            continue

        fid   = meta.get('id', '')
        fname = meta.get('name', '')
        tag   = meta.get('tag', 'input')

        if fid:
            sel = f'#{fid}'
        elif fname:
            sel = f"{tag}[name='{fname}']"
        else:
            continue

        try:
            loc = page.locator(sel).first
            if tag == 'select':
                try:
                    await loc.select_option(
                        label=re.compile(
                            r'ai|saas|software|tech|tool|marketing|sales|automation', re.I))
                except Exception:
                    pass
            else:
                await loc.fill(str(value))
                filled_log.append({'name': fname or fid, 'value': str(value)[:50]})
        except Exception:
            pass

    # --- Click submit ---
    submitted = False
    btn_text  = ''

    async def try_click(locator):
        nonlocal submitted, btn_text
        try:
            if await locator.is_visible(timeout=1000):
                try:
                    btn_text = (await locator.inner_text()).strip()[:50]
                except Exception:
                    btn_text = (await locator.get_attribute('value') or '')[:50]
                await locator.click()
                submitted = True
                return True
        except Exception:
            pass
        return False

    if not submitted:
        await try_click(page.locator('button[type="submit"]').first)
    if not submitted:
        await try_click(page.locator('input[type="submit"]').first)
    if not submitted and filled_log:
        try:
            btn = page.get_by_role(
                'button',
                name=re.compile(r'^(submit|send|post|add|create|register|sign\s?up|list|save)', re.I)
            ).first
            await try_click(btn)
        except Exception:
            pass

    return {
        'filled':           len(filled_log),
        'filledDetails':    filled_log,
        'submitted':        submitted,
        'submitButtonText': btn_text,
    }


async def submit_site(context, entry, seq_num, total, results):
    """Visit a directory and attempt to fill + submit its form."""
    name  = entry['directory_name']
    url   = entry['submission_url']
    copy  = entry.get('copy', {})
    title = copy.get('title', PRODUCT['name'] + ' — ' + PRODUCT['tagline'])
    desc  = copy.get('description', '')
    tag   = f"[{seq_num}/{total}]"

    page = await context.new_page()
    await page.route("**/*", lambda route: (
        route.abort() if route.request.resource_type in BLOCKED_RESOURCE_TYPES
        else route.continue_()
    ))

    try:
        t0 = time.monotonic()
        async with asyncio.timeout(HARD_LIMIT_S):
            await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until='domcontentloaded')
            await page.wait_for_timeout(JS_WAIT_MS)

            fill_result = await fill_and_submit(page, title, desc)

            # Handle file upload fields (logo / screenshot)
            try:
                for fi in await page.query_selector_all('input[type="file"]'):
                    fi_name  = ((await fi.get_attribute('name')) or '').lower()
                    fi_id    = ((await fi.get_attribute('id'))   or '').lower()
                    fi_label = f"{fi_name} {fi_id}"
                    if any(k in fi_label for k in ('logo', 'icon', 'avatar')):
                        await fi.set_input_files(PRODUCT['logo_path'])
                    elif any(k in fi_label for k in ('screen', 'image', 'photo', 'screenshot', 'cover', 'banner')):
                        await fi.set_input_files(PRODUCT['screenshot_path'])
                    else:
                        await fi.set_input_files(PRODUCT['screenshot_path'])
            except Exception:
                pass

            if fill_result.get('submitted'):
                await page.wait_for_timeout(2000)

        elapsed   = time.monotonic() - t0
        filled    = fill_result.get('filled', 0)
        submitted = fill_result.get('submitted', False)
        btn_text  = fill_result.get('submitButtonText', '')

        if submitted and filled > 0:
            status = 'submitted';         results['submitted'] += 1
        elif filled > 0:
            status = 'filled_no_submit';  results['filled'] += 1
        else:
            status = 'no_fields_matched'; results['no_match'] += 1

        entry['status']        = status
        entry['submit_result'] = {k: v for k, v in fill_result.items() if k != 'filledDetails'}

        marker = "OK" if submitted else "FILL" if filled > 0 else "SKIP"
        print(f"{tag} [{marker:4s}] {name[:38]:38s} {elapsed:4.1f}s  filled={filled}  btn=\"{btn_text[:25]}\"")

    except (PWTimeout, TimeoutError):
        elapsed = time.monotonic() - t0
        print(f"{tag} [TIME] {name[:38]:38s} {elapsed:4.1f}s  TIMEOUT")
        entry['status'] = 'submit_timeout'; results['timeout'] += 1
    except Exception as e:
        print(f"{tag} [ERR ] {name[:38]:38s}  {str(e)[:60]}")
        entry['status']        = 'submit_error'
        entry['submit_result'] = {'error': str(e)[:200]}
        results['error'] += 1
    finally:
        try:
            await page.close()
        except Exception:
            pass


async def main():
    with open('submission_plan.json') as f:
        plan = json.load(f)

    todo = []
    for e in plan:
        if e.get('status') != 'discovered':
            continue
        has_real = any(
            f.get('type') not in ('checkbox', 'search', 'hidden', 'radio', '')
            for form in (e.get('form_fields') or [])
            for f in form.get('fields', [])
        )
        if has_real:
            todo.append(e)

    total = len(todo)
    print(f"Submitting to {total} directories with {WORKERS} workers")

    results = {'submitted': 0, 'filled': 0, 'no_match': 0, 'timeout': 0, 'error': 0}
    semaphore = asyncio.Semaphore(WORKERS)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 720},
        )

        async def worker(entry, seq_num):
            async with semaphore:
                await submit_site(context, entry, seq_num, total, results)

        await asyncio.gather(*[worker(e, i + 1) for i, e in enumerate(todo)])
        await browser.close()

    # Strip passwords from saved plan before writing — never persist credentials to disk
    for entry in plan:
        entry.pop('password', None)
        if isinstance(entry.get('credentials'), dict):
            entry['credentials'].pop('password', None)

    with open('submission_plan.json', 'w') as f:
        json.dump(plan, f, indent=2)

    print(f"\n=== DONE ===")
    print(f"  Submitted:        {results['submitted']}")
    print(f"  Filled (no btn):  {results['filled']}")
    print(f"  No fields match:  {results['no_match']}")
    print(f"  Timeout:          {results['timeout']}")
    print(f"  Error:            {results['error']}")


if __name__ == '__main__':
    asyncio.run(main())
