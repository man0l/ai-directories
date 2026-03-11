#!/usr/bin/env python3
"""
Categorize obviously broken entries and prepare a list for browser verification.
"""
import json
import re
from urllib.parse import urlparse

with open('directories.json', 'r') as f:
    data = json.load(f)

fixed = 0
browser_check = []

for i, d in enumerate(data):
    url = d.get('submission_url', '')
    err = d.get('analysis_error', '')
    status = d.get('site_status', '')
    
    # 1. Invalid URLs (contain descriptions, not real URLs)
    if not url.startswith('http') or ' ' in url or '**' in url or '"' in url:
        data[i]['site_status'] = 'invalid_url'
        data[i]['auth_type'] = 'unknown'
        data[i]['captcha_type'] = 'unknown'
        fixed += 1
        continue
    
    # 2. Facebook groups - these require Facebook login
    if 'facebook.com/groups/' in url:
        data[i]['site_status'] = 'facebook_group'
        data[i]['auth_type'] = 'facebook'
        data[i]['captcha_type'] = 'none'
        data[i]['requires_login'] = True
        fixed += 1
        continue
    
    # 3. DNS resolution failures (dead domains)
    if 'Name or service not known' in err or 'No address associated' in err or 'Temporary failure in name resolution' in err:
        data[i]['site_status'] = 'domain_dead'
        data[i]['auth_type'] = 'unknown'
        data[i]['captcha_type'] = 'unknown'
        fixed += 1
        continue
    
    # 4. HTTP 404 - page not found
    if err == 'HTTP 404':
        data[i]['site_status'] = 'not_found'
        fixed += 1
        continue
    
    # 5. Timeout errors
    if 'timed out' in err:
        data[i]['site_status'] = 'timeout'
        fixed += 1
        continue
    
    # If still needs checking, add to browser list
    if d.get('auth_type') == 'unknown' or status == 'error':
        browser_check.append((i, d['name'], url, err))

# Save updated JSON
with open('directories.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"Auto-fixed: {fixed} entries")
print(f"Need browser check: {len(browser_check)} entries")
print()

# Status summary
statuses = {}
for d in data:
    s = d.get('site_status', 'unknown')
    statuses[s] = statuses.get(s, 0) + 1
print("Updated status counts:")
for k, v in sorted(statuses.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print(f"\n--- Browser check list ({len(browser_check)} sites) ---")
for idx, name, url, err in browser_check:
    print(f"  [{idx:3d}] {name:40s} | {url[:70]:70s} | {err[:30]}")

# Save browser check list for easy reference
with open('browser_check_list.json', 'w') as f:
    json.dump([{'index': idx, 'name': name, 'url': url, 'error': err} for idx, name, url, err in browser_check], f, indent=2)
