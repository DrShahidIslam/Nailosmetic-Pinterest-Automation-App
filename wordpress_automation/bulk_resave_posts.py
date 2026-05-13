"""
bulk_resave_posts.py
====================
Forces a Rank Math SEO score recalculation on all published posts by
doing a "touch resave" — PATCHing each post with its own existing content.

This fires WordPress's full save_post hook chain, which triggers Rank Math's
server-side analysis engine to compute and store the SEO score.

WHY THIS IS NEEDED:
  Rank Math stores its SEO score only when save_post fires through the editor.
  Posts published via the REST API bypass this hook. A bare meta PATCH doesn't
  trigger it either. Re-PATCHing the post content IS enough to fire the hook.

Run once via GitHub Actions (workflow_dispatch) or locally.

Usage:
    python wordpress_automation/bulk_resave_posts.py
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Dict

sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from wp_client import WordPressClient


# ─────────────────────────────────────────────────────────────────────────────
# Fetch all published posts (with content for the resave)
# ─────────────────────────────────────────────────────────────────────────────
def get_all_posts(wp: WordPressClient) -> List[Dict]:
    all_posts = []
    page = 1
    per_page = 50
    while True:
        url = f"{wp.api_url}/posts"
        params = {
            "per_page": per_page,
            "page": page,
            "status": "publish",
            "context": "edit",
            "_fields": "id,title,slug,content,link",
        }
        resp = wp.session.get(url, headers=wp.headers, params=params,
                              timeout=wp.default_timeout)
        if resp.status_code == 400:
            break
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_posts.extend(batch)
        print(f"   📄 Page {page} — {len(batch)} posts ({len(all_posts)} total)")
        if len(batch) < per_page:
            break
        page += 1
        time.sleep(1)
    return all_posts


# ─────────────────────────────────────────────────────────────────────────────
# Touch-resave a single post (fires save_post → Rank Math recalculates score)
# ─────────────────────────────────────────────────────────────────────────────
def touch_resave(wp: WordPressClient, post: Dict) -> bool:
    post_id = post["id"]
    # Re-send the existing raw content — this triggers save_post hooks
    content_raw = post.get("content", {})
    content = content_raw.get("raw", "") if isinstance(content_raw, dict) else str(content_raw)

    url = f"{wp.api_url}/posts/{post_id}"
    payload = {
        "content": content,
        "status": "publish",  # ensure it stays published
    }
    resp = wp.session.post(url, headers=wp.headers, json=payload,
                           timeout=(30, 90))
    return resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("🔄 Nailosmetic — Bulk Resave Posts (Rank Math Score Fix)")
    print("=" * 60)

    wp_url  = os.getenv("WORDPRESS_URL", "https://nailosmetic.com")
    wp_user = os.getenv("WORDPRESS_USER", "")
    wp_pass = os.getenv("WORDPRESS_APP_PASSWORD", "")

    if not all([wp_user, wp_pass]):
        print("❌ Missing WORDPRESS_USER or WORDPRESS_APP_PASSWORD")
        sys.exit(1)

    wp = WordPressClient(wp_url, wp_user, wp_pass)

    # ── Connectivity check (same pattern as other bots) ────────────────────
    print("🔌 Checking WordPress connectivity...")
    for attempt in range(5):
        test = wp.test_connection()
        if test["success"]:
            print(f"   ✅ Connected on attempt {attempt + 1}")
            break
        wait = 30 * (attempt + 1)
        print(f"   ⚠️  Attempt {attempt+1}/5 failed: {test['error']} — retry in {wait}s")
        time.sleep(wait)
    else:
        print("❌ WordPress unreachable. Aborting.")
        sys.exit(1)

    # ── Fetch all posts ────────────────────────────────────────────────────
    print("\n📥 Fetching all published posts...")
    posts = get_all_posts(wp)
    print(f"✅ {len(posts)} posts found.\n")

    # ── Resave each post ───────────────────────────────────────────────────
    succeeded = 0
    failed    = 0

    for i, post in enumerate(posts):
        post_id = post["id"]
        title   = post.get("title", {})
        title   = title.get("rendered", "") if isinstance(title, dict) else str(title)
        link    = post.get("link", "")

        print(f"[{i+1}/{len(posts)}] {title[:65]}")

        ok = touch_resave(wp, post)
        if ok:
            print(f"   ✅ Resaved — Rank Math score will now compute")
            succeeded += 1
        else:
            print(f"   ❌ Failed for post ID {post_id}")
            failed += 1

        # Rate limit: ~2s between each to avoid overloading WP
        time.sleep(2)

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"✅ Resaved:  {succeeded} / {len(posts)}")
    print(f"❌ Failed:   {failed} / {len(posts)}")
    print("\n🏁 Done! Rank Math will now show SEO scores for all posts.")
    print("   Check Rank Math > Analytics > Overview to see the improvement.")


if __name__ == "__main__":
    main()
