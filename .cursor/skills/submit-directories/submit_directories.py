#!/usr/bin/env python3
"""
Auto-submit a product to discovered directories using Playwright.
Reads submission_plan.json, fills forms heuristically, and submits.

Configure the PRODUCT dict below with your own details before running.
"""
import asyncio
import json
import re
import time
import sys

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

WORKERS = 5
NAV_TIMEOUT_MS = 15000
JS_WAIT_MS = 3000
HARD_LIMIT_S = 30
BLOCKED_RESOURCE_TYPES = {"media", "font"}  # allow images for upload

import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Product data — CONFIGURE THESE WITH YOUR OWN DETAILS
PRODUCT = {
    "url": "https://YOUR_PRODUCT_URL",
    "app_url": "https://YOUR_APP_URL",
    "github": "https://github.com/YOUR_GITHUB_REPO",
    "name": "YOUR_PRODUCT_NAME",
    "tagline": "YOUR_PRODUCT_TAGLINE",
    "email": "YOUR_EMAIL",
    "author_name": "YOUR_NAME",
    "author_first": "YOUR_FIRST_NAME",
    "author_last": "YOUR_LAST_NAME",
    "username": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD",
    "twitter": "https://twitter.com/YOUR_TWITTER_HANDLE",
    "category_keywords": ["ai", "sales", "saas", "marketing", "automation", "lead generation", "open source"],
    "logo_path": os.path.join(SCRIPT_DIR, "logo.png"),
    "screenshot_path": os.path.join(SCRIPT_DIR, "site-image.png"),
}


def match_field(field):
    """Determine what value to fill based on field metadata."""
    name = (field.get('name', '') or '').lower()
    label = (field.get('label', '') or '').lower()
    placeholder = (field.get('placeholder', '') or '').lower()
    ftype = (field.get('type', '') or '').lower()
    fid = (field.get('id', '') or '').lower()
    tag = (field.get('tag', '') or '').lower()
    combined = f"{name} {label} {placeholder} {fid}"

    # Skip hidden, submit, checkbox, radio, file, image, search
    if ftype in ('hidden', 'submit', 'checkbox', 'radio', 'file', 'image', 'search', 'button'):
        return None

    # Password
    if ftype == 'password':
        return ('password', PRODUCT['password'])

    # Email
    if ftype == 'email' or any(k in combined for k in ['email', 'e-mail', 'e_mail']):
        return ('email', PRODUCT['email'])

    # URL / Website
    if ftype == 'url' or any(k in combined for k in [
        'url', 'website', 'web site', 'homepage', 'web address', 'tool-tool-website',
        'tool url', 'tool_url', 'product url', 'product_url', 'link', 'site'
    ]):
        return ('url', PRODUCT['url'])

    # GitHub specifically
    if any(k in combined for k in ['github']):
        return ('github', PRODUCT['github'])

    # Twitter
    if any(k in combined for k in ['twitter']):
        return ('twitter', PRODUCT['twitter'])

    # Social media (leave empty)
    if any(k in combined for k in ['facebook', 'instagram', 'linkedin', 'discord', 'youtube', 'product hunt', 'social']):
        return None

    # Phone / Tel
    if ftype == 'tel' or any(k in combined for k in ['phone', 'tel']):
        return None

    # Full name
    if any(k in combined for k in ['your name', 'your-name', 'full name', 'fullname', 'contact name', 'name *', 'listcontact']):
        if 'last' in combined or 'nachname' in combined:
            return ('last_name', PRODUCT['author_last'])
        if 'first' in combined or 'vorname' in combined:
            return ('first_name', PRODUCT['author_first'])
        return ('name', PRODUCT['author_name'])

    # First name / Last name
    if any(k in combined for k in ['first_name', 'firstname', 'first name', 'vorname']):
        return ('first_name', PRODUCT['author_first'])
    if any(k in combined for k in ['last_name', 'lastname', 'last name', 'nachname']):
        return ('last_name', PRODUCT['author_last'])

    # Author
    if any(k in combined for k in ['author']):
        return ('author', PRODUCT['author_name'])

    # Username
    if any(k in combined for k in ['username', 'user name', 'user_name']):
        return ('username', PRODUCT['username'])

    # Tool / Product / Company name
    if any(k in combined for k in [
        'tool name', 'tool-name', 'tool_name', 'product name', 'product_name',
        'company name', 'company_name', 'companyname', 'startup name',
        'app name', 'app_name', 'project name', 'title', 'name of',
        'listorgname', 'ai tool name',
    ]):
        return ('product_name', None)  # Will be set from copy

    # Subject
    if any(k in combined for k in ['subject']):
        return ('subject', None)  # Will be set from copy title

    # Description / Message / Comment / Content / Overview / About
    if tag == 'textarea' or any(k in combined for k in [
        'description', 'message', 'comment', 'content', 'overview', 'about',
        'details', 'summary', 'pitch', 'what does', 'tell us',
        'how is your', 'why did you', 'founding', 'short-ter',
        'where can people', 'who is the', 'product aimed',
        'statement', 'promo', 'bio',
    ]):
        return ('description', None)  # Will be set from copy

    # Location
    if any(k in combined for k in ['location', 'city', 'state', 'zip', 'country', 'address', 'addr']):
        return None

    # Date
    if ftype == 'date' or any(k in combined for k in ['date', 'launch', 'when did']):
        return ('date', '2025-01-01')

    # Captcha math fields
    if any(k in combined for k in ['captcha', 'plus', '+ ']):
        return None  # Can't solve

    # Job / Position / Industry
    if any(k in combined for k in ['job', 'position', 'industry', 'role']):
        return ('job', 'Founder')

    # Company
    if any(k in combined for k in ['company']):
        return ('company', PRODUCT['name'])

    # Fallback: if it's a text input with no clear purpose, skip
    return None


async def submit_site(context, entry, seq_num, total, results):
    """Visit a directory and attempt to fill + submit its form."""
    name = entry['directory_name']
    url = entry['submission_url']
    copy = entry.get('copy', {})
    title = copy.get('title', PRODUCT['name'] + ' — ' + PRODUCT['tagline'])
    desc = copy.get('description', 'Configure your product description in submission_plan.json copy variations.')
    tag = f"[{seq_num}/{total}]"

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

            # Use JS to find and fill form fields
            fill_result = await page.evaluate('''(args) => {
                const { product, title, desc, authorName, authorFirst, authorLast,
                        email, username, password, productUrl, github, twitter } = args;

                function matchField(el) {
                    const name = (el.name || '').toLowerCase();
                    const label = (el.labels?.[0]?.textContent || el.getAttribute('aria-label') || '').toLowerCase();
                    const ph = (el.placeholder || '').toLowerCase();
                    const id = (el.id || '').toLowerCase();
                    const type = (el.type || '').toLowerCase();
                    const tag = el.tagName.toLowerCase();
                    const c = name + ' ' + label + ' ' + ph + ' ' + id;

                    if (['hidden','submit','checkbox','radio','file','image','button'].includes(type)) return null;
                    if (el.offsetParent === null && type !== 'textarea') return null;

                    if (type === 'search') return null;
                    if (type === 'password') return password;
                    if (type === 'email' || /email|e-mail|e_mail/.test(c)) return email;
                    if (type === 'url' || /\burl\b|website|web.?site|homepage|web.?address|tool.?url|product.?url|tool-tool-website|\blink\b/.test(c)) {
                        if (/github/.test(c)) return github;
                        if (/twitter/.test(c)) return twitter;
                        if (/facebook|instagram|linkedin|discord|youtube|product.?hunt|social/.test(c)) return '';
                        return productUrl;
                    }
                    if (/github/.test(c)) return github;
                    if (/twitter/.test(c)) return twitter;
                    if (/facebook|instagram|linkedin|discord|youtube|product.?hunt|social/.test(c)) return '';
                    if (type === 'tel' || /phone|tel/.test(c)) return '';
                    if (/captcha|\bplus\b|\+ /.test(c)) return null;

                    if (/last.?name|nachname/.test(c)) return authorLast;
                    if (/first.?name|vorname/.test(c)) return authorFirst;
                    if (/your.?name|full.?name|contact.?name|listcontact|\bauthor\b/.test(c)) return authorName;
                    if (/user.?name/.test(c)) return username;

                    if (/tool.?name|product.?name|company.?name|startup.?name|app.?name|project.?name|\btitle\b|name.?of|listorgname/.test(c)) return product;
                    if (/\bsubject\b/.test(c)) return title;

                    if (/job|position|industry|role/.test(c)) return 'Founder';
                    if (/company/.test(c)) return product;
                    if (/location|city|state|zip|country|address|addr/.test(c)) return '';
                    if (type === 'date' || /date|launch|when.?did/.test(c)) return '2025-01-01';

                    if (tag === 'textarea' || /description|message|comment|content|overview|about|details|summary|pitch|what.?does|tell.?us|statement|promo|bio/.test(c)) return desc;

                    return null;
                }

                const allInputs = document.querySelectorAll('input, textarea, select');
                const filled = [];
                const skipped = [];

                for (const el of allInputs) {
                    const val = matchField(el);
                    if (val === null) {
                        skipped.push({name: el.name, type: el.type, tag: el.tagName});
                        continue;
                    }
                    if (val === '') continue; // intentionally empty

                    try {
                        if (el.tagName === 'SELECT') {
                            // Try to find best option
                            const options = [...el.options];
                            const aiOpt = options.find(o => /ai|saas|software|tech|tool|marketing|sales|automation/i.test(o.text));
                            if (aiOpt) {
                                el.value = aiOpt.value;
                                el.dispatchEvent(new Event('change', {bubbles: true}));
                                filled.push({name: el.name, value: aiOpt.text});
                            }
                        } else {
                            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                                el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype, 'value'
                            )?.set;
                            if (nativeInputValueSetter) {
                                nativeInputValueSetter.call(el, val);
                            } else {
                                el.value = val;
                            }
                            el.dispatchEvent(new Event('input', {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                            filled.push({name: el.name || el.id, value: val.substring(0, 50)});
                        }
                    } catch(e) {
                        skipped.push({name: el.name, error: e.message});
                    }
                }

                // Try to find and click submit button
                const submitBtn = document.querySelector(
                    'button[type="submit"], input[type="submit"], ' +
                    'button:not([type])'
                );
                let buttons = [...document.querySelectorAll('button, input[type="submit"], a[role="button"]')];
                const submitButton = buttons.find(b => {
                    const t = (b.textContent || b.value || '').toLowerCase().trim();
                    return /^submit|^send|^post|^add|^create|^register|^sign up|^list|^save/.test(t);
                }) || submitBtn;

                let submitted = false;
                let submitText = '';
                if (submitButton && filled.length > 0) {
                    submitText = (submitButton.textContent || submitButton.value || '').trim().substring(0, 50);
                    submitButton.click();
                    submitted = true;
                }

                return {
                    filled: filled.length,
                    skipped: skipped.length,
                    filledDetails: filled,
                    submitted: submitted,
                    submitButtonText: submitText,
                    pageUrl: window.location.href,
                };
            }''', {
                'product': PRODUCT['name'],
                'title': title,
                'desc': desc,
                'authorName': PRODUCT['author_name'],
                'authorFirst': PRODUCT['author_first'],
                'authorLast': PRODUCT['author_last'],
                'email': PRODUCT['email'],
                'username': PRODUCT['username'],
                'password': PRODUCT['password'],
                'productUrl': PRODUCT['url'],
                'github': PRODUCT['github'],
                'twitter': PRODUCT['twitter'],
            })

            # Handle file upload fields (logo / screenshot)
            try:
                file_inputs = await page.query_selector_all('input[type="file"]')
                for fi in file_inputs:
                    fi_name = (await fi.get_attribute('name') or '').lower()
                    fi_id = (await fi.get_attribute('id') or '').lower()
                    fi_label = f"{fi_name} {fi_id}"
                    if any(k in fi_label for k in ['logo', 'icon', 'avatar']):
                        await fi.set_input_files(PRODUCT['logo_path'])
                    elif any(k in fi_label for k in ['screen', 'image', 'photo', 'screenshot', 'cover', 'banner']):
                        await fi.set_input_files(PRODUCT['screenshot_path'])
                    else:
                        # Default: use screenshot for first, logo for second
                        await fi.set_input_files(PRODUCT['screenshot_path'])
            except Exception:
                pass

            # Wait a bit for submission to process
            if fill_result.get('submitted'):
                await page.wait_for_timeout(2000)

        elapsed = time.monotonic() - t0
        filled = fill_result.get('filled', 0)
        submitted = fill_result.get('submitted', False)
        btn_text = fill_result.get('submitButtonText', '')

        if submitted and filled > 0:
            status = 'submitted'
            results['submitted'] += 1
        elif filled > 0:
            status = 'filled_no_submit'
            results['filled'] += 1
        else:
            status = 'no_fields_matched'
            results['no_match'] += 1

        entry['status'] = status
        entry['submit_result'] = fill_result

        marker = "OK" if submitted else "FILL" if filled > 0 else "SKIP"
        print(f"{tag} [{marker:4s}] {name[:38]:38s} {elapsed:4.1f}s  filled={filled}  btn=\"{btn_text[:25]}\"")

    except (PWTimeout, TimeoutError):
        elapsed = time.monotonic() - t0
        print(f"{tag} [TIME] {name[:38]:38s} {elapsed:4.1f}s  TIMEOUT")
        entry['status'] = 'submit_timeout'
        results['timeout'] += 1
    except Exception as e:
        print(f"{tag} [ERR ] {name[:38]:38s}  {str(e)[:60]}")
        entry['status'] = 'submit_error'
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

    # Filter to discovered entries only, skip search-only
    todo = []
    for e in plan:
        if e.get('status') != 'discovered':
            continue
        # Check if it has real form fields
        forms = e.get('form_fields') or []
        has_real = False
        for form in forms:
            for f in form.get('fields', []):
                if f.get('type') not in ('checkbox', 'search', 'hidden', 'radio', ''):
                    has_real = True
                    break
            if has_real:
                break
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
            ignore_https_errors=True,
        )

        async def worker(entry, seq_num):
            async with semaphore:
                await submit_site(context, entry, seq_num, total, results)

        tasks = [worker(e, i + 1) for i, e in enumerate(todo)]
        await asyncio.gather(*tasks)
        await browser.close()

    # Save updated plan
    with open('submission_plan.json', 'w') as f:
        json.dump(plan, f, indent=2)

    # Summary
    print(f"\n=== DONE ===")
    print(f"  Submitted:        {results['submitted']}")
    print(f"  Filled (no btn):  {results['filled']}")
    print(f"  No fields match:  {results['no_match']}")
    print(f"  Timeout:          {results['timeout']}")
    print(f"  Error:            {results['error']}")


if __name__ == '__main__':
    asyncio.run(main())
