"""
normalize_titles.py — Post title auditor and normalizer for nailosmetic.com.

Finds and repairs broken or substandard post titles:
  1. All lowercase (e.g., "fall nails red burgundy")
  2. Uncapitalized starting word
  3. Outdated years (e.g., title mentions "2024" or "2025" but was published in 2026)
  4. Length check: Under 30 characters (too short for SEO) or over 60 characters (truncates in SERPs)
  5. Unescaped HTML entities (e.g., &amp;, &#8217;, &#038;)
  6. Whitespace or punctuation artifacts

Modes:
  - Default (dry run / read-only): Scans posts, reports findings, generates Markdown + CSV reports. Zero changes made.
  - --apply: Connects to WordPress REST API, updates titles, and logs every single change to an audit log file.
  - --only-lowercase: When applying, targets ONLY the lowercase-title fixes (skips year mismatches and length flags).

Usage:
  # 1. Audit only (Safe read-only):
  python wordpress_automation/normalize_titles.py

  # 2. Target only lowercase titles in apply mode:
  python wordpress_automation/normalize_titles.py --apply --only-lowercase --yes
"""

import argparse
import base64
import csv
from datetime import datetime
from html import unescape
import io
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import requests

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, io.UnsupportedOperation):
        pass

LOWERCASE_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "in", "nor", "of",
    "on", "or", "per", "the", "to", "vs", "via", "with", "without"
}

ALWAYS_UPPERCASE = {
    "diy", "faq", "faqs", "y2k", "3d", "4d", "led", "uv", "hd", "bb", "cc"
}


def clean_html_entities(text: str) -> str:
    """Decodes HTML entities and common encoding mojibake."""
    if not text:
        return ""
    text = unescape(text)
    replacements = {
        "&#8217;": "'",
        "&#8216;": "'",
        "&#8220;": '"',
        "&#8221;": '"',
        "&#8211;": "–",
        "&#8212;": "—",
        "&#038;": "&",
        "&amp;": "&",
        "â€™": "'",
        "â€œ": '"',
        "â€": '"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip()


def suggest_normalized_title(title: str, pub_year: str = "2026") -> str:
    """
    Generates a clean, professional Title Cased version of the title
    and updates outdated years to the publication/current year.
    """
    cleaned = clean_html_entities(title)
    
    # 1. Update outdated years (e.g. 2023, 2024, 2025 -> pub_year or 2026)
    target_year = pub_year if pub_year and pub_year.isdigit() else "2026"
    cleaned = re.sub(r"\b20[12][0-5]\b", target_year, cleaned)

    # 2. Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 3. Smart title-casing
    words = cleaned.split(" ")
    title_words = []
    
    for i, word in enumerate(words):
        # Strip outer punctuation for casing check while keeping it for display
        match = re.match(r"^([^\w]*)(.*?)([^\w]*)$", word)
        if not match:
            title_words.append(word)
            continue
            
        prefix, core, suffix = match.groups()
        core_lower = core.lower()
        
        if core_lower in ALWAYS_UPPERCASE:
            cased = core.upper()
        elif i == 0 or i == len(words) - 1:
            # First and last words are always capitalized
            cased = core.capitalize()
        elif core_lower in LOWERCASE_WORDS:
            cased = core_lower
        elif "-" in core:
            # Handle hyphenated words like "Spider-Web" or "Rose-Gold"
            subparts = [p.capitalize() if p.lower() not in LOWERCASE_WORDS else p.lower() for p in core.split("-")]
            cased = "-".join(subparts)
        else:
            cased = core.capitalize()
            
        title_words.append(f"{prefix}{cased}{suffix}")

    fixed = " ".join(title_words)
    fixed = re.sub(r"\s+([,.:;?!])", r"\1", fixed)
    return fixed


def analyze_title(title: str, date_str: str = "") -> List[str]:
    """
    Analyzes a title and returns a list of detected issues.
    Includes:
      - All lowercase
      - Starts with lowercase
      - Outdated year
      - Title length under 30 chars or over 60 chars
      - HTML entity / mojibake artifacts
      - Whitespace / trailing punctuation
    """
    issues = []
    cleaned = clean_html_entities(title)

    # Check publication year
    pub_year = "2026"
    if date_str:
        m = re.match(r"^(20\d\d)", date_str)
        if m:
            pub_year = m.group(1)

    # 1. All lowercase check
    alpha_chars = [c for c in title if c.isalpha()]
    if alpha_chars and all(c.islower() for c in alpha_chars):
        issues.append("ALL_LOWERCASE: Entire title is lowercase with no capital letters.")

    # 2. Starts with lowercase
    first_alpha = next((c for c in title if c.isalpha()), None)
    if first_alpha and first_alpha.islower() and "ALL_LOWERCASE" not in str(issues):
        issues.append("STARTS_LOWERCASE: First letter is lowercase.")

    # 3. Outdated year check
    years_in_title = re.findall(r"\b(20[12]\d)\b", title)
    for y in years_in_title:
        if y < pub_year:
            issues.append(f"OUTDATED_YEAR: Mentions '{y}' but post was published in '{pub_year}'.")
        elif y < "2026":
            issues.append(f"PAST_YEAR: Mentions past year '{y}'.")

    # 4. Title Length Check (<30 chars or >60 chars)
    title_len = len(cleaned)
    if title_len < 30:
        issues.append(f"TOO_SHORT: Title is {title_len} chars (<30 chars, weak for SEO).")
    elif title_len > 60:
        issues.append(f"TOO_LONG: Title is {title_len} chars (>60 chars, may truncate in Google SERPs).")

    # 5. Raw HTML entities or encoding artifacts
    if re.search(r"&#\d+;|&[a-zA-Z]+;|â[€\x80-\xbf]", title):
        issues.append("HTML_OR_MOJIBAKE: Contains unrendered HTML entities or mojibake characters.")

    # 6. Consecutive whitespace or dangling punctuation
    if re.search(r"\s{2,}", title):
        issues.append("DOUBLE_WHITESPACE: Contains redundant consecutive spaces.")
    if re.search(r"[-–—]\s*$", title):
        issues.append("TRAILING_HYPHEN: Ends with dangling dash or hyphen.")

    return issues


def fetch_posts_from_csv(csv_path: Path) -> List[Dict]:
    """Loads posts from local triage CSV."""
    if not csv_path.exists():
        return []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def fetch_posts_from_json(json_path: Path) -> List[Dict]:
    """Loads posts from published_links.json."""
    if not json_path.exists():
        return []
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        posts = []
        for item in data:
            posts.append({
                "id": "",
                "title": item.get("topic") or item.get("title", ""),
                "link": item.get("url", ""),
                "date": "2026-01-01",
                "slug": item.get("slug", "")
            })
        return posts


def fetch_posts_from_api(base_url: str = "https://nailosmetic.com") -> List[Dict]:
    """Fetches all published posts via the public WordPress REST API."""
    posts = []
    page = 1
    per_page = 100
    print(f"🌐 Fetching live posts from {base_url}/wp-json/wp/v2/posts...")

    while True:
        try:
            url = f"{base_url.rstrip('/')}/wp-json/wp/v2/posts"
            resp = requests.get(url, params={"page": page, "per_page": per_page, "status": "publish"}, timeout=20)
            if resp.status_code == 400:  # Past last page
                break
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            for p in batch:
                title_raw = p.get("title", {}).get("rendered", "") if isinstance(p.get("title"), dict) else str(p.get("title", ""))
                posts.append({
                    "id": str(p.get("id", "")),
                    "title": clean_html_entities(title_raw),
                    "link": p.get("link", ""),
                    "date": p.get("date", "")[:10],
                    "slug": p.get("slug", "")
                })
            sys.stdout.write(f"\r   Fetched {len(posts)} posts so far...")
            sys.stdout.flush()
            total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
            if page >= total_pages:
                break
            page += 1
        except Exception as e:
            print(f"\n   ⚠️ API fetch error on page {page}: {e}")
            break

    print(f"\n   ✅ Fetched total {len(posts)} posts from WP API.")
    return posts


def apply_title_fixes_to_wordpress(
    items_to_fix: List[Dict],
    wp_url: str,
    wp_user: str,
    wp_pass: str,
    log_file: Path,
    csv_file: Optional[Path] = None,
    json_file: Optional[Path] = None
) -> Tuple[int, int]:
    """
    Applies recommended title fixes to WordPress via the REST API
    and logs every single change to an audit CSV file.
    Returns (success_count, fail_count).
    """
    api_url = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
    auth_header = base64.b64encode(f"{wp_user}:{wp_pass}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/json"
    }

    log_file.parent.mkdir(parents=True, exist_ok=True)
    write_header = not log_file.exists() or log_file.stat().st_size == 0

    log_fp = open(log_file, "a", encoding="utf-8", newline="")
    log_writer = csv.writer(log_fp)
    if write_header:
        log_writer.writerow([
            "timestamp", "post_id", "slug", "link",
            "old_title", "new_title", "status", "http_status", "error"
        ])
        log_fp.flush()

    successes = 0
    failures = 0
    updated_map = {}  # id -> new_title

    print(f"\n🚀 Applying fixes to {len(items_to_fix)} posts on WordPress ({wp_url})...\n")

    for i, item in enumerate(items_to_fix, 1):
        post_id = str(item.get("id", "")).strip()
        old_title = item.get("current_title", "")
        new_title = item.get("suggested_title", "")
        slug = item.get("slug", "")
        link = item.get("link", "")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not post_id or not post_id.isdigit():
            print(f"[{i:02d}/{len(items_to_fix)}] ⚠️ SKIP (No valid Post ID): '{old_title}'")
            log_writer.writerow([now_str, post_id, slug, link, old_title, new_title, "SKIPPED_NO_ID", "", "Missing numeric post ID"])
            log_fp.flush()
            failures += 1
            continue

        payload = {
            "title": new_title,
            "meta": {
                "rank_math_title": new_title,
                "_yoast_wpseo_title": new_title
            }
        }

        try:
            target_url = f"{api_url}/{post_id}"
            resp = requests.post(target_url, headers=headers, json=payload, timeout=25)
            
            if resp.status_code == 200:
                print(f"[{i:02d}/{len(items_to_fix)}] ✅ [ID: {post_id}] SUCCESS")
                print(f"       Old: \"{old_title}\"")
                print(f"       New: \"{new_title}\"")
                log_writer.writerow([now_str, post_id, slug, link, old_title, new_title, "SUCCESS", resp.status_code, ""])
                log_fp.flush()
                successes += 1
                updated_map[post_id] = new_title
            else:
                err_text = resp.text[:200].replace("\n", " ")
                print(f"[{i:02d}/{len(items_to_fix)}] ❌ [ID: {post_id}] FAILED (HTTP {resp.status_code}): {err_text}")
                log_writer.writerow([now_str, post_id, slug, link, old_title, new_title, "FAILED", resp.status_code, err_text])
                log_fp.flush()
                failures += 1

            # Pacing delay to avoid server rate-limiting
            time.sleep(1)

        except Exception as e:
            print(f"[{i:02d}/{len(items_to_fix)}] ❌ [ID: {post_id}] ERROR: {e}")
            log_writer.writerow([now_str, post_id, slug, link, old_title, new_title, "ERROR", "", str(e)])
            log_fp.flush()
            failures += 1

    log_fp.close()

    # Synchronize local CSV if present
    if csv_file and csv_file.exists() and updated_map:
        try:
            rows = []
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for r in reader:
                    pid = r.get("id", "")
                    if pid in updated_map:
                        r["title"] = updated_map[pid]
                    rows.append(r)
            with open(csv_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"   🔄 Updated local cache: {csv_file}")
        except Exception as e:
            print(f"   ⚠️ Could not update local CSV: {e}")

    # Synchronize local published_links.json if present
    if json_file and json_file.exists() and updated_map:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                p_links = json.load(f)
            changed_json = False
            for item in p_links:
                for pid, new_t in updated_map.items():
                    if item.get("slug") and any(x.get("slug") == item.get("slug") and x.get("id") == pid for x in items_to_fix):
                        item["topic"] = new_t
                        changed_json = True
            if changed_json:
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(p_links, f, indent=2)
                print(f"   🔄 Updated local cache: {json_file}")
        except Exception as e:
            print(f"   ⚠️ Could not update published_links.json: {e}")

    return (successes, failures)


def main():
    root_dir = Path(__file__).parent.parent
    load_dotenv(root_dir / ".env")

    parser = argparse.ArgumentParser(description="Audit and normalize post titles on nailosmetic.com.")
    parser.add_argument("--source", choices=["auto", "api", "csv", "json"], default="auto",
                        help="Data source: 'auto', 'api', 'csv', or 'json'.")
    parser.add_argument("--csv-path", default="triage_output/all_posts.csv", help="Path to all_posts.csv.")
    parser.add_argument("--output-dir", default="triage_output", help="Directory where reports are written.")
    parser.add_argument("--apply", action="store_true",
                        help="APPLY mode: Modifies titles on WordPress via REST API and logs every change.")
    parser.add_argument("--only-lowercase", action="store_true",
                        help="Target ONLY lowercase titles during --apply (skips year mismatches and length-only flags).")
    parser.add_argument("--filter", choices=["all", "lowercase", "years"], default="all",
                        help="Filter target issue types (default: 'all').")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip interactive confirmation when running --apply.")
    parser.add_argument("--log-file", default="triage_output/title_changes_log.csv",
                        help="Path to audit log CSV file.")
    args = parser.parse_args()

    csv_file = root_dir / args.csv_path
    json_file = root_dir / "shared" / "published_links.json"
    out_dir = root_dir / args.output_dir
    log_file = root_dir / args.log_file
    out_dir.mkdir(parents=True, exist_ok=True)

    posts = []
    source_used = ""

    if args.source == "api":
        posts = fetch_posts_from_api()
        source_used = "WordPress REST API (Live)"
    elif args.source == "csv":
        posts = fetch_posts_from_csv(csv_file)
        source_used = f"Local CSV ({csv_file.name})"
    elif args.source == "json":
        posts = fetch_posts_from_json(json_file)
        source_used = f"Local JSON ({json_file.name})"
    else:  # auto
        if csv_file.exists():
            posts = fetch_posts_from_csv(csv_file)
            source_used = f"Local CSV cache ({csv_file.name})"
        else:
            posts = fetch_posts_from_api()
            source_used = "WordPress REST API (Live)"
            if not posts and json_file.exists():
                posts = fetch_posts_from_json(json_file)
                source_used = f"Local JSON fallback ({json_file.name})"

    if not posts:
        print("❌ No posts found. Try running with --source api or make sure triage_output/all_posts.csv exists.")
        sys.exit(1)

    print(f"\n🔍 Auditing {len(posts)} posts from {source_used} for title issues...\n")

    bad_posts = []
    fixable_posts = []
    all_lowercase_count = 0
    outdated_year_count = 0
    too_short_count = 0
    too_long_count = 0
    other_issues_count = 0

    for p in posts:
        title = p.get("title", "")
        date_str = p.get("date", "2026-01-01")
        pub_year = date_str[:4] if date_str else "2026"

        issues = analyze_title(title, date_str)
        if issues:
            fixed_title = suggest_normalized_title(title, pub_year)
            item = {
                "id": p.get("id", ""),
                "slug": p.get("slug", ""),
                "link": p.get("link", ""),
                "date": date_str,
                "current_title": title,
                "issues": issues,
                "suggested_title": fixed_title
            }
            bad_posts.append(item)

            if fixed_title != title:
                fixable_posts.append(item)

            has_lower = any("LOWERCASE" in i for i in issues)
            has_year = any("YEAR" in i for i in issues)
            has_short = any("TOO_SHORT" in i for i in issues)
            has_long = any("TOO_LONG" in i for i in issues)

            if has_lower:
                all_lowercase_count += 1
            if has_year:
                outdated_year_count += 1
            if has_short:
                too_short_count += 1
            if has_long:
                too_long_count += 1
            if not (has_lower or has_year or has_short or has_long):
                other_issues_count += 1

    mode_label = "EXECUTION MODE (--apply)" if args.apply else "READ-ONLY AUDIT (NO CHANGES MADE)"
    print("=" * 80)
    print(f"📊 TITLE AUDIT SUMMARY — {mode_label}")
    print("=" * 80)
    print(f"Total Posts Audited              : {len(posts)}")
    print(f"Total Flagged Title Issues       : {len(bad_posts)}")
    print(f"  • All / starts lowercase       : {all_lowercase_count}")
    print(f"  • Outdated year mismatch       : {outdated_year_count}")
    print(f"  • Under 30 characters (too short): {too_short_count}")
    print(f"  • Over 60 characters (too long) : {too_long_count}")
    print(f"  • HTML / format artifacts      : {other_issues_count}")
    print(f"Posts with Casing/Year Fix Ready : {len(fixable_posts)}")
    print("=" * 80)

    # Filter target posts if requested
    target_posts = list(fixable_posts)
    if args.only_lowercase or args.filter == "lowercase":
        target_posts = [p for p in target_posts if any("LOWERCASE" in i for i in p["issues"]) and not any("YEAR" in i for i in p["issues"])]
        print(f"\n🎯 FILTER ACTIVE: Targeting ONLY {len(target_posts)} lowercase titles (skipping year mismatches and length-only flags).")
    elif args.filter == "years":
        target_posts = [p for p in target_posts if any("YEAR" in i for p in target_posts for i in p["issues"])]
        print(f"\n🎯 FILTER ACTIVE: Targeting ONLY {len(target_posts)} year mismatch titles.")

    # Print sample of targets
    print("\nSAMPLE OF TARGETED TITLES:")
    print("-" * 80)
    for i, item in enumerate(target_posts[:25], 1):
        print(f"[{i:02d}] ID: {item['id'] or 'N/A'} | Date: {item['date']} | Len: {len(item['current_title'])} chars")
        print(f"     ❌ Current   : {item['current_title']}")
        print(f"     ✅ Suggested : {item['suggested_title']}")
        print(f"     ⚠️  Issues    : {', '.join(item['issues'])}")
        print(f"     🔗 Link      : {item['link']}")
        print()

    if len(target_posts) > 25:
        print(f"... and {len(target_posts) - 25} more items.")

    # Write Markdown Report
    md_path = out_dir / "bad_titles_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 🏷️ Nailosmetic Post Titles SEO & Formatting Audit Report\n\n")
        f.write(f"- **Generated At**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **Data Source**: {source_used}\n")
        f.write(f"- **Total Posts Audited**: {len(posts)}\n")
        f.write(f"- **Total Flagged Titles**: {len(bad_posts)}\n")
        f.write(f"  - **All/Starts Lowercase**: {all_lowercase_count}\n")
        f.write(f"  - **Outdated Year**: {outdated_year_count}\n")
        f.write(f"  - **Under 30 Chars**: {too_short_count}\n")
        f.write(f"  - **Over 60 Chars**: {too_long_count}\n\n")
        status_note = "**APPLIED TO WORDPRESS**" if args.apply else "**READ-ONLY** (No titles modified)"
        f.write(f"> **STATUS**: {status_note}.\n\n")
        f.write("## 📋 Flagged Titles and Recommended Fixes\n\n")
        f.write("| ID | Date | Length | Current Title | Recommended Clean Title | Issues Detected | Link |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for item in bad_posts:
            issues_str = "<br>".join(item["issues"]).replace("|", "-")
            curr = item["current_title"].replace("|", "-")
            sugg = item["suggested_title"].replace("|", "-")
            link_md = f"[View]({item['link']})" if item["link"] else "N/A"
            f.write(f"| {item['id']} | {item['date']} | {len(item['current_title'])} | {curr} | **{sugg}** | {issues_str} | {link_md} |\n")

    # Write CSV Report
    csv_report_path = out_dir / "bad_titles.csv"
    with open(csv_report_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "date", "length", "slug", "link", "current_title", "suggested_title", "issues"])
        for item in bad_posts:
            writer.writerow([
                item["id"],
                item["date"],
                len(item["current_title"]),
                item["slug"],
                item["link"],
                item["current_title"],
                item["suggested_title"],
                " | ".join(item["issues"])
            ])

    print(f"\n💾 Full reports saved:")
    print(f"   📄 Markdown Report : {md_path}")
    print(f"   📊 CSV Data Export : {csv_report_path}")

    # Handle --apply mode
    if args.apply:
        wp_url = os.getenv("WORDPRESS_URL")
        wp_user = os.getenv("WORDPRESS_USER")
        wp_pass = os.getenv("WORDPRESS_APP_PASSWORD")

        if not wp_url or not wp_user or not wp_pass:
            print("\n❌ Missing WordPress credentials in .env (WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_APP_PASSWORD).")
            print("   Cannot run --apply mode without valid credentials.")
            sys.exit(1)

        if not target_posts:
            print("\n✨ No targeted titles require changes.")
            return

        if not args.yes:
            print(f"\n⚠️  CONFIRMATION REQUIRED:")
            print(f"   You are about to modify {len(target_posts)} post titles on live WordPress ({wp_url}).")
            print(f"   Every change will be logged to: {log_file}")
            confirm = input("   Proceed with updating WordPress titles? [y/N]: ").strip().lower()
            if confirm not in ("y", "yes"):
                print("   ❌ Operation cancelled by user. No changes were made.")
                return

        succ, fail = apply_title_fixes_to_wordpress(
            items_to_fix=target_posts,
            wp_url=wp_url,
            wp_user=wp_user,
            wp_pass=wp_pass,
            log_file=log_file,
            csv_file=csv_file,
            json_file=json_file
        )

        print("=" * 80)
        print(f"🏁 APPLY COMPLETE")
        print(f"   ✅ Successfully Updated : {succ}")
        print(f"   ❌ Failed / Skipped     : {fail}")
        print(f"   📝 Detailed Audit Log   : {log_file}")
        print("=" * 80)
    else:
        print(f"\n🔒 Dry run finished. Zero changes were made to WordPress.")
        print(f"   To apply the fixes and record the audit log, run with:")
        print(f"   python wordpress_automation/normalize_titles.py --apply --only-lowercase\n")


if __name__ == "__main__":
    main()
