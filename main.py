"""
Nailosmetic Pinterest Automation Bot
=====================================
A fully automated pipeline that:
  1. Uses Google Gemini to generate nail art content (title, description, image prompt)
  2. Uses SiliconFlow (FLUX.1-schnell) to generate a vertical 9:16 image
  3. Uses Pillow to overlay a gradient + title text on the image
  4. Publishes the final pin to Pinterest via their REST API

All API keys are loaded from environment variables (.env for local, GitHub Secrets for CI).
"""

import os
import sys
import json
import random
import base64
import textwrap
import tempfile
import requests
import time
from pathlib import Path
from io import BytesIO
from dotenv import load_dotenv

# Fix Unicode output on Windows terminals (emojis etc.)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# --- Phase 3 imports (Pillow) ---
from PIL import Image, ImageDraw, ImageFont

# --- Phase 1 import (Gemini) ---
from google import genai

# ============================================================================
# CONFIGURATION
# ============================================================================

load_dotenv()  # Load .env file if present (local development)

# API Keys
# Supports multiple GEMINI keys (comma-separated). Fallback to solitary key.
raw_gemini_keys = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEYS = [k.strip() for k in raw_gemini_keys.split(",") if k.strip()]
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN")
PINTEREST_REFRESH_TOKEN = os.getenv("PINTEREST_REFRESH_TOKEN")
PINTEREST_APP_ID = os.getenv("PINTEREST_APP_ID")
PINTEREST_APP_SECRET = os.getenv("PINTEREST_APP_SECRET")

# Board routing: maps each content category to its Pinterest board ID and blog link.
# The Gemini prompt will classify each generated pin into one of these categories.
BOARD_MAP = {
    "aesthetic_nail_art": {
        "board_id": os.getenv("PINTEREST_BOARD_AESTHETIC", ""),
        "name": "Aesthetic Nail Art & Designs",
        "link": "https://nailosmetic.com/creative-3d-aesthetic-nail-art/",
    },
    "chrome_glazed": {
        "board_id": os.getenv("PINTEREST_BOARD_CHROME", ""),
        "name": "Chrome & Glazed Donut Nails",
        "link": "https://nailosmetic.com/chrome-glazed-donut-nails/",
    },
    "minimalist_clean": {
        "board_id": os.getenv("PINTEREST_BOARD_MINIMALIST", ""),
        "name": "Minimalist & Clean Girl Nails",
        "link": "https://nailosmetic.com/minimalist-clean-girl-nails/",
    },
    "spring_trends": {
        "board_id": os.getenv("PINTEREST_BOARD_SPRING", ""),
        "name": "Spring Nail Ideas & Trends",
        "link": "https://nailosmetic.com/spring-nail-designs-inspo/",
    },
    "summer_vacation": {
        "board_id": os.getenv("PINTEREST_BOARD_SUMMER", ""),
        "name": "Summer Vacation Nails & Aesthetic Ideas",
        "link": "https://nailosmetic.com/summer-vacation-nail-ideas/",
    },
}

# Fallback board (aesthetic is the most general)
DEFAULT_BOARD_CATEGORY = "aesthetic_nail_art"

# SiliconFlow API config
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/images/generations"
SILICONFLOW_MODEL = "Kwai-Kolors/Kolors"

# Pinterest API base (Production mode)
PINTEREST_API_BASE = "https://api.pinterest.com/v5"


def validate_env_vars():
    """Ensure all required environment variables are set."""
    required = {
        "GEMINI_API_KEYS": True if GEMINI_API_KEYS else False,
        "SILICONFLOW_API_KEY": SILICONFLOW_API_KEY,
        "PINTEREST_ACCESS_TOKEN": PINTEREST_ACCESS_TOKEN,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Check that at least one board ID is configured
    boards_configured = [cat for cat, info in BOARD_MAP.items() if info["board_id"]]
    if not boards_configured:
        print("❌ No Pinterest board IDs configured! Set at least one PINTEREST_BOARD_* variable.")
        sys.exit(1)

    print("✅ All required environment variables are set.")
    print(f"   📋 Boards configured: {', '.join(boards_configured)}")


# ============================================================================
# PHASE 1: THE BRAIN — Gemini API
# ============================================================================

def generate_content_with_gemini() -> dict:
    """
    Use Google Gemini to generate a JSON payload containing:
      - title: A catchy Pinterest title for a nail art pin
      - description: An SEO-optimized Pinterest description
      - image_prompt: A highly detailed prompt for image generation
    """
    print("\n🧠 Phase 1: Generating content with Gemini...")



    # Build list of available board categories so Gemini only picks from configured boards
    available_categories = [cat for cat, info in BOARD_MAP.items() if info["board_id"]]
    if not available_categories:
        available_categories = list(BOARD_MAP.keys())  # fallback to all

    category_descriptions = {
        "aesthetic_nail_art": "Creative, artistic, 3D, maximalist, abstract, geometric, or editorial nail art designs",
        "chrome_glazed": "Chrome nails, glazed donut finish, metallic, pearlescent, reflective, or shiny nail designs",
        "minimalist_clean": "Minimalist, clean girl aesthetic, short nails, neutral tones, milky white, micro-French, subtle elegant designs",
        "spring_trends": "Spring-themed nails: pastels, florals, bright fresh colors, seasonal trendy designs",
        "summer_vacation": "Summer vacation nails, tropical designs, bright summer colors, beach aesthetics, neon, fruit patterns, warm weather seasonal trends",
    }

    categories_prompt = "\n".join(
        f'  - "{cat}": {category_descriptions.get(cat, cat)}'
        for cat in available_categories
    )

    system_prompt = f"""You are a creative social media strategist specializing in nail art and beauty content for Pinterest.
Your task is to come up with a UNIQUE, trendy nail art concept and provide content for a Pinterest pin.

Return ONLY valid JSON (no markdown, no code fences) with these exact keys:
{{
  "board_category": "One of the category keys listed below that BEST matches the generated concept.",
  "title": "A short, catchy, click-worthy Pinterest title (max 100 chars). Use emojis sparingly.",
  "description": "An SEO-optimized Pinterest description (150-300 chars). You MUST include exactly 10 highly relevant and trending hashtags at the very end (e.g., #nailart #nails #[niche_style]).",
  "image_prompt": "A highly detailed, ultra-macro image generation prompt (200-400 chars). The focal point MUST be the specific nail design, patterns, and textures. Force a tight, close-up shot of the nails themselves, with minimal hand visibility and no distracting background. Use terms like 'high-resolution jewelry photography', 'extreme close-up on nail art', 'sharp focus', 'luxurious editorial beauty photography'. Specify the exact finish (glossy, matte, iridescent) and any 3D elements clearly."
}}

Available board categories (pick the BEST match):
{categories_prompt}

Important guidelines for variety:
- Rotate between ALL the categories above — do not always pick the same one
- Mix styles: minimalist, maximalist, 3D art, chrome, glazed, French tips, ombré, abstract, geometric
- Vary nail shapes: almond, coffin, stiletto, square, oval, round
- Include trending aesthetics: clean girl, coquette, Y2K, old money, cottagecore, mob wife"""

    import re
    models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
    max_retries_per_model = 3
    success = False
    raw_text = ""
    
    for api_key in GEMINI_API_KEYS:
        key_preview = f"...{api_key[-4:]}" if len(api_key) > 4 else "***"
        print(f"   🔄 Attempting generation with API Key ending in {key_preview}")
        client = genai.Client(api_key=api_key)
        
        for current_model in models_to_try:
            print(f"   🤖 Trying model: {current_model}")
            for attempt in range(max_retries_per_model):
                try:
                    response = client.models.generate_content(
                        model=current_model,
                        contents=system_prompt,
                    )
                    raw_text = response.text.strip()
                    success = True
                    break
                except Exception as e:
                    error_str = str(e)
                    # If model not found or it has 0 limit (unsupported in free tier for this region/account)
                    if "404" in error_str or "limit: 0" in error_str:
                        print(f"   ⚠️  Model {current_model} unavailable or zero quota, skipping...")
                        break
                    
                    wait_time = 15 * (attempt + 1)
                    if "429" in error_str:
                        match = re.search(r"Please retry in ([\d\.]+)s", error_str)
                        if match:
                            requested_delay = float(match.group(1))
                            wait_time = max(wait_time, requested_delay + 2.0)
                    
                    print(f"   ⚠️  Gemini API error ({error_str.split('.')[0]}), retrying {current_model} in {wait_time:.1f}s...")
                    time.sleep(wait_time)
            
            if success:
                break
        
        if success:
            break
            
    if not success:
        print(f"❌ Gemini API failed permanently across all provided API keys.")
        sys.exit(1)

    # Clean up potential markdown code fences
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]  # Remove first line
    if raw_text.endswith("```"):
        raw_text = raw_text.rsplit("```", 1)[0]  # Remove last fence
    raw_text = raw_text.strip()

    try:
        content = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse Gemini response as JSON: {e}")
        print(f"   Raw response: {raw_text[:500]}")
        sys.exit(1)

    # Validate required keys
    for key in ("board_category", "title", "description", "image_prompt"):
        if key not in content:
            print(f"❌ Gemini response missing key: '{key}'")
            sys.exit(1)

    # Validate that the category is one of our known boards
    if content["board_category"] not in BOARD_MAP:
        print(f"   ⚠️  Unknown category '{content['board_category']}', falling back to '{DEFAULT_BOARD_CATEGORY}'")
        content["board_category"] = DEFAULT_BOARD_CATEGORY

    board_info = BOARD_MAP[content["board_category"]]
    print(f"   📋 Board: {board_info['name']} ({content['board_category']})")
    print(f"   📌 Title: {content['title']}")
    print(f"   📝 Description: {content['description'][:80]}...")
    print(f"   🎨 Image Prompt: {content['image_prompt'][:80]}...")
    return content


# ============================================================================
# PHASE 2: THE ARTIST — SiliconFlow API (FLUX.1-schnell)
# ============================================================================

def generate_image_with_siliconflow(image_prompt: str, output_dir: str) -> str:
    """
    Send the image prompt to SiliconFlow's FLUX.1-schnell model.
    Downloads the generated vertical (9:16) image to a local file.
    Returns the path to the downloaded image.
    """
    print("\n🎨 Phase 2: Generating image with SiliconFlow (FLUX.1-schnell)...")

    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": SILICONFLOW_MODEL,
        "prompt": image_prompt + ", highly detailed, masterpiece, best quality, perfect anatomy, flawless fingers",
        "negative_prompt": "mutated hands, poorly drawn hands, extra fingers, missing fingers, malformed hands, deformed fingers, unnatural hands, bad anatomy, bad proportions, disfigured, blurry, worst quality, low quality",
        "image_size": "768x1024",  # 3:4 vertical aspect ratio supported by Kolors
        "batch_size": 1,
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(SILICONFLOW_API_URL, headers=headers, json=payload, timeout=120)
            if response.status_code == 200:
                break
            else:
                print(f"   ⚠️  SiliconFlow API error ({response.status_code}): {response.text[:200]}")
                if attempt < max_retries - 1:
                    time.sleep(10)
        except Exception as e:
            print(f"   ⚠️  SiliconFlow API exception: {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
    else:
        print(f"❌ SiliconFlow API failed permanently after {max_retries} attempts.")
        sys.exit(1)

    result = response.json()

    # Extract image URL from the response
    try:
        image_url = result["images"][0]["url"]
    except (KeyError, IndexError):
        print(f"❌ Unexpected SiliconFlow response format: {json.dumps(result, indent=2)[:500]}")
        sys.exit(1)

    print(f"   🖼️  Image URL received. Downloading...")

    # Download the image
    img_response = requests.get(image_url, timeout=60)
    if img_response.status_code != 200:
        print(f"❌ Failed to download image: {img_response.status_code}")
        sys.exit(1)

    image_path = os.path.join(output_dir, "raw_nail_art.png")
    with open(image_path, "wb") as f:
        f.write(img_response.content)

    print(f"   ✅ Image saved to: {image_path}")
    return image_path


# --- Support functions for design ---

def clean_text_for_rendering(text: str) -> str:
    """
    Remove emojis and replace special Unicode characters (smart quotes, em-dashes)
    with their standard ASCII equivalents to prevent 'tofu' in certain fonts.
    """
    # Replace smart quotes and dashes
    replacements = {
        "—": "-",  # em dash
        "–": "-",  # en dash
        "“": '"',  # smart double quote
        "”": '"',
        "‘": "'",  # smart single quote
        "’": "'",
        "…": "...",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove emojis (common source of tofu)
    # This regex removes most emoji/picto ranges
    import re
    emoji_pattern = re.compile("["
                               "\U0001f600-\U0001f64f"  # emoticons
                               "\U0001f300-\U0001f5ff"  # symbols & pictographs
                               "\U0001f680-\U0001f6ff"  # transport & map symbols
                               "\U0001f1e0-\U0001f1ff"  # flags (iOS)
                               "\U00002702-\U000027b0"
                               "\U000024c2-\U0001f251"
                               "]+", flags=re.UNICODE)
    cleaned = emoji_pattern.sub("", text)
    return cleaned.strip()


# ============================================================================
# PHASE 3: THE DESIGNER — Pillow (PIL)
# ============================================================================

def design_pin_image(image_path: str, title: str, output_dir: str) -> str:
    """
    Open the raw image, apply a sophisticated overlay, and render the title
    in a premium font with better typography.
    """
    print("\n🎨 Phase 3: Designing the Pinterest pin with Pillow (Premium Style)...")

    # Clean the title to avoid tofu characters
    title = clean_text_for_rendering(title)

    img = Image.open(image_path).convert("RGBA")
    width, height = img.size

    # --- Create more subtle gradient overlay ---
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)

    # Gradient covers the bottom 45%
    gradient_start_y = int(height * 0.55)
    for y in range(gradient_start_y, height):
        progress = (y - gradient_start_y) / (height - gradient_start_y)
        alpha = int(220 * (progress ** 1.5))  # Non-linear for smoother transition
        draw_overlay.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))

    img = Image.alpha_composite(img, overlay)

    # --- Add title text with premium typography ---
    draw = ImageDraw.Draw(img)

    # Font setup
    font_size = int(width * 0.075)
    font_path = "assets/fonts/Montserrat-Bold.ttf"

    try:
        if os.path.exists(font_path):
            font = ImageFont.truetype(font_path, font_size)
            print(f"   ✅ Using premium font: {font_path}")
        else:
            # Fallback to high-quality system fonts
            font_candidates = [
                # Windows
                "C:/Windows/Fonts/segoeuib.ttf",  # Segoe UI Bold
                "C:/Windows/Fonts/corbelb.ttf",   # Corbel Bold
                "C:/Windows/Fonts/arialbd.ttf",   # Arial Bold
                # Linux (GitHub Actions / Debian)
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                # macOS
                "/System/Library/Fonts/SFNSDisplay.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
            font = None
            for p in font_candidates:
                try:
                    font = ImageFont.truetype(p, font_size)
                    print(f"   ✅ Using system font fallback: {p}")
                    break
                except: continue
            if not font: font = ImageFont.load_default()
    except Exception as e:
        print(f"   ⚠️ Font error: {e}. Using default.")
        font = ImageFont.load_default()

    # Word-wrap the title
    max_chars_per_line = int(width / (font_size * 0.5))
    wrapped_lines = textwrap.wrap(title, width=max_chars_per_line)

    # Text Layout Refinement
    line_spacing = 1.15
    line_height = int(font_size * line_spacing)
    total_text_height = len(wrapped_lines) * line_height
    text_y_start = height - total_text_height - int(height * 0.08)

    for i, line in enumerate(wrapped_lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2
        text_y = text_y_start + (i * line_height)

        # Subtle shadow for depth
        draw.text((text_x + 2, text_y + 2), line, font=font, fill=(0, 0, 0, 100))
        # Main white text
        draw.text((text_x, text_y), line, font=font, fill=(255, 255, 255, 255))

    # --- Add Branding Badge (Nailosmetic) ---
    try:
        brand_font_size = int(width * 0.035)
        brand_font = ImageFont.truetype(font_path, brand_font_size) if os.path.exists(font_path) else None
        if brand_font:
            brand_text = "Nailosmetic"
            brand_bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
            bw, bh = brand_bbox[2] - brand_bbox[0], brand_bbox[3] - brand_bbox[1]

            # Draw a pill-shaped background for the brand
            bg_padding = 15
            bx = (width - bw) // 2
            by = height - bh - int(height * 0.03)
            # draw.rounded_rectangle([(bx - bg_padding, by - 5), (bx + bw + bg_padding, by + bh + 5)], radius=15, fill=(255, 255, 255, 40))
            draw.text((bx, by), brand_text, font=brand_font, fill=(255, 255, 255, 180))
    except: pass

    # Save
    final_img = img.convert("RGB")
    final_path = os.path.join(output_dir, "final_pin.jpg")
    final_img.save(final_path, "JPEG", quality=95)

    print(f"   ✅ Final stylish pin saved: {final_path}")
    return final_path


# ============================================================================
# PHASE 4: THE PUBLISHER — Pinterest REST API
# ============================================================================

def refresh_pinterest_token() -> str:
    """
    Attempt to refresh the Pinterest access token using the refresh token.
    Returns the new access token if successful, or the existing one.
    """
    if not all([PINTEREST_REFRESH_TOKEN, PINTEREST_APP_ID, PINTEREST_APP_SECRET]):
        print("   ℹ️  No refresh token credentials found. Using existing access token.")
        return PINTEREST_ACCESS_TOKEN

    print("   🔄 Attempting to refresh Pinterest access token...")

    # Pinterest requires HTTP Basic Auth with client_id:client_secret
    credentials = base64.b64encode(
        f"{PINTEREST_APP_ID}:{PINTEREST_APP_SECRET}".encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "grant_type": "refresh_token",
        "refresh_token": PINTEREST_REFRESH_TOKEN,
    }

    response = requests.post(
        f"{PINTEREST_API_BASE}/oauth/token",
        headers=headers,
        data=data,
        timeout=30,
    )

    if response.status_code == 200:
        tokens = response.json()
        new_access_token = tokens.get("access_token", PINTEREST_ACCESS_TOKEN)
        new_refresh_token = tokens.get("refresh_token")

        if new_refresh_token:
            print("   ✅ Token refreshed successfully!")
            print(f"   ⚠️  NEW REFRESH TOKEN received. Update your secrets!")
            print(f"   New refresh token: {new_refresh_token[:10]}...")

        return new_access_token
    else:
        print(f"   ⚠️  Token refresh failed ({response.status_code}). Using existing token.")
        return PINTEREST_ACCESS_TOKEN


def publish_to_pinterest(image_path: str, title: str, description: str, board_id: str, destination_link: str) -> dict:
    """
    Upload the final pin image to Pinterest.
    Uses base64 encoding for the image upload.
    Returns the API response as a dict.
    """
    print("\n📌 Phase 4: Publishing to Pinterest...")

    # Attempt to refresh the access token
    access_token = refresh_pinterest_token()

    # Read and encode the image as base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    print(f"   🔗 Destination link: {destination_link}")
    print(f"   📋 Board ID: {board_id}")

    # Build the pin payload
    pin_payload = {
        "board_id": board_id,
        "title": title[:100],  # Pinterest title limit
        "description": description[:500],  # Pinterest description limit
        "link": destination_link,
        "media_source": {
            "source_type": "image_base64",
            "content_type": "image/jpeg",
            "data": image_data,
        },
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{PINTEREST_API_BASE}/pins",
                headers=headers,
                json=pin_payload,
                timeout=60,
            )
            if response.status_code in (200, 201):
                result = response.json()
                pin_id = result.get("id", "unknown")
                print(f"   ✅ Pin published successfully! Pin ID: {pin_id}")
                return result
            elif response.status_code == 429:
                print(f"   ⚠️  Pinterest rate limit exceeded. Retrying in 60s...")
                time.sleep(60)
            else:
                print(f"   ⚠️  Pinterest API error ({response.status_code}): {response.text[:200]}")
                if attempt < max_retries - 1:
                    time.sleep(10)
        except Exception as e:
            print(f"   ⚠️  Pinterest API exception: {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
    else:
        print(f"❌ Pinterest API failed permanently after {max_retries} attempts.")
        sys.exit(1)


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Execute the full automation pipeline."""
    print("=" * 60)
    print("🌸 Nailosmetic Pinterest Automation Bot")
    print("=" * 60)

    # Validate environment
    validate_env_vars()

    # Create a temporary directory for image processing
    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"\n📁 Working directory: {tmp_dir}")

        # Phase 1: Generate content with Gemini
        content = generate_content_with_gemini()

        # Resolve the target board and destination link
        category = content["board_category"]
        board_info = BOARD_MAP[category]

        # If the chosen board isn't configured, fall back to default
        if not board_info["board_id"]:
            print(f"   ⚠️  Board for '{category}' not configured, falling back to '{DEFAULT_BOARD_CATEGORY}'")
            category = DEFAULT_BOARD_CATEGORY
            board_info = BOARD_MAP[category]

        # --- DYNAMIC LINK INJECTION ---
        queue_path = Path("shared/links_queue.json")
        destination_link = board_info["link"]
        
        if queue_path.exists():
            try:
                with open(queue_path, "r") as f:
                    queue = json.load(f)
                if queue:
                    queued_item = queue.pop(0) # FIFO: Get the oldest dynamic link
                    destination_link = queued_item["url"]
                    print(f"   🔥 Dynamic Link Found: {destination_link}")
                    
                    # Update queue file
                    with open(queue_path, "w") as f:
                        json.dump(queue, f, indent=4)
            except Exception as e:
                print(f"   ⚠️ Error reading links_queue.json: {e}. Using fallback link.")

        target_board_id = board_info["board_id"]
        print(f"\n   🎯 Routing pin to: {board_info['name']}")

        # Phase 2: Generate image with SiliconFlow
        raw_image_path = generate_image_with_siliconflow(
            content["image_prompt"], tmp_dir
        )

        # Phase 3: Design the pin with Pillow
        final_image_path = design_pin_image(
            raw_image_path, content["title"], tmp_dir
        )

        # Phase 4: Publish to Pinterest
        result = publish_to_pinterest(
            final_image_path, content["title"], content["description"],
            board_id=target_board_id, destination_link=destination_link
        )

    print("\n" + "=" * 60)
    print("✨ Pipeline complete! Your nail art pin is live on Pinterest.")
    print("=" * 60)


if __name__ == "__main__":
    main()
