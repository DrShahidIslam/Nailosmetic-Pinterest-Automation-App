import os
import json
import sys
import tempfile
import requests
from pathlib import Path
from dotenv import load_dotenv

# Fix Unicode output on Windows terminals
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (AttributeError, io.UnsupportedOperation):
        pass

# Add root to sys.path to allow sharing resources if needed
sys.path.append(str(Path(__file__).parent.parent))

from wp_client import WordPressClient
from content_generator import ContentGenerator
from image_manager import ImageManager
from shared_data_manager import SmartJSON

def validate_and_fix_category(title: str, current_category: str, chosen_niche: str) -> str:
    """
    The Authoritative Gatekeeper: Ensures articles are filed correctly based on the source niche.
    For non-nail niches, it forces the correct broad category.
    For the nail niche, it enforces nail-specific subcategories.
    """
    title_lower = title.lower()
    
    # Authoritative mapping for "Authority" niches
    NICHE_TO_CATEGORY = {
        "hair_beauty": "Hair & Beauty",
        "home_garden": "Home & Garden",
        "gardening": "Home & Garden",
        "fashion_style": "Styles & Fashion"
    }

    # Define nail subcategories that are FORBIDDEN for other niches
    NAIL_SPECIFIC_CATS = ["Aesthetic & Art", "Chrome & Glazed", "Minimalist & Clean Girl", "Seasonal Trends", "Nails and Manicure"]
    
    # Define keywords for the "Janitor" fallback (catches leaks across niches)
    nail_exclusion = ["nail", "mani", "polish", "pedi", "acrylic"]
    hair_keywords = ["hair", "hairstyle", "haircut", "bob", "updo", "braid", "shaggy"]
    home_keywords = ["decor", "home", "garden", "patio", "backyard", "pond", "curb appeal", "interior", "oasis"]
    fashion_keywords = ["outfit", "wear", "fashion", "look", "leggings", "dress", "style"]

    # --- 1. Authoritative Override (Niche-based) ---
    if chosen_niche in NICHE_TO_CATEGORY:
        target_cat = NICHE_TO_CATEGORY[chosen_niche]
        if current_category != target_cat:
            print(f"   [GATEKEEPER] Niche is '{chosen_niche}'. Forcing category '{target_cat}' (was '{current_category}').")
            return target_cat
        return current_category

    # --- 2. Nail Niche Enforcement ---
    if chosen_niche == "nails":
        # If a nail post accidentally got a non-nail category
        if current_category not in NAIL_SPECIFIC_CATS:
            print(f"   [GATEKEEPER] Nail niche article found in '{current_category}'. Forcing 'Aesthetic & Art'.")
            return "Aesthetic & Art"
        return current_category

    # --- 3. The Janitor (Keyword-based Fallback for double-safety) ---
    # Hair in Nails?
    if any(k in title_lower for k in hair_keywords) and not any(k in title_lower for k in nail_exclusion):
        return "Hair & Beauty"
    
    # Home in Nails?
    if any(k in title_lower for k in home_keywords) and not any(k in title_lower for k in nail_exclusion):
        return "Home & Garden"

    return current_category

def main():
    print("✨ Nailosmetic — WordPress Automation Starting...")
    load_dotenv()
    import time
    import random as rng
    
    # Config
    wp_url = os.getenv("WORDPRESS_URL", "https://nailosmetic.com")
    wp_user = os.getenv("WORDPRESS_USER", "")
    wp_pass = os.getenv("WORDPRESS_APP_PASSWORD", "")
    gemini_keys_raw = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
    gemini_keys = [k.strip() for k in gemini_keys_raw.split(",") if k.strip()]
    silicon_key = os.getenv("SILICONFLOW_API_KEY")
    hf_keys_raw = os.getenv("HUGGINGFACE_API_KEYS", "") or os.getenv("HUGGINGFACE_API_KEY", "")
    hf_keys = [k.strip() for k in hf_keys_raw.split(",") if k.strip()]
    
    # Required variables check
    required_vars = {
        "WORDPRESS_URL": wp_url,
        "WORDPRESS_USER": wp_user,
        "WORDPRESS_APP_PASSWORD": wp_pass,
        "GEMINI_API_KEYS": gemini_keys,
        "HUGGINGFACE_API_KEYS": hf_keys
    }
    
    missing = [name for name, val in required_vars.items() if not val]
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        print("   Check your .env file or GitHub Secrets.")
        sys.exit(1)

    # ===== STEP 0: WordPress Health Check (before using any paid APIs) =====
    print("🔌 Checking WordPress connectivity FIRST (before using any API credits)...")
    wp = WordPressClient(wp_url, wp_user, wp_pass)
    
    wp_cats = None
    max_connection_attempts = 5
    for attempt in range(1, max_connection_attempts + 1):
        test = wp.test_connection()
        if test["success"]:
            wp_cats = wp.get_categories()
            print(f"   ✅ WordPress is reachable! Connected on attempt {attempt}. Found {len(wp_cats)} categories.")
            break
        else:
            if attempt == max_connection_attempts:
                print(f"   ❌ WordPress is UNREACHABLE after {max_connection_attempts} attempts.")
                print(f"   ❌ ERROR DETAIL: {test['error']}")
                print(f"   ❌ Aborting to save API credits. No Gemini or SiliconFlow calls were made.")
                sys.exit(1)
            
            wait = 30 * attempt  # 30s, 60s, 90s, 120s
            print(f"   ⚠️  Connection attempt {attempt}/{max_connection_attempts} failed.")
            print(f"   ⚠️  REASON: {test['error']}")
            print(f"   ⚠️  Retrying in {wait}s...")
            time.sleep(wait)
    
    import html
    cat_names = [html.unescape(c["name"]) for c in wp_cats]
    
    history_path = Path(__file__).parent.parent / "shared" / "history.json"
    with open(history_path, "r") as f:
        previous_slugs = json.load(f)

    # ===== Pick a niche and high-demand topic from the topic bank =====
    # Niche weights: 40% nails, 20% hair, 20% home, 20% fashion
    NICHE_WEIGHTS = {
        "nails": 0.40,
        "hair_beauty": 0.20,
        "home_garden": 0.20,
        "fashion_style": 0.20,
    }
    
    topic_bank_path = Path(__file__).parent.parent / "shared" / "topic_bank.json"
    used_topics_path = Path(__file__).parent.parent / "shared" / "used_topics.json"
    
    chosen_topic = None
    chosen_niche = "nails"  # default
    
    if topic_bank_path.exists():
        with open(topic_bank_path, "r") as f:
            all_topics = json.load(f)
        
        # Load used topics
        used_topics = []
        if used_topics_path.exists():
            with open(used_topics_path, "r") as f:
                used_topics = json.load(f)
        
        if isinstance(all_topics, dict):
            # Niche-keyed format: pick niche then topic
            niches = list(NICHE_WEIGHTS.keys())
            weights = list(NICHE_WEIGHTS.values())
            chosen_niche = rng.choices(niches, weights=weights, k=1)[0]
            
            niche_topics = all_topics.get(chosen_niche, [])
            # Merge gardening into home_garden
            if chosen_niche == "home_garden":
                niche_topics = niche_topics + all_topics.get("gardening", [])
            
            available_topics = [t for t in niche_topics if t not in used_topics]
            if available_topics:
                chosen_topic = rng.choice(available_topics)
                print(f"🎯 Niche: {chosen_niche} | Topic: \"{chosen_topic}\"")
            else:
                # Try any niche
                for nk, topics in all_topics.items():
                    avail = [t for t in topics if t not in used_topics]
                    if avail:
                        chosen_niche = nk
                        chosen_topic = rng.choice(avail)
                        print(f"📋 {chosen_niche} fallback topic: \"{chosen_topic}\"")
                        break
                if not chosen_topic:
                    print("📋 All topics used! Picking random.")
                    chosen_topic = rng.choice(niche_topics) if niche_topics else None
        else:
            # Legacy flat list format
            chosen_niche = "nails"
            available_topics = [t for t in all_topics if t not in used_topics]
            if available_topics:
                chosen_topic = rng.choice(available_topics)
                print(f"🎯 High-demand topic selected: \"{chosen_topic}\"")
            else:
                print("📋 All topics in bank have been used! Gemini will pick a fresh topic.")
    else:
        print("📋 No topic bank found. Gemini will pick a topic on its own.")

    # ===== Now safe to initialize paid API clients =====
    gen = ContentGenerator(gemini_keys)
    img_mgr = ImageManager(hf_api_keys=hf_keys, siliconflow_api_key=silicon_key)

    # 2. Generate Article Plan (niche-aware)
    print(f"🧠 Generating high-quality {chosen_niche} article plan...")
    plan = gen.generate_article_plan(cat_names, previous_slugs, topic=chosen_topic, niche=chosen_niche)
    print(f"📌 Title: {plan['title']}")

    # 3. Handle Images and WordPress Media
    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"📁 Temp directory: {tmp_dir}")
        
        # Featured Image
        print("🎨 Generating featured image (16:9)...")
        feat_img_path = str(Path(tmp_dir) / "featured.png")
        img_mgr.generate_image(plan["featured_image"]["prompt"], "16:9", feat_img_path, prefer_kolors=True)
        
        # Convert to WebP
        print("⚡ Converting featured image to WebP...")
        feat_webp_path = img_mgr.convert_to_webp(feat_img_path)
        feat_media_id = wp.upload_media(feat_webp_path, plan["featured_image"]["alt_text"])
        print(f"✅ Featured image (WebP) uploaded. ID: {feat_media_id}")

        # Block Images
        html_content = gen.build_html_content(plan)
        
        for i, block in enumerate(plan["blocks"]):
            print(f"🎨 Generating image for '{block['heading']}' (4:5)...")
            block_img_path = str(Path(tmp_dir) / f"block_{i}.png")
            img_mgr.generate_image(block["prompt"], "4:5", block_img_path, prefer_kolors=True)
            
            # Convert to WebP
            print(f"⚡ Converting block '{block['heading']}' to WebP...")
            block_webp_path = img_mgr.convert_to_webp(block_img_path)
            block_media_id = wp.upload_media(block_webp_path, block["alt_text"])
            
            # Fetch URL for Kadence image block
            media_info = wp.session.get(f"{wp.api_url}/media/{block_media_id}", headers=wp.headers).json()
            img_url = media_info["source_url"]
            
            # Replace placeholder in Kadence block
            img_tag = f'<img src="{img_url}" alt="{block["alt_text"]}" class="kb-img wp-image-{block_media_id}"/>'
            html_content = html_content.replace(f"<!-- IMAGE_PLACEHOLDER_{block['heading']} -->", img_tag)

    # 5. Determine Target Categories
    target_category_ids = []
    initial_suggestion = plan.get("category_suggestion", "Nails and Manicure")
    
    # Apply Programmatic Guardrail
    category_suggestion = validate_and_fix_category(plan["title"], initial_suggestion, chosen_niche)
    
    is_new = plan.get("is_new_category", False)

    if is_new:
        print(f"🆕 Creating new category: {category_suggestion}")
        try:
            new_cat_id = wp.create_category(category_suggestion)
            target_category_ids.append(new_cat_id)
        except Exception as e:
            print(f"   ⚠️ Error creating category: {e}. Falling back to search.")
            # Fallback to search if creation fails or if it already exists
            is_new = False 

    if not is_new:
        for cat in wp_cats:
            if html.unescape(cat["name"]).lower() == category_suggestion.lower():
                target_category_ids.append(cat["id"])
                break
        
        if not target_category_ids:
            print(f"   ⚠️ Category '{category_suggestion}' not found. Using first available.")
            target_category_ids.append(wp_cats[0]["id"] if wp_cats else 1)

    # 6. Create Post with RankMath Meta
    print("🚀 Publishing post to WordPress with RankMath SEO...")
    rankmath_meta = {
        "rank_math_title": plan["seo"]["title"],
        "rank_math_description": plan["seo"]["description"],
        "rank_math_focus_keyword": plan["seo"]["focus_keyword"]
    }
    
    post_result = wp.create_post(
        title=plan["title"],
        content=html_content,
        featured_media_id=feat_media_id,
        categories=target_category_ids,
        meta=rankmath_meta,
        slug=plan.get("slug")
    )
    
    post_url = post_result["link"]
    post_slug = post_result["slug"]
    print(f"✨ Post Live! URL: {post_url}")

    # 6. Update History and Queue
    print("📝 Updating history and Pinterest queue...")
    history_path = Path(__file__).parent.parent / "shared" / "history.json"
    SmartJSON.update_file(history_path, [post_slug])
        
    queue_path = Path(__file__).parent.parent / "shared" / "links_queue.json"
    SmartJSON.update_file(queue_path, [{
        "url": post_url, 
        "category": plan.get("category_suggestion", "Nails and Manicure"),
        "topic": chosen_topic,
        "niche": chosen_niche
    }])

    # Also save to persistent published links history (used by Pinterest bot for smart link fallback)
    published_path = Path(__file__).parent.parent / "shared" / "published_links.json"
    SmartJSON.update_file(published_path, [{
        "url": post_url,
        "category": plan.get("category_suggestion", "Nails and Manicure"),
        "niche": chosen_niche,
        "topic": chosen_topic,
        "slug": post_slug
    }])

    # Mark topic as used so we don't repeat it
    if chosen_topic:
        used_topics_path = Path(__file__).parent.parent / "shared" / "used_topics.json"
        SmartJSON.update_file(used_topics_path, [chosen_topic])
        print(f"📋 Topic \"{chosen_topic}\" marked as used.")

    print(f"✅ All done! ({chosen_niche} article published)")


if __name__ == "__main__":
    main()
