#!/usr/bin/env python3
"""
Analyze AI directory submission URLs for authentication type, captcha, and pricing signals.
"""

import json
import re
import time
import ssl
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# Timeout for each request
TIMEOUT = 15

def fetch_url(url):
    """Fetch URL content, following redirects."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
        response = urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)
        final_url = response.geturl()
        content_type = response.headers.get('Content-Type', '')
        
        if 'text/html' not in content_type and 'text/plain' not in content_type and 'application/xhtml' not in content_type:
            return {'final_url': final_url, 'html': '', 'status': response.status, 'error': f'Non-HTML content: {content_type}'}
        
        html = response.read().decode('utf-8', errors='ignore')
        return {'final_url': final_url, 'html': html, 'status': response.status, 'error': None}
    except urllib.error.HTTPError as e:
        return {'final_url': url, 'html': '', 'status': e.code, 'error': f'HTTP {e.code}'}
    except Exception as e:
        return {'final_url': url, 'html': '', 'status': 0, 'error': str(e)[:200]}


def analyze_html(html, url, final_url):
    """Analyze HTML content for auth, captcha, and pricing signals."""
    html_lower = html.lower()
    result = {
        'auth_type': 'unknown',
        'captcha_type': 'none',
        'requires_login': False,
        'signals': [],
    }
    
    # --- Auth type detection ---
    has_google = False
    has_github = False
    has_twitter = False
    has_email_pass = False
    has_login_required = False
    
    # Google OAuth / Sign-in
    google_patterns = [
        r'accounts\.google\.com',
        r'googleapis\.com/auth',
        r'google-signin',
        r'gsi/client',
        r'sign\s*in\s*with\s*google',
        r'login\s*with\s*google',
        r'continue\s*with\s*google',
        r'google\.com/o/oauth',
        r'googleusercontent',
        r'google-login',
        r'auth/google',
        r'oauth/google',
        r'signup.*google',
        r'google.*signup',
        r'btn[_-]google',
        r'social[_-]google',
    ]
    for pat in google_patterns:
        if re.search(pat, html_lower):
            has_google = True
            result['signals'].append(f'google_auth: {pat}')
            break
    
    # GitHub OAuth
    github_patterns = [
        r'github\.com/login/oauth',
        r'sign\s*in\s*with\s*github',
        r'login\s*with\s*github',
        r'continue\s*with\s*github',
        r'auth/github',
        r'oauth/github',
    ]
    for pat in github_patterns:
        if re.search(pat, html_lower):
            has_github = True
            result['signals'].append(f'github_auth: {pat}')
            break
    
    # Twitter/X OAuth
    twitter_patterns = [
        r'api\.twitter\.com/oauth',
        r'sign\s*in\s*with\s*twitter',
        r'login\s*with\s*twitter',
        r'continue\s*with\s*twitter',
        r'auth/twitter',
        r'sign\s*in\s*with\s*x\b',
    ]
    for pat in twitter_patterns:
        if re.search(pat, html_lower):
            has_twitter = True
            result['signals'].append(f'twitter_auth: {pat}')
            break
    
    # Email/Password login
    email_pass_patterns = [
        r'<input[^>]*type=["\']password["\']',
        r'<input[^>]*type=["\']email["\']',
        r'sign\s*up.*email',
        r'create.*account',
        r'register.*account',
    ]
    password_found = bool(re.search(r'<input[^>]*type=["\']password["\']', html_lower))
    email_found = bool(re.search(r'<input[^>]*type=["\']email["\']', html_lower))
    if password_found:
        has_email_pass = True
        result['signals'].append('has_password_field')
    if email_found:
        result['signals'].append('has_email_field')
    
    # Login required signals
    login_signals = [
        r'you\s*must\s*log\s*in',
        r'please\s*log\s*in',
        r'sign\s*in\s*to\s*continue',
        r'login\s*to\s*continue',
        r'sign\s*in\s*to\s*submit',
        r'login\s*required',
        r'create\s*an?\s*account\s*to',
        r'sign\s*up\s*to\s*submit',
    ]
    for pat in login_signals:
        if re.search(pat, html_lower):
            has_login_required = True
            result['signals'].append(f'login_required: {pat}')
            break
    
    # Determine auth_type
    auths = []
    if has_google:
        auths.append('google')
    if has_github:
        auths.append('github')
    if has_twitter:
        auths.append('twitter')
    if has_email_pass:
        auths.append('email_password')
    
    if not auths:
        # Check if there's a form at all (might be free/open submission)
        has_form = bool(re.search(r'<form[^>]*>', html_lower))
        has_submit_button = bool(re.search(r'<(button|input)[^>]*submit', html_lower))
        if has_form:
            result['signals'].append('has_form')
            result['auth_type'] = 'none'
        else:
            # Check for common submit page patterns  
            if re.search(r'submit.*tool|submit.*product|submit.*startup|submit.*site|submit.*url|add.*url|add.*site|list.*tool', html_lower):
                result['signals'].append('has_submit_text')
                result['auth_type'] = 'unknown'
            else:
                result['auth_type'] = 'unknown'
    elif len(auths) == 1 and auths[0] == 'email_password':
        result['auth_type'] = 'email_password'
    elif 'google' in auths and 'email_password' not in auths:
        result['auth_type'] = 'google_only'
    elif 'google' in auths and 'email_password' in auths:
        result['auth_type'] = 'google_and_email'
    else:
        result['auth_type'] = '+'.join(auths)
    
    result['requires_login'] = has_login_required or has_email_pass or has_google or has_github or has_twitter
    
    # --- Captcha detection ---
    # reCAPTCHA v2
    if re.search(r'g-recaptcha|recaptcha/api\.js|grecaptcha', html_lower):
        if re.search(r'recaptcha/api\.js\?.*render=', html_lower) or re.search(r'grecaptcha\.execute', html_lower):
            result['captcha_type'] = 'recaptcha_v3'
        else:
            result['captcha_type'] = 'recaptcha_v2'
        result['signals'].append('recaptcha_detected')
    
    # hCaptcha
    if re.search(r'hcaptcha\.com|h-captcha', html_lower):
        result['captcha_type'] = 'hcaptcha'
        result['signals'].append('hcaptcha_detected')
    
    # Cloudflare Turnstile
    if re.search(r'challenges\.cloudflare\.com/turnstile|cf-turnstile', html_lower):
        result['captcha_type'] = 'cloudflare_turnstile'
        result['signals'].append('turnstile_detected')
    
    # Generic captcha
    if result['captcha_type'] == 'none' and re.search(r'captcha', html_lower):
        result['captcha_type'] = 'captcha_unknown'
        result['signals'].append('generic_captcha_mention')
    
    # --- Pricing signals ---
    pricing_signals = []
    if re.search(r'\$\d+|paid.*submission|premium.*submission|upgrade.*to.*submit|pay.*to.*submit', html_lower):
        pricing_signals.append('paid_signals')
    if re.search(r'free.*submission|submit.*free|free.*listing|no.*cost', html_lower):
        pricing_signals.append('free_signals')
    if re.search(r'freemium|free.*plan|basic.*free|free.*tier', html_lower):
        pricing_signals.append('freemium_signals')
    result['pricing_signals'] = pricing_signals
    
    # --- Page status ---
    # Check if page is a 404 or dead
    if re.search(r'page\s*not\s*found|404\s*error|not\s*found|this\s*page\s*doesn.t\s*exist', html_lower):
        result['signals'].append('page_not_found')
    
    # Check if redirected to homepage / different page
    if final_url and urlparse(final_url).path in ('/', '') and urlparse(url).path not in ('/', ''):
        result['signals'].append('redirected_to_homepage')
    
    return result


def analyze_directory(entry):
    """Analyze a single directory entry."""
    name = entry.get('name', 'Unknown')
    url = entry.get('submission_url', entry.get('url', ''))
    
    if not url:
        return {**entry, 'auth_type': 'unknown', 'captcha_type': 'none', 'analysis_error': 'no_url'}
    
    fetch_result = fetch_url(url)
    
    if fetch_result['error']:
        return {
            **entry,
            'auth_type': 'unknown',
            'captcha_type': 'unknown',
            'site_status': 'error',
            'analysis_error': fetch_result['error'],
        }
    
    analysis = analyze_html(fetch_result['html'], url, fetch_result['final_url'])
    
    updated = {**entry}
    updated['auth_type'] = analysis['auth_type']
    updated['captcha_type'] = analysis['captcha_type']
    updated['requires_login'] = analysis['requires_login']
    if analysis['pricing_signals']:
        updated['pricing_signals'] = analysis['pricing_signals']
    updated['site_status'] = 'active'
    if 'page_not_found' in analysis.get('signals', []):
        updated['site_status'] = 'not_found'
    
    return updated


def main():
    with open('directories.json', 'r') as f:
        directories = json.load(f)
    
    print(f"Analyzing {len(directories)} directories...")
    
    results = [None] * len(directories)
    completed = 0
    
    with ThreadPoolExecutor(max_workers=50) as executor:
        future_to_idx = {}
        for idx, entry in enumerate(directories):
            future = executor.submit(analyze_directory, entry)
            future_to_idx[future] = idx
        
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = {**directories[idx], 'auth_type': 'unknown', 'captcha_type': 'unknown', 'analysis_error': str(e)[:200]}
            completed += 1
            if completed % 20 == 0:
                print(f"  {completed}/{len(directories)} done...")
    
    # Save updated JSON
    with open('directories.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("\n=== SUMMARY ===")
    
    auth_counts = {}
    captcha_counts = {}
    status_counts = {}
    
    for r in results:
        auth = r.get('auth_type', 'unknown')
        auth_counts[auth] = auth_counts.get(auth, 0) + 1
        
        captcha = r.get('captcha_type', 'unknown')
        captcha_counts[captcha] = captcha_counts.get(captcha, 0) + 1
        
        status = r.get('site_status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("\nAuth types:")
    for k, v in sorted(auth_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    
    print("\nCaptcha types:")
    for k, v in sorted(captcha_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    
    print("\nSite status:")
    for k, v in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    
    # List sites with errors
    errors = [r for r in results if r.get('analysis_error')]
    print(f"\nSites with errors: {len(errors)}")
    for r in errors[:10]:
        print(f"  {r['name']}: {r.get('analysis_error', '')[:80]}")
    if len(errors) > 10:
        print(f"  ... and {len(errors) - 10} more")


if __name__ == '__main__':
    main()
