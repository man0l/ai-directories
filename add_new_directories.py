#!/usr/bin/env python3
"""Parse and add new directories from pasted text."""

import json
import re
from urllib.parse import urlparse

# Input data
INPUT_TEXT = """
BetaList	https://betalist.com/	Free (Queue)	
Login Required

F6S	https://www.f6s.com/	Free	
Login Required

Startup Stash	https://startupstash.com/	Free	
Form Submission

Startup Buffer	https://startupbuffer.com/	Free	
Form Submission

Crunchbase	https://www.crunchbase.com/	Free / Paid ($29+)	
Login Required

AngelList (Wellfound)	https://wellfound.com/	Free	Login Required
G2	https://www.g2.com/	Free / Paid	
Login Required

Capterra	https://www.capterra.com/	Free / PPC	Login Required
GetApp	https://www.getapp.com/	Free	Login Required
AlternativeTo	https://alternativeto.net/	Free	Login Required
SaaSHub	https://www.saashub.com/	Free	
Form Submission

Indie Hackers	https://www.indiehackers.com/	Free	
Login Required

Launching Next	https://www.launchingnext.com/	Free	
Form Submission

StartupBase.ai	https://startupbase.ai/	Free	Login Required
Fe/male Switch	https://www.femaleswitch.com/	Application	
Login Required

CrozDesk	https://crozdesk.com/	Free	Form Submission
Software Advice	https://www.softwareadvice.com/	Free	
Login Required

SaaSWorthy	https://www.saasworthy.com/	Free / Paid	Form Submission
AppExchange	https://appexchange.salesforce.com/	Fee-based	
Login Required

KillerStartups	https://www.killerstartups.com/	Paid	
Form Submission

Launched	https://launched.io/	Free	
Form Submission

Robin Good's T5	https://tools.robingood.com/	Free	
Form Submission

Startup Tracker	https://startuptracker.io/	Free	
Form Submission

Startup Inspire	https://www.startupinspire.com/	Free	
Form Submission

Side Projectors	https://www.sideprojectors.com/	Free	
Login Required

10words	https://10words.io/	Free	
Form Submission

Web Design Inspiration	https://www.webdesign-inspiration.com/	Free	
Form Submission

AllTopStartups	https://alltopstartups.com/	Paid	Form Submission
FeedMyStartup	https://feedmystartup.com/	Free	
Form Submission

Get Worm	https://getworm.com/	Free	
Form Submission

Startup88	https://startup88.com/	Free	
Form Submission

Startuplister	https://startuplister.com/	Free	
Form Submission

The Startup INC	https://www.thestartupinc.com/	Free	
Form Submission

ToolSalad	https://toolsalad.com/	Free	
Form Submission

Webwiki	https://www.webwiki.com/	Free	
Form Submission

EU-Startups	https://www.eu-startups.com/	Free	
Form Submission

The Startup Pitch	https://thestartuppitch.com/	Free	
Form Submission

NoCodeList	https://nocodelist.co/	Free	
Form Submission

NoCodeDevs	https://www.nocodedevs.com/	Paid	
Login Required

ActiveSearchResults	https://www.activesearchresults.com/	Free	
Form Submission

AppRater	https://apprater.net/	Free	
Form Submission

AppsThunder	https://appsthunder.com/	Paid	
Form Submission

AwesomeIndie	https://awesomeindie.com/	Free	
Form Submission

CrowdReviews	https://www.crowdreviews.com/	Free	
Form Submission

Alternative Me	https://alternative.me/	Free	
Form Submission

SoftwareSuggest	https://www.softwaresuggest.com/	Free	
Form Submission

SoftwareWorld	https://www.softwareworld.co/	Free	
Form Submission

Cloudfindr	https://www.cloudfindr.co/	Free	
Form Submission

MicroLaunch	https://microlaunch.net/	Free	
Form Submission

EzWebDirectory	https://ezwebdirectory.com/	Free	
Form Submission

SubmissionWebDirectory	https://www.submissionwebdirectory.com/	Free	
Form Submission

SoMuch	https://somuch.com/	Free	
Form Submission

Build in Public	https://buildinpublic.page/	Paid	
Form Submission

Hand Picked Tools	https://handpickedtools.com/	Paid	
Form Submission

IndieHackerStacks	https://indiehackerstacks.com/	Free	
Login Required

Uneed	https://www.uneed.best/	Free / Featured	
Form Submission

PayOnceApps	https://payonceapps.com/	Free	
Form Submission

Buy Me a Coffee	https://buymeacoffee.com/	Free	
Login Required

Startups.fyi	https://www.startups.fyi/	Free	
Form Submission

BizRaw	https://bizraw.com/	Free	
Form Submission

Toolio	https://www.toolio.ai/	Paid	
Form Submission

SaaS AI Tools	https://saasaitools.com/	Free	Form Submission
Insanely Cool Tools	https://insanelycooltools.com/	Paid	
Form Submission

Startup Fame	https://startupfa.me/	Free	
Login Required

Failory	https://www.failory.com/	Free	
Form Submission

Best of Web	https://botw.org/	Free / Backlink	
Form Submission
"""


def normalize_url(url):
    """Normalize URL for comparison."""
    parsed = urlparse(url.lower().strip())
    domain = parsed.netloc
    path = parsed.path.rstrip('/')
    return f"{domain}{path}"


def create_slug(name):
    """Create a slug from name."""
    slug = name.lower()
    slug = re.sub(r"['\(\)\.]+", "", slug)  # Remove special chars
    slug = re.sub(r"[^a-z0-9]+", "-", slug)  # Replace non-alphanumeric with hyphens
    slug = slug.strip('-')
    return slug


def parse_pricing(pricing_text):
    """Determine pricing type from text."""
    pricing_lower = pricing_text.lower()
    if 'paid' in pricing_lower and 'free' not in pricing_lower:
        return 'paid'
    elif 'fee' in pricing_lower or '$' in pricing_text:
        return 'paid'
    else:
        return 'free'


def parse_input():
    """Parse the input text into directory entries."""
    entries = []
    lines = INPUT_TEXT.strip().split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # Look for pattern: Name\tURL\tPricing info
        parts = [p.strip() for p in line.split('\t') if p.strip()]
        
        if len(parts) >= 2 and parts[1].startswith('http'):
            name = parts[0]
            url = parts[1]
            pricing = parts[2] if len(parts) > 2 else 'Free'
            
            # Check next line for auth info
            auth_info = ''
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not '\t' in next_line and 'http' not in next_line.lower():
                    auth_info = next_line
                    i += 1  # Skip this line next iteration
            
            entry = {
                'name': name,
                'url': url,
                'pricing': pricing,
                'auth_info': auth_info
            }
            entries.append(entry)
        
        i += 1
    
    return entries


def main():
    """Main function to add new directories."""
    print("=" * 60)
    print("ADDING NEW DIRECTORIES")
    print("=" * 60)
    
    # Load existing directories
    with open('directories.json', 'r') as f:
        existing_dirs = json.load(f)
    
    print(f"\n✓ Loaded {len(existing_dirs)} existing directories")
    
    # Build lookup sets for deduplication
    existing_urls = set()
    existing_domains = set()
    existing_names = set()
    
    for d in existing_dirs:
        if 'url' in d:
            existing_urls.add(normalize_url(d['url']))
            domain = urlparse(d['url']).netloc.lower()
            existing_domains.add(domain)
        if 'name' in d:
            existing_names.add(d['name'].lower())
    
    # Parse input
    parsed_entries = parse_input()
    print(f"✓ Parsed {len(parsed_entries)} entries from input")
    
    # Deduplicate and create new entries
    new_entries = []
    duplicates = []
    
    for entry in parsed_entries:
        url_normalized = normalize_url(entry['url'])
        domain = urlparse(entry['url']).netloc.lower()
        name_lower = entry['name'].lower()
        
        # Check for duplicates
        if url_normalized in existing_urls:
            duplicates.append((entry['name'], 'URL match'))
            continue
        elif domain in existing_domains:
            duplicates.append((entry['name'], 'Domain match'))
            continue
        elif name_lower in existing_names:
            duplicates.append((entry['name'], 'Name match'))
            continue
        
        # Create new entry
        new_entry = {
            "categories": ["General"],
            "description": "",
            "is_active": True,
            "name": entry['name'],
            "pricing_type": parse_pricing(entry['pricing']),
            "slug": create_slug(entry['name']),
            "submission_url": entry['url'],
            "url": entry['url']
        }
        
        new_entries.append(new_entry)
        
        # Update lookup sets
        existing_urls.add(url_normalized)
        existing_domains.add(domain)
        existing_names.add(name_lower)
    
    # Report duplicates
    if duplicates:
        print(f"\n⚠ Skipped {len(duplicates)} duplicates:")
        for name, reason in duplicates[:10]:
            print(f"  - {name} ({reason})")
        if len(duplicates) > 10:
            print(f"  ... and {len(duplicates) - 10} more")
    
    # Add new entries
    if new_entries:
        existing_dirs.extend(new_entries)
        
        # Save updated file
        with open('directories.json', 'w') as f:
            json.dump(existing_dirs, f, indent=2)
        
        print(f"\n✓ Added {len(new_entries)} new directories")
        print(f"✓ Total directories: {len(existing_dirs)}")
        
        # Show sample of added
        print("\nSample of added directories:")
        for entry in new_entries[:5]:
            print(f"  - {entry['name']} ({entry['url']})")
        if len(new_entries) > 5:
            print(f"  ... and {len(new_entries) - 5} more")
    else:
        print("\n⚠ No new directories to add (all were duplicates)")
    
    print("\n" + "=" * 60)
    return len(new_entries)


if __name__ == "__main__":
    count = main()
    exit(0 if count > 0 else 1)
