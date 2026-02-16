#!/usr/bin/env python3
"""
Use Playwright to visit all sites that need browser verification.
Analyzes rendered page content for auth type, captcha, etc.
"""
import asyncio
import json
import re
import sys
import time

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
except ImportError:
    print("Installing playwright...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# --- Tunable settings ---
WORKERS = 5               # number of concurrent browser tabs
NAV_TIMEOUT_MS = 10000    # max time for page.goto()
JS_WAIT_MS = 800          # wait for JS rendering after load
JS_WAIT_MS_DEEP = 2500    # longer wait for deep recheck (SPA/JS-heavy)
HARD_LIMIT_S = 15         # hard per-site wall-clock limit (seconds)

# Resource types to block (speeds up loads significantly)
BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}


async def analyze_page(page, url, deep=False):
    """Analyze a loaded page for auth/captcha/submission info."""
    result = {
        'auth_type': 'unknown',
        'captcha_type': 'none',
        'requires_login': False,
        'site_status': 'active',
    }

    try:
        html = (await page.content()).lower()
    except Exception:
        result['site_status'] = 'error'
        return result

    title = (await page.title()).lower()

    # Check if page is dead/404
    if any(x in title for x in ['404', 'not found', 'page not found', 'error']):
        result['site_status'] = 'not_found'
    if any(x in html for x in ['page not found', '404 error', 'this page doesn\'t exist', 'page doesn&#39;t exist']):
        result['site_status'] = 'not_found'

    # Cloudflare challenge
    if 'just a moment' in title or 'checking your browser' in html or 'cf-browser-verification' in html:
        result['site_status'] = 'cloudflare_blocked'
        result['captcha_type'] = 'cloudflare'
        return result

    # Parked / for-sale domains
    if any(x in html for x in ['domain is for sale', 'buy this domain', 'domain may be for sale', 'parked domain', 'this domain is parked']):
        result['site_status'] = 'domain_parked'
        return result

    # --- Auth detection ---
    has_google = has_github = has_twitter = has_email_pass = False
    has_facebook = has_apple = has_linkedin = False

    for pat in ('accounts.google.com', 'googleapis.com/auth', 'google-signin',
                'gsi/client', 'sign in with google', 'login with google',
                'continue with google', 'google.com/o/oauth', 'google-login',
                'auth/google', 'oauth/google', 'btn-google', 'btn_google',
                'social-google', 'google oauth', 'google_oauth'):
        if pat in html:
            has_google = True
            break

    for pat in ('github.com/login/oauth', 'sign in with github', 'login with github',
                'continue with github', 'auth/github', 'oauth/github',
                'btn-github', 'btn_github', 'social-github'):
        if pat in html:
            has_github = True
            break

    for pat in ('api.twitter.com/oauth', 'sign in with twitter', 'login with twitter',
                'continue with twitter', 'auth/twitter', 'sign in with x',
                'continue with x', 'login with x', 'btn-twitter', 'social-twitter'):
        if pat in html:
            has_twitter = True
            break

    for pat in ('facebook.com/v', 'facebook.com/dialog/oauth', 'connect.facebook.net',
                'sign in with facebook', 'login with facebook', 'continue with facebook',
                'auth/facebook', 'oauth/facebook', 'btn-facebook', 'btn_facebook',
                'social-facebook', 'fb-login', 'fbconnect'):
        if pat in html:
            has_facebook = True
            break

    for pat in ('appleid.apple.com/auth', 'sign in with apple', 'continue with apple',
                'auth/apple', 'apple-login', 'btn-apple', 'apple-sign-in'):
        if pat in html:
            has_apple = True
            break

    for pat in ('linkedin.com/oauth', 'sign in with linkedin', 'login with linkedin',
                'continue with linkedin', 'auth/linkedin', 'oauth/linkedin',
                'btn-linkedin', 'social-linkedin'):
        if pat in html:
            has_linkedin = True
            break

    if re.search(r'<input[^>]*type=["\']password["\']', html):
        has_email_pass = True

    for pat in ('sign in to continue', 'log in to continue', 'login to submit',
                'sign up to submit', 'create an account', 'you must log in',
                'please sign in', 'please log in', 'sign in to submit',
                'login required', 'sign up to continue'):
        if pat in html:
            result['requires_login'] = True
            break

    auths = []
    if has_google: auths.append('google')
    if has_github: auths.append('github')
    if has_twitter: auths.append('twitter')
    if has_facebook: auths.append('facebook')
    if has_apple: auths.append('apple')
    if has_linkedin: auths.append('linkedin')
    if has_email_pass: auths.append('email_password')

    if not auths:
        # Check for <form> tags in HTML
        has_form = bool(re.search(r'<form[^>]*>', html))
        # Also check for <input> fields outside form wrappers (React/Vue style)
        has_inputs = bool(re.search(
            r'<input[^>]*type=["\'](?:text|email|url|search|tel)["\']', html))
        # Check for contenteditable or textarea
        has_textarea = 'textarea' in html or 'contenteditable' in html
        # Check for role="form" or data-form attributes (JS frameworks)
        has_js_form = bool(re.search(
            r'role=["\']form["\']|data-form|ng-form|formik|react-hook-form', html))

        if has_form or has_inputs or has_textarea or has_js_form:
            result['auth_type'] = 'none'
        elif deep:
            # --- Deep: use Playwright DOM queries for JS-rendered content ---
            try:
                dom_info = await page.evaluate('''() => {
                    const inputs = document.querySelectorAll(
                        'input[type="text"], input[type="email"], input[type="url"], '
                        + 'input[type="password"], input[type="search"], input[type="tel"], '
                        + 'input:not([type]), textarea');
                    const forms = document.querySelectorAll('form, [role="form"]');
                    const buttons = [...document.querySelectorAll('button, a, [role="button"]')];
                    const btnTexts = buttons.map(b => b.textContent.toLowerCase().trim())
                        .filter(t => t.length < 80);
                    const signupBtns = btnTexts.filter(t =>
                        /sign.?up|sign.?in|log.?in|register|get started|create account|submit|join/i.test(t));
                    const oauthBtns = btnTexts.filter(t =>
                        /google|github|facebook|twitter|apple|linkedin|microsoft|sso/i.test(t));
                    return {
                        inputCount: inputs.length,
                        formCount: forms.length,
                        signupBtns: signupBtns.slice(0, 10),
                        oauthBtns: oauthBtns.slice(0, 10),
                    };
                }''')
            except Exception:
                dom_info = None

            if dom_info:
                # Re-check OAuth from button text
                for btn in dom_info.get('oauthBtns', []):
                    if 'google' in btn: has_google = True
                    if 'github' in btn: has_github = True
                    if 'facebook' in btn: has_facebook = True
                    if 'twitter' in btn or ' x ' in btn: has_twitter = True
                    if 'apple' in btn: has_apple = True
                    if 'linkedin' in btn: has_linkedin = True

                # Rebuild auths after DOM check
                auths = []
                if has_google: auths.append('google')
                if has_github: auths.append('github')
                if has_twitter: auths.append('twitter')
                if has_facebook: auths.append('facebook')
                if has_apple: auths.append('apple')
                if has_linkedin: auths.append('linkedin')

                if auths:
                    pass  # handled below
                elif dom_info['formCount'] > 0 or dom_info['inputCount'] > 0:
                    result['auth_type'] = 'none'
                elif dom_info['signupBtns']:
                    result['auth_type'] = 'none'
                    result['_submission_hints'] = dom_info['signupBtns']
                else:
                    # Truly no interactive elements found
                    result['auth_type'] = 'unknown'
            else:
                result['auth_type'] = 'unknown'
        else:
            result['auth_type'] = 'unknown'

    if auths:
        if len(auths) == 1:
            result['auth_type'] = auths[0] + '_only' if auths[0] in ('google',) else auths[0]
            result['requires_login'] = True
        else:
            result['auth_type'] = '+'.join(auths)
            result['requires_login'] = True

    # --- Captcha detection ---
    if re.search(r'g-recaptcha|recaptcha/api\.js|grecaptcha', html):
        if re.search(r'recaptcha/api\.js\?.*render=|grecaptcha\.execute', html):
            result['captcha_type'] = 'recaptcha_v3'
        else:
            result['captcha_type'] = 'recaptcha_v2'

    if re.search(r'hcaptcha\.com|h-captcha', html):
        result['captcha_type'] = 'hcaptcha'

    if re.search(r'challenges\.cloudflare\.com/turnstile|cf-turnstile', html):
        result['captcha_type'] = 'cloudflare_turnstile'

    if result['captcha_type'] == 'none' and 'captcha' in html:
        result['captcha_type'] = 'captcha_unknown'

    return result


async def check_site(context, entry, seq_num, total, data, stats, deep=False):
    """Check a single site using its own page (tab)."""
    idx = entry['index']
    name = entry['name']
    url = entry['url']
    tag = f"[{seq_num}/{total}]"

    js_wait = JS_WAIT_MS_DEEP if deep else JS_WAIT_MS

    page = await context.new_page()

    # Block heavy resources to speed things up
    await page.route("**/*", lambda route: (
        route.abort() if route.request.resource_type in BLOCKED_RESOURCE_TYPES
        else route.continue_()
    ))

    try:
        t0 = time.monotonic()
        async with asyncio.timeout(HARD_LIMIT_S):
            await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until='domcontentloaded')
            await page.wait_for_timeout(js_wait)
            result = await analyze_page(page, url, deep=deep)

        elapsed = time.monotonic() - t0

        data[idx]['auth_type'] = result['auth_type']
        data[idx]['captcha_type'] = result['captcha_type']
        data[idx]['requires_login'] = result['requires_login']
        if result['site_status'] != 'active':
            data[idx]['site_status'] = result['site_status']
        else:
            data[idx]['site_status'] = 'active'
            if 'analysis_error' in data[idx]:
                del data[idx]['analysis_error']

        short_status = result['site_status'][:10]
        print(f"{tag} {name[:35]:35s} {elapsed:4.1f}s  auth={result['auth_type']}  cap={result['captcha_type']}  st={short_status}")
        stats['ok'] += 1

    except (PWTimeout, TimeoutError):
        elapsed = time.monotonic() - t0
        print(f"{tag} {name[:35]:35s} {elapsed:4.1f}s  TIMEOUT - skipped")
        data[idx]['site_status'] = 'timeout'
        stats['timeout'] += 1
    except Exception as e:
        print(f"{tag} {name[:35]:35s}  ERR: {str(e)[:60]}")
        data[idx]['site_status'] = 'error'
        data[idx]['analysis_error'] = str(e)[:200]
        stats['error'] += 1
    finally:
        try:
            await page.close()
        except Exception:
            pass


async def main():
    print("[startup] browser_verify.py starting...", flush=True)
    recheck = '--recheck-unknown' in sys.argv or '--deep' in sys.argv

    print("[startup] Loading directories.json...", flush=True)
    with open('directories.json', 'r') as f:
        data = json.load(f)
    print(f"[startup] Loaded {len(data)} entries", flush=True)

    if recheck:
        # Build check list from active unknowns in directories.json
        check_list = []
        for i, d in enumerate(data):
            if d.get('auth_type') == 'unknown' and d.get('site_status') == 'active':
                check_list.append({
                    'index': i,
                    'name': d['name'],
                    'url': d.get('submission_url') or d.get('url', ''),
                })
        mode = 'DEEP recheck'
    else:
        with open('browser_check_list.json', 'r') as f:
            check_list = json.load(f)
        mode = 'standard'

    total = len(check_list)
    print(f"[{mode}] Checking {total} sites with {WORKERS} workers (nav {NAV_TIMEOUT_MS/1000:.0f}s, hard {HARD_LIMIT_S}s)", flush=True)

    if total == 0:
        print("[startup] Nothing to check — exiting.", flush=True)
        return

    stats = {'ok': 0, 'timeout': 0, 'error': 0}
    semaphore = asyncio.Semaphore(WORKERS)

    print("[startup] Launching Playwright chromium...", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        print("[startup] Browser launched, creating context...", flush=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 720},
            ignore_https_errors=True,
        )
        print(f"[startup] Context ready, dispatching {total} tasks...", flush=True)

        save_lock = asyncio.Lock()
        processed_count = 0

        async def worker(entry, seq_num):
            nonlocal processed_count
            async with semaphore:
                await check_site(context, entry, seq_num, total, data, stats, deep=recheck)
                processed_count += 1
                # Intermediate save every 50 sites
                if processed_count % 50 == 0:
                    async with save_lock:
                        with open('directories.json', 'w') as f:
                            json.dump(data, f, indent=2)
                        print(f"  [autosave] {processed_count}/{total} processed", flush=True)

        tasks = [worker(entry, i + 1) for i, entry in enumerate(check_list)]
        await asyncio.gather(*tasks)

        print("[cleanup] Closing browser...", flush=True)
        await browser.close()

    # Save updated JSON
    with open('directories.json', 'w') as f:
        json.dump(data, f, indent=2)

    # Print summary
    print(f"\n=== DONE === ok={stats['ok']}  timeout={stats['timeout']}  error={stats['error']}")

    auth_counts = {}
    status_counts = {}
    for d in data:
        a = d.get('auth_type', 'unknown')
        auth_counts[a] = auth_counts.get(a, 0) + 1
        s = d.get('site_status', 'unknown')
        status_counts[s] = status_counts.get(s, 0) + 1

    print("\nAuth:", "  ".join(f"{k}:{v}" for k, v in sorted(auth_counts.items(), key=lambda x: -x[1])))
    print("Status:", "  ".join(f"{k}:{v}" for k, v in sorted(status_counts.items(), key=lambda x: -x[1])))


if __name__ == '__main__':
    asyncio.run(main())
