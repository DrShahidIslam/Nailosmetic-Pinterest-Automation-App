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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
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
        "GEMINI_API_KEY": GEMINI_API_KEY,
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

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Build list of available board categories so Gemini only picks from configured boards
    available_categories = [cat for cat, info in BOARD_MAP.items() if info["board_id"]]
    if not available_categories:
        available_categories = list(BOARD_MAP.keys())  # fallback to all

    category_descriptions = {
        "aesthetic_nail_art": "Creative, artistic, 3D, maximalist, abstract, geometric, or editorial nail art designs",
        "chrome_glazed": "Chrome nails, glazed donut finish, metallic, pearlescent, reflective, or shiny nail designs",
        "minimalist_clean": "Minimalist, clean girl aesthetic, short nails, neutral tones, milky white, micro-French, subtle elegant designs",
        "spring_trends": "Spring-themed nails: pastels, florals, bright fresh colors, seasonal trendy designs",
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
  "description": "An SEO-optimized Pinterest description (150-300 chars). Include relevant hashtags like #nailart #nails #naildesign #nailinspiration #manicure etc.",
  "image_prompt": "A highly detailed image generation prompt (200-400 chars) describing a close-up photograph of beautifully manicured hands showcasing the nail art concept. Include details about: the specific nail design/pattern/color, hand pose and anatomy, lighting (studio/natural), background, camera angle, and overall aesthetic. The style should be editorial, high-end beauty magazine quality."
}}

Available board categories (pick the BEST match):
{categories_prompt}

Important guidelines for variety:
- Rotate between ALL the categories above — do not always pick the same one
- Mix styles: minimalist, maximalist, 3D art, chrome, glazed, French tips, ombré, abstract, geometric
- Vary nail shapes: almond, coffin, stiletto, square, oval, round
- Include trending aesthetics: clean girl, coquette, Y2K, old money, cottagecore, mob wife"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=system_prompt,
    )
    raw_text = response.text.strip()

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
        "prompt": image_prompt,
        "image_size": "768x1024",  # 3:4 vertical aspect ratio supported by Kolors
        "batch_size": 1,
    }

    response = requests.post(SILICONFLOW_API_URL, headers=headers, json=payload, timeout=120)

    if response.status_code != 200:
        print(f"❌ SiliconFlow API error ({response.status_code}): {response.text[:500]}")
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


# ============================================================================
# PHASE 3: THE DESIGNER — Pillow (PIL)
# ============================================================================

def design_pin_image(image_path: str, title: str, output_dir: str) -> str:
    """
    Open the raw image, apply a dark gradient overlay at the bottom,
    and render the title text in a clean white modern font.
    Returns the path to the final designed image.
    """
    print("\n🎨 Phase 3: Designing the Pinterest pin with Pillow...")

    img = Image.open(image_path).convert("RGBA")
    width, height = img.size

    # --- Create gradient overlay at the bottom ---
    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw_gradient = ImageDraw.Draw(gradient)

    # Gradient covers the bottom 40% of the image
    gradient_start_y = int(height * 0.60)
    max_alpha = 200  # Maximum opacity of the dark overlay

    for y in range(gradient_start_y, height):
        # Progress from 0 to 1 across the gradient zone
        progress = (y - gradient_start_y) / (height - gradient_start_y)
        alpha = int(max_alpha * progress)
        draw_gradient.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))

    # Composite the gradient onto the image
    img = Image.alpha_composite(img, gradient)

    # --- Add title text ---
    draw = ImageDraw.Draw(img)

    # Try to load a clean modern font; fall back to default if not available
    font_size = int(width * 0.065)  # Responsive font size based on image width
    font = None

    # List of common system fonts to try (in order of preference)
    font_candidates = [
        # Windows fonts
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        # Linux fonts (GitHub Actions runners)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        # macOS fonts
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
    ]

    for font_path in font_candidates:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except (OSError, IOError):
            continue

    if font is None:
        print("   ⚠️  No TrueType font found, using default bitmap font.")
        font = ImageFont.load_default()

    # Word-wrap the title to fit within the image width
    max_chars_per_line = int(width / (font_size * 0.55))  # Approximate chars per line
    wrapped_lines = textwrap.wrap(title, width=max_chars_per_line)

    # Calculate text positioning (centered, near bottom)
    line_height = font_size + 10
    total_text_height = len(wrapped_lines) * line_height
    text_y_start = height - total_text_height - int(height * 0.06)  # 6% padding from bottom

    for i, line in enumerate(wrapped_lines):
        # Get text bounding box for centering
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2
        text_y = text_y_start + (i * line_height)

        # Draw text shadow for better readability
        shadow_offset = 2
        draw.text(
            (text_x + shadow_offset, text_y + shadow_offset),
            line,
            font=font,
            fill=(0, 0, 0, 180),
        )

        # Draw main text in white
        draw.text(
            (text_x, text_y),
            line,
            font=font,
            fill=(255, 255, 255, 255),
        )

    # Convert back to RGB for JPEG compatibility and save
    final_img = img.convert("RGB")
    final_path = os.path.join(output_dir, "final_pin.jpg")
    final_img.save(final_path, "JPEG", quality=95)

    print(f"   ✅ Final pin saved to: {final_path}")
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
    else:
        print(f"❌ Pinterest API error ({response.status_code}): {response.text[:500]}")
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

        target_board_id = board_info["board_id"]
        destination_link = board_info["link"]
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
