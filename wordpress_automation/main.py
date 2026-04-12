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

    # Initialize Clients
    wp = WordPressClient(wp_url, wp_user, wp_pass)
    gen = ContentGenerator(gemini_keys)
    img_mgr = ImageManager(silicon_key)

    # 1. Fetch Categories and History
    print("📊 Fetching metadata...")
    wp_cats = wp.get_categories()
    cat_names = [c["name"] for c in wp_cats]
    
    history_path = Path(__file__).parent.parent / "shared" / "history.json"
    with open(history_path, "r") as f:
        previous_slugs = json.load(f)

    # 2. Generate Article Plan
    print("🧠 Generating high-quality article plan...")
    plan = gen.generate_article_plan(cat_names, previous_slugs)
    print(f"📌 Title: {plan['title']}")

    # 3. Handle Images and WordPress Media
    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"📁 Temp directory: {tmp_dir}")
        
        # Featured Image
        print("🎨 Generating featured image (16:9)...")
        feat_img_path = str(Path(tmp_dir) / "featured.jpg")
        img_mgr.generate_image(plan["featured_image"]["prompt"], "16:9", feat_img_path)
        feat_media_id = wp.upload_media(feat_img_path, plan["featured_image"]["alt_text"])
        print(f"✅ Featured image uploaded. ID: {feat_media_id}")

        # Block Images
        html_content = gen.build_html_content(plan)
        
        for i, block in enumerate(plan["blocks"]):
            print(f"🎨 Generating image for '{block['heading']}' (4:5)...")
            block_img_path = str(Path(tmp_dir) / f"block_{i}.jpg")
            img_mgr.generate_image(block["prompt"], "4:5", block_img_path)
            block_media_id = wp.upload_media(block_img_path, block["alt_text"])
            
            # Replace placeholder in HTML
            # We'll use a simple WP Image Block HTML structure
            img_html = f"""
            <figure class="wp-block-image size-large">
                <img src="REPLACE_WP_URL" alt="{block['alt_text']}" class="wp-image-{block_media_id}"/>
            </figure>
            """
            # WP REST API will handle the actual source if we provide the media ID properly, 
            # but for the content body, we just need to ensure the figure is there.
            # Actually, to be safe, I'll fetch the uploaded media URL.
            media_info = wp.session.get(f"{wp.api_url}/media/{block_media_id}", headers=wp.headers).json()
            img_url = media_info["source_url"]
            img_html = img_html.replace("REPLACE_WP_URL", img_url)
            
            html_content = html_content.replace(f"<!-- IMAGE_PLACEHOLDER_{block['heading']} -->", img_html)

    # 4. Finalize Category
    target_category_ids = []
    if plan["is_new_category"]:
        print(f"🆕 Creating new category: {plan['category_suggestion']}")
        new_cat_id = wp.create_category(plan["category_suggestion"])
        target_category_ids.append(new_cat_id)
    else:
        # Find ID for suggested existing category
        for cat in wp_cats:
            if cat["name"].lower() == plan["category_suggestion"].lower():
                target_category_ids.append(cat["id"])
                break
        if not target_category_ids: # Fallback
            target_category_ids.append(wp_cats[0]["id"] if wp_cats else 1)

    # 5. Create Post
    print("🚀 Publishing post to WordPress...")
    post_result = wp.create_post(
        title=plan["title"],
        content=html_content,
        featured_media_id=feat_media_id,
        categories=target_category_ids
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
    queue.append({"url": post_url, "category": plan["category_suggestion"]})
    with open(queue_path, "w") as f:
        json.dump(queue, f, indent=4)

    print("✅ All done!")

if __name__ == "__main__":
    main()
