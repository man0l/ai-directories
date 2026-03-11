#!/usr/bin/env python3
"""
Visit each directory submission page, discover form fields, and update submission_plan.json.
"""
import asyncio
import json
import time
import sys

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

WORKERS = 10
NAV_TIMEOUT_MS = 12000
JS_WAIT_MS = 2000
HARD_LIMIT_S = 20
BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}


async def discover_form(page, url):
    """Use Playwright DOM queries to find all form fields on the page."""
    try:
        info = await page.evaluate(r'''() => {
            // Gather all forms
            const forms = [...document.querySelectorAll('form')];
            const results = [];

            for (const form of forms) {
                const fields = [];
                const els = form.querySelectorAll(
                    'input, textarea, select, [contenteditable="true"]'
                );
                for (const el of els) {
                    if (el.type === 'hidden' || el.type === 'submit' ||
                        el.offsetParent === null) continue;
                    const label = (
                        el.labels?.[0]?.textContent?.trim() ||
                        el.getAttribute('aria-label') ||
                        el.getAttribute('placeholder') ||
                        el.getAttribute('name') ||
                        el.getAttribute('id') ||
                        ''
                    ).substring(0, 100);
                    fields.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: (el.placeholder || '').substring(0, 100),
                        label: label,
                        required: el.required || false,
                    });
                }
                if (fields.length > 0) {
                    results.push({
                        action: form.action || '',
                        method: form.method || 'get',
                        id: form.id || '',
                        class: form.className?.substring?.(0, 100) || '',
                        fields: fields,
                    });
                }
            }

            // Also look for formless inputs (React/Vue style)
            if (results.length === 0) {
                const allInputs = document.querySelectorAll(
                    'input:not([type="hidden"]):not([type="submit"]), textarea, select'
                );
                const fields = [];
                for (const el of allInputs) {
                    if (el.offsetParent === null) continue;
                    if (el.closest('form')) continue;  // already covered
                    const label = (
                        el.labels?.[0]?.textContent?.trim() ||
                        el.getAttribute('aria-label') ||
                        el.getAttribute('placeholder') ||
                        el.getAttribute('name') ||
                        el.getAttribute('id') ||
                        ''
                    ).substring(0, 100);
                    fields.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: (el.placeholder || '').substring(0, 100),
                        label: label,
                        required: el.required || false,
                    });
                }
                if (fields.length > 0) {
                    results.push({
                        action: '',
                        method: '',
                        id: '_no_form_wrapper',
                        class: '',
                        fields: fields,
                    });
                }
            }

            return {
                url: window.location.href,
                title: document.title,
                formCount: results.length,
                forms: results,
            };
        }''')
        return info
    except Exception as e:
        return {"error": str(e)[:200], "forms": []}


async def check_one(context, entry, seq_num, total, results):
    """Visit a single directory and discover its forms."""
    name = entry['directory_name']
    url = entry['submission_url']
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
            info = await discover_form(page, url)

        elapsed = time.monotonic() - t0
        final_url = page.url
        form_count = info.get('formCount', 0)
        field_count = sum(len(f.get('fields', [])) for f in info.get('forms', []))

        entry['form_path'] = final_url
        entry['form_fields'] = info.get('forms', [])
        entry['status'] = 'discovered' if form_count > 0 else 'no_form_found'

        print(f"{tag} {name[:40]:40s} {elapsed:4.1f}s  forms={form_count}  fields={field_count}  {entry['status']}")
        results['ok'] += 1

    except (PWTimeout, TimeoutError):
        elapsed = time.monotonic() - t0
        print(f"{tag} {name[:40]:40s} {elapsed:4.1f}s  TIMEOUT")
        entry['status'] = 'timeout'
        results['timeout'] += 1
    except Exception as e:
        print(f"{tag} {name[:40]:40s}  ERR: {str(e)[:60]}")
        entry['status'] = 'error'
        entry['form_fields'] = [{"error": str(e)[:200]}]
        results['error'] += 1
    finally:
        try:
            await page.close()
        except Exception:
            pass


async def main():
    with open('submission_plan.json') as f:
        plan = json.load(f)

    # Only discover for entries not yet done
    todo = [e for e in plan if e.get('status') in ('pending', None)]
    total = len(todo)
    print(f"Discovering forms for {total} directories with {WORKERS} workers")

    results = {'ok': 0, 'timeout': 0, 'error': 0}
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
                await check_one(context, entry, seq_num, total, results)

        tasks = [worker(e, i + 1) for i, e in enumerate(todo)]
        await asyncio.gather(*tasks)
        await browser.close()

    # Save updated plan
    with open('submission_plan.json', 'w') as f:
        json.dump(plan, f, indent=2)

    # Summary
    from collections import Counter
    statuses = Counter(e.get('status') for e in plan)
    print(f"\n=== DONE === ok={results['ok']}  timeout={results['timeout']}  error={results['error']}")
    print("Plan status:", "  ".join(f"{k}:{v}" for k, v in statuses.most_common()))


if __name__ == '__main__':
    asyncio.run(main())
