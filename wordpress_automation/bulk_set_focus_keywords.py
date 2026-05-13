"""
bulk_set_focus_keywords.py
==========================
Fetches all published WordPress posts that are missing a Rank Math focus
keyword and uses Gemini to derive the best target keyword from the post
title. Then PATCHes the post meta to set rank_math_focus_keyword.

Run once manually or via a one-off GitHub Action.

Usage:
    python wordpress_automation/bulk_set_focus_keywords.py
"""

import os
import sys
import time
import re
import json
from pathlib import Path
from typing import List, Dict

sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from wp_client import WordPressClient
from google import genai


# ─────────────────────────────────────────────────────────────────────────────
# Gemini: derive best focus keyword from post title
# ─────────────────────────────────────────────────────────────────────────────
def derive_keyword(api_keys: List[str], post_title: str, post_slug: str) -> str:
    """
    Ask Gemini to pick the single best SEO focus keyword for this post.
    Returns a short keyword string (2-5 words).
    """
    models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.1-flash-lite-preview"]
    prompt = f"""
You are an SEO expert. Given the blog post title and URL slug below, return the
single BEST focus keyword for Rank Math SEO — the exact phrase real users type
into Google to find this content.

POST TITLE: {post_title}
URL SLUG: {post_slug}

RULES:
- Return 2-5 words only, lowercase, no punctuation
- It must be a real search query with meaningful monthly search volume
- Prefer specific long-tail keywords over single broad words
- Do NOT return the full title, paraphrase it as a search query
- Return ONLY the keyword, nothing else — no explanation, no quotes

KEYWORD:"""

    for key in api_keys:
        client = genai.Client(api_key=key)
        for model in models:
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                keyword = response.text.strip().lower()
                # Sanitise — strip quotes, punctuation, limit to 60 chars
                keyword = re.sub(r'["\'\*\#]', '', keyword).strip()
                keyword = keyword[:60]
                if keyword:
                    return keyword
            except Exception as e:
                err = str(e)
                if "404" in err or "limit: 0" in err:
                    break
                time.sleep(10)
    # Fallback: derive from slug
    return post_slug.replace("-", " ")


# ─────────────────────────────────────────────────────────────────────────────
# WordPress: fetch all posts, check meta, patch missing keywords
# ─────────────────────────────────────────────────────────────────────────────
def get_all_posts(wp: WordPressClient) -> List[Dict]:
    """Fetch all published posts with their meta (requires edit context)."""
    all_posts = []
    page = 1
    per_page = 50
    while True:
        url = f"{wp.api_url}/posts"
        params = {
            "per_page": per_page,
            "page": page,
            "status": "publish",
            "context": "edit",   # needed to read meta fields
            "_fields": "id,title,slug,meta,link",
        }
        resp = wp.session.get(url, headers=wp.headers, params=params,
                              timeout=wp.default_timeout)
        if resp.status_code == 400:
            break  # no more pages
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_posts.extend(batch)
        print(f"   📄 Fetched page {page} — {len(batch)} posts ({len(all_posts)} total)")
        if len(batch) < per_page:
            break
        page += 1
        time.sleep(1)
    return all_posts


def patch_focus_keyword(wp: WordPressClient, post_id: int, keyword: str) -> bool:
    """PATCH rank_math_focus_keyword onto an existing post."""
    url = f"{wp.api_url}/posts/{post_id}"
    payload = {"meta": {"rank_math_focus_keyword": keyword}}
    resp = wp.session.post(url, headers=wp.headers, json=payload,
                           timeout=wp.default_timeout)
    return resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("🔑 Nailosmetic — Bulk Focus Keyword Setter")
    print("=" * 55)

    wp_url  = os.getenv("WORDPRESS_URL", "https://nailosmetic.com")
    wp_user = os.getenv("WORDPRESS_USER", "")
    wp_pass = os.getenv("WORDPRESS_APP_PASSWORD", "")
    gemini_keys = [
        k.strip()
        for k in (os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")).split(",")
        if k.strip()
    ]

    if not all([wp_user, wp_pass, gemini_keys]):
        print("❌ Missing WORDPRESS_USER, WORDPRESS_APP_PASSWORD, or GEMINI_API_KEYS")
        sys.exit(1)

    wp = WordPressClient(wp_url, wp_user, wp_pass)

    # ── Connectivity check ────────────────────────────────────────────────
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

    # ── Fetch all posts ───────────────────────────────────────────────────
    print("\n📥 Fetching all published posts...")
    posts = get_all_posts(wp)
    print(f"✅ {len(posts)} published posts found.\n")

    # ── Filter: posts missing a focus keyword ─────────────────────────────
    missing = []
    for post in posts:
        meta = post.get("meta", {}) or {}
        existing_kw = meta.get("rank_math_focus_keyword", "")
        if not existing_kw or existing_kw.strip() == "":
            missing.append(post)

    print(f"🔍 Posts missing focus keyword: {len(missing)} / {len(posts)}")

    if not missing:
        print("🎉 All posts already have a focus keyword set. Nothing to do!")
        sys.exit(0)

    # ── Process each post ─────────────────────────────────────────────────
    updated   = 0
    failed    = 0
    skipped   = 0

    for i, post in enumerate(missing):
        post_id    = post["id"]
        title_raw  = post.get("title", {})
        title      = title_raw.get("rendered", "") if isinstance(title_raw, dict) else str(title_raw)
        slug       = post.get("slug", "")
        link       = post.get("link", "")

        print(f"\n[{i+1}/{len(missing)}] {title[:60]}")
        print(f"   🔗 {link}")

        # Derive keyword via Gemini
        keyword = derive_keyword(gemini_keys, title, slug)
        print(f"   🎯 Keyword: \"{keyword}\"")

        # PATCH the post
        success = patch_focus_keyword(wp, post_id, keyword)
        if success:
            print(f"   ✅ Updated!")
            updated += 1
        else:
            print(f"   ❌ PATCH failed for post ID {post_id}")
            failed += 1

        # Rate-limit: 1 Gemini call + 1 WP PATCH per ~3s to stay safe
        time.sleep(3)

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print(f"✅ Updated:  {updated}")
    print(f"❌ Failed:   {failed}")
    print(f"⏭️  Skipped:  {skipped}")
    print(f"📊 Total processed: {len(missing)}")
    print("\n🏁 Done! Rank Math focus keywords are now set on all posts.")
    print("   Go to Rank Math > Dashboard to see the improved site-wide score.")


if __name__ == "__main__":
    main()
