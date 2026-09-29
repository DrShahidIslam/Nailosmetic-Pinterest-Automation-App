"""
apply_redirects.py — 301 Redirect Implementation & Internal Link Updater for Nailosmetic.

Context:
  Implements the 20 Google Search Console (GSC) verified 301 redirect pairs
  for cannibalized/thin posts using the WordPress "Redirection" plugin (by John Godley)
  already installed on nailosmetic.com.

The 20 Approved Pairs (loser -> survivor):
   1. halloween-nail-ideas -> trendy-halloween-nails
   2. pumpkin-spice-nail-designs -> fall-pumpkin-nail-designs
   3. easy-homecoming-hairstyles -> simple-hoco-hairstyles
   4. hair-styles-for-hoco -> simple-hoco-hairstyles
   5. early-autumn-nails -> fall-nails-inspo-2026
   6. fall-nails-brown-chrome -> fall-nail-inspo-brown
   7. nail-ideas-fall -> fall-themed-nails-simple
   8. fall-pedicure-ideas -> fall-pedicures
   9. bio-adaptive-ph-responsive-gel-manicures -> bio-adaptive-ph-responsive-gel-manicure
  10. bio-synthetic-hybrid-hair-extensions-guide-3 -> bio-synthetic-hybrid-hair-extensions-guide-2
  11. bio-synthetic-hybrid-hair-extensions-guide -> bio-synthetic-hybrid-hair-extensions-guide-2
  12. biophilic-modular-garden-walls-urban-balcony -> biophilic-modular-garden-walls-diy-urban-balcony
  13. spring-nails-french-ideas -> french-tip-nail-designs
  14. 4th-of-july-nails-french-tip -> french-tip-nail-designs
  15. shaggy-bob-haircut-ideas -> shaggy-bob-haircut-for-90s-aesthetic
  16. shaggy-bob-haircut-ideas-2 -> shaggy-bob-haircut-for-90s-aesthetic
  17. minimalist-clean-girl-nails -> clean-girl-nail-looks
  18. front-yard-landscaping-ideas -> flower-bed-ideas-front-house
  19. small-bathroom-makeover-ideas -> small-bathroom-ideas
  20. 3d-nail-art-designs -> creative-3d-aesthetic-nail-art

Protected Slugs (NEVER redirected, NEVER rewritten):
  fourth-of-july-hairstyles, texas-rangers-outfit-guide, cubs-game-outfit-women,
  wash-go-curly-hair-styles, chrome-nails-complete-guide, back-to-school-nails-square,
  september-nail-inspo

Usage:
  # Mode 1: Verify status of all 20 pairs (default, read-only)
  python wordpress_automation/apply_redirects.py --verify

  # Mode 2: Build CSV for Redirection plugin import
  python wordpress_automation/apply_redirects.py --build-csv

  # Mode 3: Verify live redirects after import
  python wordpress_automation/apply_redirects.py --verify-live

  # Internal Link Updater: Dry-run scan across all posts
  python wordpress_automation/apply_redirects.py --update-links

  # Internal Link Updater: Apply link rewrites and bonus title fix live
  python wordpress_automation/apply_redirects.py --update-links --apply
"""

import argparse
import base64
import csv
from html import unescape
import io
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Dict, List, Optional, Set, Tuple
from dotenv import load_dotenv
import requests

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, io.UnsupportedOperation):
        pass

# The 20 approved pairs strictly verified by GSC indexing data (loser -> survivor)
APPROVED_PAIRS: List[Tuple[str, str]] = [
    ("halloween-nail-ideas", "trendy-halloween-nails"),
    ("pumpkin-spice-nail-designs", "fall-pumpkin-nail-designs"),
    ("easy-homecoming-hairstyles", "simple-hoco-hairstyles"),
    ("hair-styles-for-hoco", "simple-hoco-hairstyles"),
    ("early-autumn-nails", "fall-nails-inspo-2026"),
    ("fall-nails-brown-chrome", "fall-nail-inspo-brown"),
    ("nail-ideas-fall", "fall-themed-nails-simple"),
    ("fall-pedicure-ideas", "fall-pedicures"),
    ("bio-adaptive-ph-responsive-gel-manicures", "bio-adaptive-ph-responsive-gel-manicure"),
    ("bio-synthetic-hybrid-hair-extensions-guide-3", "bio-synthetic-hybrid-hair-extensions-guide-2"),
    ("bio-synthetic-hybrid-hair-extensions-guide", "bio-synthetic-hybrid-hair-extensions-guide-2"),
    ("biophilic-modular-garden-walls-urban-balcony", "biophilic-modular-garden-walls-diy-urban-balcony"),
    ("spring-nails-french-ideas", "french-tip-nail-designs"),
    ("4th-of-july-nails-french-tip", "french-tip-nail-designs"),
    ("shaggy-bob-haircut-ideas", "shaggy-bob-haircut-for-90s-aesthetic"),
    ("shaggy-bob-haircut-ideas-2", "shaggy-bob-haircut-for-90s-aesthetic"),
    ("minimalist-clean-girl-nails", "clean-girl-nail-looks"),
    ("front-yard-landscaping-ideas", "flower-bed-ideas-front-house"),
    ("small-bathroom-makeover-ideas", "small-bathroom-ideas"),
    ("3d-nail-art-designs", "creative-3d-aesthetic-nail-art"),
]

# Protected URLs — strictly forbidden from redirection or internal link rewriting
PROTECTED_SLUGS: Set[str] = {
    "fourth-of-july-hairstyles",
    "texas-rangers-outfit-guide",
    "cubs-game-outfit-women",
    "wash-go-curly-hair-styles",
    "chrome-nails-complete-guide",
    "back-to-school-nails-square",
    "september-nail-inspo"
}

# Bonus fix configuration
BONUS_TARGET_SLUG = "creative-3d-aesthetic-nail-art"
BONUS_NEW_TITLE = "3D Nail Art Designs: 15 Creative Ideas for 2026"


def get_base_url() -> str:
    """Returns base WordPress site URL without trailing slash."""
    load_dotenv()
    return os.getenv("WORDPRESS_URL", "https://nailosmetic.com").rstrip("/")


def get_wp_auth_headers() -> Dict[str, str]:
    """Generates Basic Auth headers from .env WordPress credentials."""
    load_dotenv()
    user = os.getenv("WORDPRESS_USER")
    pwd = os.getenv("WORDPRESS_APP_PASSWORD")
    if not user or not pwd:
        return {}
    token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "User-Agent": "Nailosmetic-Redirect-Manager/1.0"
    }


# ==============================================================================
# MODE 1: VERIFY (Read-Only)
# ==============================================================================

def mode_verify(base_url: str) -> List[Dict]:
    """
    HTTP GETs each loser and survivor URL:
      - Loser must return 200 (exists and not already redirected).
      - Survivor must return 200 (live canonical destination).
    Returns list of verification result dictionaries.
    """
    print("\n" + "=" * 90)
    print("🔍 MODE 1: PRE-REDIRECT VERIFICATION (READ-ONLY)")
    print("=" * 90)
    print(f"Base Site URL: {base_url}\n")
    print(f"{'#':<3} | {'Loser URL (Expected: 200)':<44} | {'Survivor URL (Expected: 200)':<42} | {'Status'}")
    print("-" * 105)

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    results = []

    for idx, (loser, survivor) in enumerate(APPROVED_PAIRS, 1):
        if loser in PROTECTED_SLUGS or survivor in PROTECTED_SLUGS:
            print(f"{idx:02d} | {loser:<44} | {survivor:<42} | 🛑 PROTECTED (SKIPPED)")
            continue

        l_url = f"{base_url}/{loser}/"
        s_url = f"{base_url}/{survivor}/"

        try:
            r_loser = requests.get(l_url, headers=headers, allow_redirects=False, timeout=12)
            l_code = r_loser.status_code
        except Exception as e:
            l_code = f"ERR: {type(e).__name__}"

        try:
            r_surv = requests.get(s_url, headers=headers, allow_redirects=False, timeout=12)
            s_code = r_surv.status_code
        except Exception as e:
            s_code = f"ERR: {type(e).__name__}"

        passed = (l_code == 200 and s_code == 200)
        status_str = "✅ PASS (Ready)" if passed else f"⚠️ FAIL ({l_code} -> {s_code})"

        print(f"{idx:02d} | {loser[:43]:<44} | {survivor[:41]:<42} | {status_str}")

        results.append({
            "index": idx,
            "loser": loser,
            "survivor": survivor,
            "loser_url": l_url,
            "survivor_url": s_url,
            "loser_status": l_code,
            "survivor_status": s_code,
            "passed": passed
        })

    passed_count = sum(1 for r in results if r["passed"])
    print("-" * 105)
    print(f"📊 SUMMARY: {passed_count}/{len(APPROVED_PAIRS)} pairs PASSED verification.")
    if passed_count < len(APPROVED_PAIRS):
        print(f"   ⚠️ {len(APPROVED_PAIRS) - passed_count} pairs failed and will be EXCLUDED from CSV generation.")
    else:
        print("   🎉 All 20 pairs verified! Ready for CSV build.")

    return results


# ==============================================================================
# MODE 2: BUILD-CSV (Redirection Plugin Import Format)
# ==============================================================================

def mode_build_csv(base_url: str, verified_results: Optional[List[Dict]] = None) -> Path:
    """
    Generates triage_output/redirection_import.csv in the Redirection plugin's CSV format.
    Specification:
      source,target,regex,code
      source: relative path (e.g. /halloween-nail-ideas/)
      target: full destination URL (e.g. https://nailosmetic.com/trendy-halloween-nails/)
      regex: 0
      code: 301
    """
    if verified_results is None:
        verified_results = mode_verify(base_url)

    valid_pairs = [r for r in verified_results if r["passed"]]

    out_dir = Path(__file__).parent.parent / "triage_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "redirection_import.csv"

    print("\n" + "=" * 90)
    print("📁 MODE 2: GENERATING REDIRECTION PLUGIN IMPORT CSV")
    print("=" * 90)
    print(f"Output File: {csv_path}")

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        # Official Redirection plugin column headers
        writer.writerow(["source", "target", "regex", "code"])
        for item in valid_pairs:
            source_rel = f"/{item['loser']}/"
            target_full = f"{base_url}/{item['survivor']}/"
            writer.writerow([source_rel, target_full, "0", "301"])

    print(f"✅ Generated {len(valid_pairs)} redirect rows in Redirection plugin format.")
    print("\n📋 INSTRUCTIONS FOR SITE OWNER TO IMPORT IN WORDPRESS:")
    print("   1. Log in to WordPress Admin at https://nailosmetic.com/wp-admin/")
    print("   2. In the left navigation menu, go to: Tools -> Redirection")
    print("   3. Click on the 'Import' tab (or 'Import/Export') at top right")
    print("   4. In the 'Import from a file' section, click 'Add File' or drag and drop:")
    print(f"      👉 {csv_path.resolve()}")
    print("   5. Select Group: 'Redirections' (default)")
    print("   6. Click 'Upload' / 'Import'")
    print("   7. Once imported, return to this terminal and run:")
    print("      python wordpress_automation/apply_redirects.py --verify-live\n")

    return csv_path


# ==============================================================================
# MODE 3: VERIFY-LIVE (Post-Import Verification)
# ==============================================================================

def mode_verify_live(base_url: str):
    """
    Runs after the owner imports redirection_import.csv:
      - Requests each loser URL with allow_redirects=False.
      - Asserts status is 301.
      - Asserts Location header redirects to survivor URL.
      - Requests survivor URL and asserts it returns 200.
      - Checks Redirection plugin REST API for active status.
    """
    print("\n" + "=" * 95)
    print("🚀 MODE 3: VERIFY LIVE REDIRECTS (POST-IMPORT AUDIT)")
    print("=" * 95)

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    auth_headers = get_wp_auth_headers()

    # Query Redirection plugin REST API for existing rules
    live_plugin_redirects = {}
    if auth_headers:
        try:
            r = requests.get(f"{base_url}/wp-json/redirection/v1/redirect", headers=auth_headers, timeout=12)
            if r.status_code == 200:
                items = r.json().get("items", [])
                for item in items:
                    u = item.get("url", "").strip("/")
                    live_plugin_redirects[u] = item
                print(f"🔌 Connected to Redirection REST API: {len(live_plugin_redirects)} active rules detected.")
        except Exception as e:
            print(f"   ⚠️ Could not read Redirection REST API: {e}")

    print(f"\n{'#':<3} | {'Loser Slug':<36} | {'Target Status':<15} | {'Location Target':<30} | {'Result'}")
    print("-" * 105)

    pass_count = 0
    for idx, (loser, survivor) in enumerate(APPROVED_PAIRS, 1):
        l_url = f"{base_url}/{loser}/"
        s_url = f"{base_url}/{survivor}/"

        try:
            r_l = requests.get(l_url, headers=headers, allow_redirects=False, timeout=10)
            l_code = r_l.status_code
            target_loc = r_l.headers.get("Location", "")
        except Exception as e:
            l_code = f"ERR"
            target_loc = str(e)

        try:
            r_s = requests.get(s_url, headers=headers, allow_redirects=False, timeout=10)
            s_code = r_s.status_code
        except Exception:
            s_code = "ERR"

        # Check if 301 and target points to survivor
        is_301 = (l_code == 301)
        correct_target = (survivor in target_loc)
        survivor_200 = (s_code == 200)

        in_plugin = (loser in live_plugin_redirects)

        if is_301 and correct_target and survivor_200:
            result_str = "✅ PASS (301 -> 200)"
            pass_count += 1
        else:
            result_str = f"❌ FAIL ({l_code})"

        loc_display = target_loc.replace(base_url, "")[:28] if target_loc else "None"
        print(f"{idx:02d} | {loser[:35]:<36} | HTTP {l_code:<10} | {loc_display:<30} | {result_str}")

    print("-" * 105)
    print(f"📊 LIVE VERIFICATION SUMMARY: {pass_count}/{len(APPROVED_PAIRS)} live redirects verified.")
    if pass_count == len(APPROVED_PAIRS):
        print("🎉 SUCCESS: All 20 redirects are returning live 301s to canonical survivors!")
    else:
        print("⚠️ NOTE: If redirects returned 200, ensure the CSV has been imported into Tools -> Redirection.")


# ==============================================================================
# INTERNAL LINK UPDATER (--update-links)
# ==============================================================================

def scan_and_update_internal_links(base_url: str, apply_changes: bool = False):
    """
    Scans all published posts on nailosmetic.com for internal links pointing to any of
    the 20 loser URLs.
    Matching logic:
      - Matches http:// and https://
      - Matches www. and non-www
      - Matches with and without trailing slash
    Safety:
      - Never touches protected URLs.
      - In dry-run mode: prints every replacement.
      - With apply_changes=True: updates post content via WP REST API with 2-second delay.
      - Updates shared/published_links.json and triage_output/all_posts.csv.
      - Logs every change to triage_output/redirect_log.csv.
    """
    mode_title = "APPLYING LIVE LINK REWRITES" if apply_changes else "DRY-RUN INTERNAL LINK AUDIT (READ-ONLY)"
    print("\n" + "=" * 90)
    print(f"🔗 INTERNAL LINK UPDATER — {mode_title}")
    print("=" * 90)

    auth_headers = get_wp_auth_headers()
    if not auth_headers:
        print("❌ Missing WordPress credentials in .env. Cannot query WP REST API.")
        return

    # Map loser -> survivor
    loser_to_survivor = dict(APPROVED_PAIRS)
    loser_slugs = list(loser_to_survivor.keys())

    # Build regex patterns for each loser URL variant
    # Handles: https?://(?:www\.)?nailosmetic\.com/{loser}(?:/|(?=["'#\s?]))
    url_patterns = {}
    for loser, survivor in loser_to_survivor.items():
        if loser in PROTECTED_SLUGS or survivor in PROTECTED_SLUGS:
            continue
        pat = re.compile(
            rf'(https?://(?:www\.)?nailosmetic\.com)/{re.escape(loser)}(/?)(?=["\'#\s?])',
            re.IGNORECASE
        )
        url_patterns[loser] = (pat, survivor)

    print("📥 Fetching all posts from WordPress REST API...")
    posts = []
    page = 1
    while True:
        try:
            r = requests.get(
                f"{base_url}/wp-json/wp/v2/posts",
                headers=auth_headers,
                params={"per_page": 100, "page": page, "_fields": "id,title,slug,link,content"},
                timeout=25
            )
            if r.status_code == 400 or not r.json():
                break
            r.raise_for_status()
            batch = r.json()
            posts.extend(batch)
            total_pages = int(r.headers.get("X-WP-TotalPages", 1))
            if page >= total_pages:
                break
            page += 1
        except Exception as e:
            print(f"   ⚠️ WP API pagination error on page {page}: {e}")
            break

    print(f"   ✅ Fetched {len(posts)} posts for inspection.\n")

    planned_updates = []
    log_rows = []

    for post in posts:
        post_id = post.get("id")
        title_raw = post.get("title", {}).get("rendered", "")
        post_title = unescape(title_raw)
        post_slug = post.get("slug", "")
        raw_content = post.get("content", {}).get("raw") or post.get("content", {}).get("rendered", "")

        updated_content = raw_content
        post_replacements = []

        for loser, (pat, survivor) in url_patterns.items():
            # Check matches
            matches = pat.findall(updated_content)
            if matches:
                survivor_url = f"{base_url}/{survivor}/"
                for match_prefix, trailing in matches:
                    old_link = f"{match_prefix}/{loser}{trailing}"
                    new_link = f"{base_url}/{survivor}/"
                    post_replacements.append({
                        "post_id": post_id,
                        "post_title": post_title,
                        "post_slug": post_slug,
                        "old_url": old_link,
                        "new_url": new_link,
                        "loser_slug": loser,
                        "survivor_slug": survivor
                    })

                # Perform substitution in content
                def _repl(m, s=survivor):
                    return f"{base_url}/{s}/"

                updated_content = pat.sub(_repl, updated_content)

        if post_replacements:
            planned_updates.append({
                "post_id": post_id,
                "post_title": post_title,
                "post_slug": post_slug,
                "replacements": post_replacements,
                "new_content": updated_content
            })

    total_replacement_instances = sum(len(p["replacements"]) for p in planned_updates)
    print(f"📋 DISCOVERY SUMMARY:")
    print(f"   • Posts containing loser links : {len(planned_updates)}")
    print(f"   • Total link replacement count : {total_replacement_instances}\n")

    print(f"{'Post ID':<8} | {'Post Title':<45} | {'Old Link -> New Link'}")
    print("-" * 105)
    for p in planned_updates:
        title_disp = p["post_title"][:44]
        for rep in p["replacements"]:
            old_disp = rep["old_url"].replace(base_url, "")
            new_disp = rep["new_url"].replace(base_url, "")
            print(f"{p['post_id']:<8} | {title_disp:<45} | {old_disp} -> {new_disp}")
            log_rows.append([
                time.strftime("%Y-%m-%d %H:%M:%S"),
                p["post_id"],
                p["post_title"],
                rep["old_url"],
                rep["new_url"],
                "APPLIED" if apply_changes else "DRY-RUN"
            ])

    # If apply_changes is True, update live posts on WordPress
    if apply_changes:
        print("\n" + "=" * 90)
        print("💾 APPLYING LINK REWRITES TO WORDPRESS VIA REST API")
        print("=" * 90)
        success_count = 0
        fail_count = 0

        for idx, item in enumerate(planned_updates, 1):
            p_id = item["post_id"]
            p_title = item["post_title"]
            print(f"[{idx:02d}/{len(planned_updates)}] Updating Post #{p_id} ('{p_title[:40]}')...")

            try:
                up_resp = requests.post(
                    f"{base_url}/wp-json/wp/v2/posts/{p_id}",
                    headers=auth_headers,
                    json={"content": item["new_content"]},
                    timeout=20
                )
                if up_resp.status_code == 200:
                    print(f"   ✅ Successfully updated links in Post #{p_id}")
                    success_count += 1
                else:
                    print(f"   ❌ WP API error on Post #{p_id}: {up_resp.status_code} - {up_resp.text[:120]}")
                    fail_count += 1
            except Exception as e:
                print(f"   ❌ Exception on Post #{p_id}: {e}")
                fail_count += 1

            # 2-second rate-limiting delay between calls as requested
            time.sleep(2)

        print(f"\n📊 LINK UPDATE COMPLETE: {success_count} posts updated successfully, {fail_count} failed.")

        # Update local published_links.json and all_posts.csv
        update_local_records(loser_to_survivor, base_url)

        # Apply Bonus Title Fix
        apply_bonus_title_fix(base_url, auth_headers)

    # Save log to triage_output/redirect_log.csv
    log_dir = Path(__file__).parent.parent / "triage_output"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "redirect_log.csv"

    file_exists = log_file.exists()
    with open(log_file, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "post_id", "post_title", "old_url", "new_url", "status"])
        for row in log_rows:
            writer.writerow(row)

    print(f"\n📄 Audit details logged to: {log_file}")


def update_local_records(loser_to_survivor: Dict[str, str], base_url: str):
    """
    Replaces loser URLs and slugs with survivor counterparts in:
      - shared/published_links.json
      - triage_output/all_posts.csv
    """
    print("\n📝 Updating local repository records to maintain consistency...")
    root_dir = Path(__file__).parent.parent

    # 1. published_links.json
    pl_path = root_dir / "shared" / "published_links.json"
    if pl_path.exists():
        try:
            with open(pl_path, "r", encoding="utf-8") as f:
                pl_data = json.load(f)

            pl_changed = 0
            for item in pl_data:
                slug = item.get("slug")
                if slug in loser_to_survivor:
                    survivor = loser_to_survivor[slug]
                    item["slug"] = survivor
                    item["url"] = f"{base_url}/{survivor}/"
                    pl_changed += 1

            if pl_changed > 0:
                with open(pl_path, "w", encoding="utf-8") as f:
                    json.dump(pl_data, f, indent=2)
                print(f"   ✅ Updated {pl_changed} entries in shared/published_links.json")
            else:
                print("   ℹ️ No matching loser slugs in shared/published_links.json.")
        except Exception as e:
            print(f"   ⚠️ Could not update published_links.json: {e}")

    # 2. triage_output/all_posts.csv
    csv_path = root_dir / "triage_output" / "all_posts.csv"
    if csv_path.exists():
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = list(csv.DictReader(f))

            csv_changed = 0
            fieldnames = reader[0].keys() if reader else []
            for row in reader:
                slug = row.get("slug")
                if slug in loser_to_survivor:
                    survivor = loser_to_survivor[slug]
                    row["slug"] = survivor
                    row["link"] = f"{base_url}/{survivor}/"
                    csv_changed += 1

            if csv_changed > 0 and fieldnames:
                with open(csv_path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(reader)
                print(f"   ✅ Updated {csv_changed} entries in triage_output/all_posts.csv")
        except Exception as e:
            print(f"   ⚠️ Could not update all_posts.csv: {e}")


def apply_bonus_title_fix(base_url: str, auth_headers: Dict[str, str]):
    """
    Sets the title of creative-3d-aesthetic-nail-art to:
    '3D Nail Art Designs: 15 Creative Ideas for 2026'
    """
    print("\n" + "=" * 90)
    print("🎨 BONUS FIX: UPDATING 3D NAIL ART CANONICAL TITLE")
    print("=" * 90)

    try:
        r = requests.get(
            f"{base_url}/wp-json/wp/v2/posts",
            headers=auth_headers,
            params={"slug": BONUS_TARGET_SLUG, "_fields": "id,title,slug"},
            timeout=15
        )
        if r.status_code == 200 and r.json():
            post_id = r.json()[0]["id"]
            old_title = unescape(r.json()[0]["title"]["rendered"])
            print(f"   Found Post #{post_id} ('{old_title}')")
            print(f"   Updating Title -> '{BONUS_NEW_TITLE}'...")

            up = requests.post(
                f"{base_url}/wp-json/wp/v2/posts/{post_id}",
                headers=auth_headers,
                json={"title": BONUS_NEW_TITLE},
                timeout=15
            )
            if up.status_code == 200:
                print(f"   ✅ Title successfully updated on Post #{post_id}!")
            else:
                print(f"   ❌ Failed to update title: {up.status_code} - {up.text[:100]}")
        else:
            print(f"   ⚠️ Post with slug '{BONUS_TARGET_SLUG}' not found.")
    except Exception as e:
        print(f"   ❌ Error updating bonus title: {e}")


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Nailosmetic 301 Redirect Implementation and Internal Link Updater."
    )
    parser.add_argument(
        "--verify", action="store_true", default=False,
        help="Mode 1: Verify current HTTP status of all 20 pairs (read-only default)."
    )
    parser.add_argument(
        "--build-csv", action="store_true", default=False,
        help="Mode 2: Generate triage_output/redirection_import.csv for Redirection plugin."
    )
    parser.add_argument(
        "--verify-live", action="store_true", default=False,
        help="Mode 3: Verify live 301 responses after plugin import."
    )
    parser.add_argument(
        "--update-links", action="store_true", default=False,
        help="Audit internal links pointing to loser URLs (dry-run by default)."
    )
    parser.add_argument(
        "--apply", action="store_true", default=False,
        help="Execute live link replacements and bonus title fix via WordPress REST API."
    )
    args = parser.parse_args()

    base_url = get_base_url()

    # If no flags specified or --verify specified
    if not (args.build_csv or args.verify_live or args.update_links):
        mode_verify(base_url)
        return

    if args.build_csv:
        mode_build_csv(base_url)

    if args.verify_live:
        mode_verify_live(base_url)

    if args.update_links:
        scan_and_update_internal_links(base_url, apply_changes=args.apply)


if __name__ == "__main__":
    main()
