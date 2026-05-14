"""
publish_pillars.py
==================
Publishes the 5 SEO pillar posts for nailosmetic.com — one per day.

Called by the GitHub Action 'pillar-posts.yml' on a daily schedule.
Tracks progress in shared/pillar_state.json — when all 5 are published the
script exits cleanly so the action can be left permanently enabled.

Image priority (same as main WordPress bot, prefer_kolors=False):
  1. HuggingFace FLUX.1-schnell
  2. SiliconFlow Kolors (fallback)
  3. Pollinations (zero-cost last resort)
"""

import os
import sys
import json
import time
import tempfile
from pathlib import Path
from typing import Dict

# Fix Unicode on Windows runners
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from wp_client import WordPressClient
from image_manager import ImageManager
from pillar_generator import (
    generate_pillar_outline,
    generate_section_body,
    build_pillar_html,
)
from shared_data_manager import SmartJSON

# State file that persists which pillar is next across daily runs
PILLAR_STATE_PATH = Path(__file__).parent.parent / "shared" / "pillar_state.json"


# ─────────────────────────────────────────────────────────────────────────────
# PILLAR CONFIGURATIONS
# One entry per pillar. Order matters: index 0 publishes on day 1, etc.
# ─────────────────────────────────────────────────────────────────────────────
PILLAR_CONFIGS = [
    # ── PILLAR 0: Master Nail Art Guide ──────────────────────────────────
    {
        "title": "The Ultimate Guide to Nail Art Designs: Every Style, Trend & Technique for 2026",
        "slug": "nail-art-designs-ultimate-guide",
        "keyword": "nail art designs",
        "category": "Aesthetic & Art",
        "word_count": 4000,
        "h2_outline": [
            "What Is Nail Art and Why Is It Exploding in Popularity in 2026?",
            "Chrome & Glazed Nails: The Viral Shine Trend Everyone Is Wearing",
            "How Do You Get That Perfect Clean Girl Manicure at Home?",
            "3D Nail Art: The Future of Sculptural, Textured Designs",
            "Seasonal Nail Designs: What to Wear Every Time of Year",
            "Which Nail Shape Is Right for You? Almond vs. Coffin vs. Square vs. Stiletto",
            "How Long Does Nail Art Last — and How Do You Make It Last Longer?",
            "Korean Nail Art vs. Japanese Nail Art: What's the Difference?",
            "The Best Beginner Nail Art Tools You Can Buy for Under $30",
        ],
        "cluster_urls": [
            "https://nailosmetic.com/chrome-glazed-donut-nails/",
            "https://nailosmetic.com/minimalist-clean-girl-nails/",
            "https://nailosmetic.com/creative-3d-aesthetic-nail-art/",
            "https://nailosmetic.com/spring-nail-designs-inspo/",
            "https://nailosmetic.com/coffin-nail-designs/",
            "https://nailosmetic.com/almond-nail-art-designs/",
            "https://nailosmetic.com/korean-nail-art-ideas/",
            "https://nailosmetic.com/aesthetic-nail-art-looks/",
            "https://nailosmetic.com/butterfly-nail-designs/",
            "https://nailosmetic.com/gel-nail-art-ideas/",
            "https://nailosmetic.com/red-nail-designs-guide/",
            "https://nailosmetic.com/pink-nail-art-designs/",
        ],
    },

    # ── PILLAR 1: Chrome Nails Complete Guide ─────────────────────────────
    {
        "title": "Chrome Nails: The Complete Guide to Every Chrome, Glazed & Mirror Finish (2026)",
        "slug": "chrome-nails-complete-guide",
        "keyword": "chrome nails",
        "category": "Chrome & Glazed",
        "word_count": 3500,
        "h2_outline": [
            "What Are Chrome Nails? The Science Behind the Metallic Shine",
            "How Do You Apply Chrome Powder at Home Without a Nail Salon?",
            "Glazed Donut Nails: Hailey Bieber's Iconic Look Fully Explained",
            "Rose Gold vs. Silver vs. Aurora Chrome: Which Finish Is Right for You?",
            "What Nail Shape Looks Best with a Chrome Finish?",
            "How Do Cat Eye Chrome Nails Work? The Magnetic Effect Explained",
            "How Long Does Chrome Nail Powder Last Before Chipping?",
            "Chrome Nails for Every Skin Tone: Picking Your Perfect Shade",
        ],
        "cluster_urls": [
            "https://nailosmetic.com/chrome-glazed-donut-nails/",
            "https://nailosmetic.com/almond-nail-art-designs/",
            "https://nailosmetic.com/coffin-nail-designs/",
            "https://nailosmetic.com/aesthetic-nail-art-looks/",
            "https://nailosmetic.com/clean-girl-nail-looks/",
            "https://nailosmetic.com/nail-art-designs-ultimate-guide/",
        ],
    },

    # ── PILLAR 2: Spring Outfits for Women ───────────────────────────────
    {
        "title": "Spring Outfits for Women: The Complete 2026 Style Guide for Every Occasion",
        "slug": "spring-outfits-women-guide",
        "keyword": "spring outfits for women",
        "category": "Styles & Fashion",
        "word_count": 3500,
        "h2_outline": [
            "What Are the Biggest Fashion Trends for Spring 2026?",
            "Casual Spring Outfits for Everyday Wear That Actually Look Effortless",
            "How Do You Dress for a Spring Brunch? Smart Casual Done Right",
            "Spring Work & Corporate Outfit Ideas for Women",
            "What to Wear to a Spring Concert, Festival, or Outdoor Event",
            "Spring Date Night Outfits That Always Make an Impression",
            "Vacation & Beach Travel Outfit Ideas for Warm-Weather Getaways",
            "How Do You Build a Spring Capsule Wardrobe Without Overspending?",
        ],
        "cluster_urls": [
            "https://nailosmetic.com/casual-spring-outfit-ideas/",
            "https://nailosmetic.com/spring-bar-outfit-ideas/",
            "https://nailosmetic.com/spring-corporate-outfits/",
            "https://nailosmetic.com/maxi-skirt-outfit-ideas/",
            "https://nailosmetic.com/chic-spring-outfits-women/",
            "https://nailosmetic.com/tulip-farm-outfit-ideas/",
            "https://nailosmetic.com/tropical-y2k-outfits/",
            "https://nailosmetic.com/perfect-leggings-outfits/",
            "https://nailosmetic.com/baseball-game-outfit/",
        ],
    },

    # ── PILLAR 3: Hairstyle Guide for Women ──────────────────────────────
    {
        "title": "The Ultimate Hairstyle Guide for Women: Every Cut, Color & Trend for 2026",
        "slug": "hairstyles-for-women-ultimate-guide",
        "keyword": "hairstyles for women",
        "category": "Hair & Beauty",
        "word_count": 3500,
        "h2_outline": [
            "What Are the Biggest Haircut Trends for Women in 2026?",
            "The Wolf Cut: Why It's Still the Most-Requested Style at Salons",
            "How Do You Choose the Best Haircut for Your Face Shape?",
            "Braid Styles for Every Occasion: From Everyday Wear to Formal Events",
            "The Best Hair Colors for 2026: Chocolate Brown to Strawberry Blonde",
            "Natural Hairstyles for Black Women: Celebrating Every Texture and Length",
            "What Is the Easiest Updo You Can Do Yourself in Under 10 Minutes?",
            "How Long Does Balayage Last Before It Needs a Touch-Up?",
        ],
        "cluster_urls": [
            "https://nailosmetic.com/wolf-cut-hairstyles-guide/",
            "https://nailosmetic.com/french-bob-haircut-styles/",
            "https://nailosmetic.com/elegant-updo-hairstyles/",
            "https://nailosmetic.com/goddess-braids-styles/",
            "https://nailosmetic.com/ultimate-box-braids-styles/",
            "https://nailosmetic.com/chocolate-brown-hair-styles/",
            "https://nailosmetic.com/wash-go-curly-hair-styles/",
            "https://nailosmetic.com/soft-glam-makeup-secrets/",
            "https://nailosmetic.com/korean-skincare-routine-secrets/",
        ],
    },

    # ── PILLAR 4: Home Decor Ideas ────────────────────────────────────────
    {
        "title": "Home Decor Ideas: The Ultimate Room-by-Room Style Guide for 2026",
        "slug": "home-decor-ideas-ultimate-guide",
        "keyword": "home decor ideas",
        "category": "Home & Garden",
        "word_count": 3500,
        "h2_outline": [
            "What Are the Biggest Home Decor Trends to Know in 2026?",
            "Bedroom Decor: How to Create a Cozy, Hotel-Worthy Sleep Sanctuary",
            "How Do You Decorate a Small Bathroom on a Budget and Make It Feel Bigger?",
            "Living Room Decor Ideas That Work for Every Style and Budget",
            "Front Yard & Garden Design: Curb Appeal Ideas That Turn Heads",
            "What Is the Easiest Way to Refresh a Room Without Repainting?",
            "The Complete Bedding Guide: How to Layer Like an Interior Designer",
            "Kitchen & Dining Room Decor: Small Tweaks That Make a Big Impact",
        ],
        "cluster_urls": [
            "https://nailosmetic.com/small-bathroom-makeover-ideas/",
            "https://nailosmetic.com/small-bathroom-ideas/",
            "https://nailosmetic.com/organic-cotton-bedding-styles/",
            "https://nailosmetic.com/front-yard-landscaping-ideas/",
            "https://nailosmetic.com/concrete-block-garden-beds/",
            "https://nailosmetic.com/light-pink-decor-ideas/",
            "https://nailosmetic.com/diy-fountain-ideas/",
            "https://nailosmetic.com/genius-drainage-ideas/",
            "https://nailosmetic.com/lemon-centerpiece-ideas/",
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Pillar state management
# ─────────────────────────────────────────────────────────────────────────────
def load_pillar_state() -> Dict:
    """Load current pillar publishing state. Creates default if missing."""
    if PILLAR_STATE_PATH.exists():
        with open(PILLAR_STATE_PATH, "r") as f:
            return json.load(f)
    return {"next_index": 0, "published": []}


def save_pillar_state(state: Dict):
    with open(PILLAR_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Category lookup
# ─────────────────────────────────────────────────────────────────────────────
def get_or_create_category(wp: WordPressClient, name: str) -> int:
    import html as html_lib
    cats = wp.get_categories()
    for c in cats:
        if html_lib.unescape(c["name"]).lower() == name.lower():
            return c["id"]
    print(f"   🆕 Creating category: {name}")
    return wp.create_category(name)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("🏛️  Nailosmetic — Pillar Post Publisher Starting...")
    load_dotenv()  # already called above, but safe to call again

    # ── Load state — determine which pillar is next ────────────────────────
    state = load_pillar_state()
    pillar_index = state.get("next_index", 0)

    if pillar_index >= len(PILLAR_CONFIGS):
        print(f"✅ All {len(PILLAR_CONFIGS)} pillar posts have already been published. Nothing to do.")
        sys.exit(0)

    config = PILLAR_CONFIGS[pillar_index]
    print(f"📌 Publishing Pillar {pillar_index + 1}/{len(PILLAR_CONFIGS)}: {config['title']}")

    # ── Env vars ──────────────────────────────────────────────────────────
    wp_url = os.getenv("WORDPRESS_URL", "https://nailosmetic.com")
    wp_user = os.getenv("WORDPRESS_USER", "")
    wp_pass = os.getenv("WORDPRESS_APP_PASSWORD", "")
    gemini_keys = [k.strip() for k in (os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")).split(",") if k.strip()]
    hf_keys = [k.strip() for k in (os.getenv("HUGGINGFACE_API_KEYS", "") or os.getenv("HUGGINGFACE_API_KEY", "")).split(",") if k.strip()]
    silicon_key = os.getenv("SILICONFLOW_API_KEY")  # Second-priority image source (Kolors)

    if not all([wp_url, wp_user, wp_pass, gemini_keys, hf_keys]):
        print("❌ Missing required environment variables.")
        sys.exit(1)

    # ── WordPress connectivity check ───────────────────────────────────────
    print("🔌 Verifying WordPress connectivity...")
    wp = WordPressClient(wp_url, wp_user, wp_pass)
    for attempt in range(5):
        test = wp.test_connection()
        if test["success"]:
            print(f"   ✅ WordPress connected on attempt {attempt+1}")
            break
        wait = 30 * (attempt + 1)
        print(f"   ⚠️  Attempt {attempt+1}/5 failed: {test['error']} — retry in {wait}s")
        time.sleep(wait)
    else:
        print("❌ WordPress unreachable after 5 attempts. Aborting.")
        sys.exit(1)

    # Image priority: FLUX (HF) → Kolors (SiliconFlow) → Pollinations
    img_mgr = ImageManager(hf_api_keys=hf_keys, siliconflow_api_key=silicon_key)

    # ── Step 1: Generate outline ───────────────────────────────────────────
    print("🧠 Generating pillar outline...")
    outline = generate_pillar_outline(gemini_keys, config)
    # Inject cluster URLs into outline for use in build_pillar_html
    outline["_cluster_urls"] = config["cluster_urls"]
    print(f"   ✅ Outline ready — {len(outline.get('sections', []))} sections planned")

    # ── Step 2: Generate section bodies ───────────────────────────────────
    print("✍️  Writing sections...")
    section_bodies = []
    previous_headings = []
    remaining_links = config["cluster_urls"].copy()
    
    for i, section in enumerate(outline["sections"]):
        print(f"   Section {i+1}/{len(outline['sections'])}: {section['heading'][:50]}...")
        
        # Pick 2 links for this section if it's an even index
        current_links = []
        if i % 2 == 0 and remaining_links:
            current_links = remaining_links[:2]
            remaining_links = remaining_links[2:]
            
        body = generate_section_body(
            api_keys=gemini_keys,
            pillar_title=config["title"],
            keyword=config["keyword"],
            section=section,
            previous_headings=previous_headings,
            cluster_urls=current_links,
            section_index=i,
        )
        section_bodies.append(body)
        previous_headings.append(section["heading"])
        time.sleep(3)  # be gentle with the API

    # ── Step 3: Generate & upload images ──────────────────────────────────
    media_map = {}
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Featured image — FLUX first, Kolors second, Pollinations last
        print("🎨 Generating featured image (16:9) via FLUX → Kolors → Pollinations...")
        feat_path = str(Path(tmp_dir) / "featured.png")
        img_mgr.generate_image(outline["featured_image"]["prompt"], "16:9", feat_path, prefer_kolors=False)
        feat_webp = img_mgr.convert_to_webp(feat_path)
        feat_media_id = wp.upload_media(feat_webp, outline["featured_image"]["alt_text"])
        print(f"   ✅ Featured image uploaded. ID: {feat_media_id}")
        time.sleep(5)

        # Section images
        img_counter = 0
        for i, section in enumerate(outline["sections"]):
            if section.get("has_image") and section.get("image_prompt") and section["image_prompt"] != "NONE":
                print(f"🎨 Generating section image (4:5) via FLUX → Kolors → Pollinations...")
                sec_path = str(Path(tmp_dir) / f"section_{img_counter}.png")
                img_mgr.generate_image(section["image_prompt"], "4:5", sec_path, prefer_kolors=False)
                sec_webp = img_mgr.convert_to_webp(sec_path)
                sec_media_id = wp.upload_media(sec_webp, section.get("image_alt", ""))
                time.sleep(5)

                # Fetch URL
                media_info = wp.session.get(
                    f"{wp.api_url}/media/{sec_media_id}", headers=wp.headers
                ).json()
                media_map[f"section_{img_counter}"] = {
                    "id": sec_media_id,
                    "url": media_info["source_url"],
                    "alt": section.get("image_alt", ""),
                }
                img_counter += 1
                print(f"   ✅ Section image uploaded. ID: {sec_media_id}")

        # ── Step 4: Build HTML ─────────────────────────────────────────────
        print("🔨 Assembling Kadence Blocks HTML...")
        html_content = build_pillar_html(outline, section_bodies, media_map)

    # ── Step 5: Get category ID ────────────────────────────────────────────
    cat_id = get_or_create_category(wp, config["category"])
    print(f"   📂 Category '{config['category']}' → ID {cat_id}")

    # ── Step 6: Publish post ───────────────────────────────────────────────
    print("🚀 Publishing pillar post to WordPress...")
    rankmath_meta = {
        "rank_math_title": outline["seo"]["title"],
        "rank_math_description": outline["seo"]["description"],
        "rank_math_focus_keyword": outline["seo"]["focus_keyword"],
    }

    post_result = wp.create_post(
        title=config["title"],
        content=html_content,
        featured_media_id=feat_media_id,
        categories=[cat_id],
        meta=rankmath_meta,
        slug=config["slug"],
    )

    post_url = post_result["link"]
    post_slug = post_result["slug"]
    print(f"✨ Pillar Post Live! URL: {post_url}")

    # ── Step 7: Update shared data ────────────────────────────────────────
    history_path = Path(__file__).parent.parent / "shared" / "history.json"
    SmartJSON.update_file(history_path, [post_slug])

    published_path = Path(__file__).parent.parent / "shared" / "published_links.json"
    SmartJSON.update_file(published_path, [{
        "url": post_url,
        "category": config["category"],
        "niche": "pillar",
        "topic": config["title"],
        "slug": post_slug,
    }])

    # ── Step 8: Advance pillar state ──────────────────────────────────────
    state["next_index"] = pillar_index + 1
    state.setdefault("published", []).append({
        "index": pillar_index,
        "slug": post_slug,
        "url": post_url,
    })
    save_pillar_state(state)
    print(f"📊 State saved — next run will publish pillar {pillar_index + 2} (if any).")

    remaining = len(PILLAR_CONFIGS) - (pillar_index + 1)
    if remaining > 0:
        print(f"⏭️  {remaining} pillar(s) remaining — next one publishes tomorrow.")
    else:
        print("🏁 All 5 pillar posts published! The workflow will skip future runs.")

    print(f"✅ Done! Pillar {pillar_index + 1}/{len(PILLAR_CONFIGS)} '{config['title'][:50]}...' published.")


if __name__ == "__main__":
    main()
