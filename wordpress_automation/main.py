import os
import json
import sys
import tempfile
import requests
from pathlib import Path
from dotenv import load_dotenv

# Add root to sys.path to allow sharing resources if needed
sys.path.append(str(Path(__file__).parent.parent))

from wp_client import WordPressClient
from content_generator import ContentGenerator
from image_manager import ImageManager

def main():
    print("🌸 Nailosmetic WordPress Automation Starting...")
    load_dotenv()
    import time
    
    # Config
    wp_url = os.getenv("WORDPRESS_URL", "https://nailosmetic.com")
    wp_user = os.getenv("WORDPRESS_USER", "shahidislam14@outlook.com")
    wp_pass = os.getenv("WORDPRESS_APP_PASSWORD", "fRSd sQwI 2iQc Fkyq eMn7 qvOw")
    gemini_keys_raw = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
    gemini_keys = [k.strip() for k in gemini_keys_raw.split(",") if k.strip()]
    silicon_key = os.getenv("SILICONFLOW_API_KEY")
    
    if not all([wp_url, wp_user, wp_pass, gemini_keys, silicon_key]):
        print("❌ Missing required environment variables. Check .env")
        sys.exit(1)

    # ===== STEP 0: WordPress Health Check (before using any paid APIs) =====
    print("🔌 Checking WordPress connectivity FIRST (before using any API credits)...")
    wp = WordPressClient(wp_url, wp_user, wp_pass)
    
    wp_cats = None
    max_connection_attempts = 5
    for attempt in range(1, max_connection_attempts + 1):
        try:
            wp_cats = wp.get_categories()
            print(f"   ✅ WordPress is reachable! Connected on attempt {attempt}. Found {len(wp_cats)} categories.")
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout) as e:
            if attempt == max_connection_attempts:
                print(f"   ❌ WordPress is UNREACHABLE after {max_connection_attempts} attempts.")
                print(f"   ❌ Aborting to save API credits. No Gemini or SiliconFlow calls were made.")
                sys.exit(1)
            wait = 30 * attempt  # 30s, 60s, 90s, 120s
            print(f"   ⚠️  Connection attempt {attempt}/{max_connection_attempts} failed. Retrying in {wait}s...")
            time.sleep(wait)
    
    cat_names = [c["name"] for c in wp_cats]
    
    history_path = Path(__file__).parent.parent / "shared" / "history.json"
    with open(history_path, "r") as f:
        previous_slugs = json.load(f)

    # ===== Pick a high-demand topic from the topic bank =====
    topic_bank_path = Path(__file__).parent.parent / "shared" / "topic_bank.json"
    used_topics_path = Path(__file__).parent.parent / "shared" / "used_topics.json"
    
    chosen_topic = None
    if topic_bank_path.exists():
        with open(topic_bank_path, "r") as f:
            all_topics = json.load(f)
        
        # Load used topics
        used_topics = []
        if used_topics_path.exists():
            with open(used_topics_path, "r") as f:
                used_topics = json.load(f)
        
        # Find topics we haven't written about yet
        available_topics = [t for t in all_topics if t not in used_topics]
        
        if available_topics:
            import random as rng
            chosen_topic = rng.choice(available_topics)
            print(f"🎯 High-demand topic selected: \"{chosen_topic}\"")
        else:
            print("📋 All topics in bank have been used! Gemini will pick a fresh topic.")
    else:
        print("📋 No topic bank found. Gemini will pick a topic on its own.")

    # ===== Now safe to initialize paid API clients =====
    gen = ContentGenerator(gemini_keys)
    img_mgr = ImageManager(silicon_key)

    # 2. Generate Article Plan
    print("🧠 Generating high-quality article plan...")
    plan = gen.generate_article_plan(cat_names, previous_slugs, topic=chosen_topic)
    print(f"📌 Title: {plan['title']}")

    # 3. Handle Images and WordPress Media
    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"📁 Temp directory: {tmp_dir}")
        
        # Featured Image
        print("🎨 Generating featured image (16:9)...")
        feat_img_path = str(Path(tmp_dir) / "featured.png")
        img_mgr.generate_image(plan["featured_image"]["prompt"], "16:9", feat_img_path)
        
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
            img_mgr.generate_image(block["prompt"], "4:5", block_img_path)
            
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

    # ... Target Category logic ...
    target_category_ids = []
    if plan["is_new_category"]:
        print(f"🆕 Creating new category: {plan['category_suggestion']}")
        new_cat_id = wp.create_category(plan["category_suggestion"])
        target_category_ids.append(new_cat_id)
    else:
        for cat in wp_cats:
            if cat["name"].lower() == plan["category_suggestion"].lower():
                target_category_ids.append(cat["id"])
                break
        if not target_category_ids: target_category_ids.append(wp_cats[0]["id"] if wp_cats else 1)

    # 5. Create Post with RankMath Meta
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
    previous_slugs.append(post_slug)
    with open(history_path, "w") as f:
        json.dump(previous_slugs, f, indent=4)
        
    queue_path = Path(__file__).parent.parent / "shared" / "links_queue.json"
    with open(queue_path, "r") as f:
        queue = json.load(f)
    
    queue.append({
        "url": post_url, 
        "category": plan["category_suggestion"],
        "topic": chosen_topic
    })
    
    with open(queue_path, "w") as f:
        json.dump(queue, f, indent=4)

    # Mark topic as used so we don't repeat it
    if chosen_topic:
        used_topics_path = Path(__file__).parent.parent / "shared" / "used_topics.json"
        used_topics = []
        if used_topics_path.exists():
            with open(used_topics_path, "r") as f:
                used_topics = json.load(f)
        used_topics.append(chosen_topic)
        with open(used_topics_path, "w") as f:
            json.dump(used_topics, f, indent=4)
        print(f"📋 Topic \"{chosen_topic}\" marked as used.")

    print("✅ All done!")

if __name__ == "__main__":
    main()
