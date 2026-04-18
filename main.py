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
    # --- Nail Boards ---
    "aesthetic_nail_art": {
        "board_id": os.getenv("PINTEREST_BOARD_AESTHETIC", ""),
        "name": "Aesthetic Nail Art & Designs",
        "niche": "nails",
        "link": "https://nailosmetic.com/creative-3d-aesthetic-nail-art/",
    },
    "chrome_glazed": {
        "board_id": os.getenv("PINTEREST_BOARD_CHROME", ""),
        "name": "Chrome & Glazed Donut Nails",
        "niche": "nails",
        "link": "https://nailosmetic.com/chrome-glazed-donut-nails/",
    },
    "minimalist_clean": {
        "board_id": os.getenv("PINTEREST_BOARD_MINIMALIST", ""),
        "name": "Minimalist & Clean Girl Nails",
        "niche": "nails",
        "link": "https://nailosmetic.com/minimalist-clean-girl-nails/",
    },
    "spring_trends": {
        "board_id": os.getenv("PINTEREST_BOARD_SPRING", ""),
        "name": "Spring Nail Ideas & Trends",
        "niche": "nails",
        "link": "https://nailosmetic.com/spring-nail-designs-inspo/",
    },
    "summer_vacation": {
        "board_id": os.getenv("PINTEREST_BOARD_SUMMER", ""),
        "name": "Summer Vacation Nails & Aesthetic Ideas",
        "niche": "nails",
        "link": "https://nailosmetic.com/summer-vacation-nail-ideas/",
    },
    # --- Hair & Beauty Boards ---
    "hair_aesthetics": {
        "board_id": os.getenv("PINTEREST_BOARD_HAIR", ""),
        "name": "Ethereal & Clean Hair Aesthetics",
        "niche": "hair_beauty",
        "link": "https://nailosmetic.com/",
    },
    "beauty_skincare": {
        "board_id": os.getenv("PINTEREST_BOARD_BEAUTY", ""),
        "name": "Luxury Beauty & Skincare Inspo",
        "niche": "hair_beauty",
        "link": "https://nailosmetic.com/",
    },
    # --- Home & Garden Boards ---
    "home_decor": {
        "board_id": os.getenv("PINTEREST_BOARD_HOME", ""),
        "name": "Minimalist & Modern Home Decor",
        "niche": "home_garden",
        "link": "https://nailosmetic.com/",
    },
    "garden_outdoor": {
        "board_id": os.getenv("PINTEREST_BOARD_GARDEN", ""),
        "name": "Zen Garden & Outdoor Living",
        "niche": "home_garden",
        "link": "https://nailosmetic.com/",
    },
    # --- Fashion & Style Boards ---
    "fashion_style": {
        "board_id": os.getenv("PINTEREST_BOARD_FASHION", ""),
        "name": "Chic & Timeless Fashion Style",
        "niche": "fashion_style",
        "link": "https://nailosmetic.com/",
    },
}

# Fallback board (aesthetic is the most general)
DEFAULT_BOARD_CATEGORY = "aesthetic_nail_art"

# Niche weights for weighted random selection (must sum to 1.0)
# 40% nails (proven performer), 20% hair, 20% home, 20% fashion
NICHE_WEIGHTS = {
    "nails": 0.40,
    "hair_beauty": 0.20,
    "home_garden": 0.20,
    "fashion_style": 0.20,
}

# Niche-specific CTA options
CTA_OPTIONS = {
    "nails": [
        "Save for your next salon visit",
        "Inspo for your next mani",
        "Show this to your nail tech",
        "Save this for your nail board",
        "Perfect for your next set",
        "Your next mani is here",
        "Screenshot for your nail tech",
    ],
    "hair_beauty": [
        "Save for your next salon visit",
        "Show this to your stylist",
        "Your next look is here",
        "Hair goals right here",
        "Save this for your next appointment",
        "Bookmark this hairstyle",
    ],
    "home_garden": [
        "Save this for your dream home",
        "Pin for your next project",
        "Home inspo you need to save",
        "Your space deserves this",
        "Bookmark for your renovation",
        "Save for your next DIY weekend",
    ],
    "fashion_style": [
        "Save this outfit idea",
        "Your next look is here",
        "Add to your style board",
        "Outfit inspo for your closet",
        "Save for your next shopping trip",
        "Bookmark this look",
    ],
}

# Niche-specific image prompt prefixes for SiliconFlow
IMAGE_PROMPT_PREFIXES = {
    "nails": "Extreme close-up macro photography of fingernails, elegant nail polish and nail art, ",
    "hair_beauty": "High-fashion portrait photography of hair and hairstyle, editorial beauty shot, soft golden hour lighting, 85mm lens, ",
    "home_garden": "Interior design photography, wide angle, natural lighting, cozy warm atmosphere, high-end lifestyle magazine style, ",
    "fashion_style": "Editorial fashion photography, street style, clean minimal backdrop, natural lighting, outfit-focused composition, ",
}

# Niche-specific negative prompts for SiliconFlow
IMAGE_NEGATIVE_PROMPTS = {
    "nails": "flowers without nails, no nails, mutated hands, poorly drawn hands, extra fingers, missing fingers, malformed hands, deformed fingers, unnatural hands, bad anatomy, bad proportions, disfigured, blurry, worst quality, low quality",
    "hair_beauty": "bad anatomy, disfigured, deformed face, extra limbs, blurry, worst quality, low quality, watermark, text",
    "home_garden": "people, humans, bad architecture, blurry, worst quality, low quality, watermark, text, cluttered",
    "fashion_style": "bad anatomy, disfigured, deformed, extra limbs, blurry, worst quality, low quality, watermark, text",
}

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

def generate_content_with_gemini(topic: str = None, niche: str = "nails") -> dict:
    """
    Use Google Gemini to generate a JSON payload.
    If a topic is provided, the content will be centered on that specific trending keyword.
    The niche parameter controls which board categories and prompt style to use.
    """
    if topic:
        print(f"\n🧠 Phase 1: Generating content for trend: \"{topic}\" (niche: {niche})...")
    else:
        print(f"\n🧠 Phase 1: Generating content with Gemini (niche: {niche}, free-style)...")

    # Build list of available board categories filtered by niche
    available_categories = [
        cat for cat, info in BOARD_MAP.items()
        if info["board_id"] and info.get("niche") == niche
    ]
    # Fallback: if no boards for this niche, use all configured boards
    if not available_categories:
        available_categories = [cat for cat, info in BOARD_MAP.items() if info["board_id"]]

    category_descriptions = {
        # Nails
        "aesthetic_nail_art": "Creative, artistic, 3D, maximalist, abstract, geometric, or editorial nail art designs",
        "chrome_glazed": "Chrome nails, glazed donut finish, metallic, pearlescent, reflective, or shiny nail designs",
        "minimalist_clean": "Minimalist, clean girl aesthetic, short nails, neutral tones, milky white, micro-French, subtle elegant designs",
        "spring_trends": "Spring-themed nails: pastels, florals, bright fresh colors, seasonal trendy designs",
        "summer_vacation": "Summer vacation nails, tropical designs, bright summer colors, beach aesthetics, neon, fruit patterns",
        # Hair & Beauty
        "hair_aesthetics": "Hairstyle inspiration, trending hair looks, braids, updos, hair color trends, salon-quality styles",
        "beauty_skincare": "Beauty tips, skincare routines, makeup looks, luxury beauty products, glowing skin aesthetics",
        # Home & Garden
        "home_decor": "Interior design, minimalist decor, modern living spaces, cozy home aesthetics, room makeover ideas",
        "garden_outdoor": "Garden design, outdoor living, flower arrangements, patio ideas, landscaping, zen garden aesthetics",
        # Fashion
        "fashion_style": "Outfit inspiration, street style, seasonal fashion trends, capsule wardrobe, chic and timeless looks",
    }

    categories_prompt = "\n".join(
        f'  - "{cat}": {category_descriptions.get(cat, cat)}'
        for cat in available_categories
    )

    # Niche-specific prompt instructions
    niche_prompts = {
        "nails": {
            "role": "a creative social media strategist specializing in nail art and beauty content for Pinterest",
            "task": "come up with a UNIQUE, trendy nail art concept and provide content for a Pinterest pin",
            "image_guide": "A highly detailed, ultra-macro image generation prompt (200-400 chars). The focal point MUST be the specific nail design, patterns, and textures. Force a tight, close-up shot of the nails themselves, with minimal hand visibility and no distracting background. Use terms like 'high-resolution jewelry photography', 'extreme close-up on nail art', 'sharp focus'. Specify the exact finish (glossy, matte, iridescent) and any 3D elements clearly.",
        },
        "hair_beauty": {
            "role": "a creative social media strategist specializing in hair styling, beauty trends, and aesthetic content for Pinterest",
            "task": "come up with a UNIQUE, trendy hairstyle or beauty concept and provide content for a Pinterest pin",
            "image_guide": "A highly detailed portrait photography prompt (200-400 chars). Focus on the hairstyle, hair texture, and styling. Describe the hair type, length, color, and specific style (braids, curls, updo, etc). Use terms like 'editorial beauty photography', 'soft golden hour lighting', '85mm portrait lens', 'salon-quality finish'. Include atmosphere and setting details.",
        },
        "home_garden": {
            "role": "a creative social media strategist specializing in interior design, home decor, and garden aesthetics for Pinterest",
            "task": "come up with a UNIQUE, trendy home decor or garden design concept and provide content for a Pinterest pin",
            "image_guide": "A highly detailed interior/exterior photography prompt (200-400 chars). Focus on the space, materials, colors, and atmosphere. Use terms like 'Architectural Digest style photography', 'natural ambient lighting', 'wide-angle lens', 'cozy warm atmosphere'. Describe specific furniture, plants, textures, and design elements.",
        },
        "fashion_style": {
            "role": "a creative social media strategist specializing in fashion, outfit styling, and trend forecasting for Pinterest",
            "task": "come up with a UNIQUE, trendy outfit or fashion concept and provide content for a Pinterest pin",
            "image_guide": "A highly detailed fashion photography prompt (200-400 chars). Focus on the outfit composition, styling, colors, and silhouette. Use terms like 'editorial street style photography', 'clean minimal backdrop', 'natural lighting', 'outfit-focused composition'. Describe specific garments, accessories, and the overall aesthetic vibe.",
        },
    }

    niche_config = niche_prompts.get(niche, niche_prompts["nails"])

    topic_instruction = ""
    if topic:
        topic_instruction = f"""
MANDATORY CONTEXT: The pin must be about "{topic}". 
- The title must capture the essence of "{topic}".
- The description must use "{topic}" as the primary focus keyword.
- The image_prompt must describe a detailed visual that represents "{topic}".
"""

    system_prompt = f"""You are {niche_config['role']}.
Your task is to {niche_config['task']}.
{topic_instruction}

RETURN ONLY VALID JSON (no markdown, no code fences) with these exact keys:
{{
  "board_category": "MANDATORY: Pick the key from the list below that BEST matches the content.",
  "title": "A short, catchy, click-worthy Pinterest title (max 100 chars). Use emojis sparingly.",
  "overlay_text": "A tiny, very catchy 3-5 word phrase for the text overlay on the image itself.",
  "description": "An SEO-optimized Pinterest description (150-300 chars). You MUST include exactly 10 highly relevant and trending hashtags at the very end.",
  "image_prompt": "{niche_config['image_guide']}"
}}

Available board categories (pick the MOST relevant key):
{categories_prompt}

Ensure the 'board_category' value in your JSON response is EXACTLY one of the keys listed above."""

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
    for key in ("board_category", "title", "overlay_text", "description", "image_prompt"):
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
    
    # Enforce basic SEO tags based on niche
    niche_hashtags = {
        "nails": ["#nailart", "#nails"],
        "hair_beauty": ["#hairstyle", "#hairinspo"],
        "home_garden": ["#homedecor", "#interiordesign"],
        "fashion_style": ["#fashion", "#outfitinspo"],
    }
    for tag in niche_hashtags.get(niche, ["#aesthetic"]):
        if tag not in content["description"].lower():
            content["description"] += f" {tag}"

    print(f"   📝 Description: {content['description'][:80]}...")
    print(f"   🎨 Image Prompt: {content['image_prompt'][:80]}...")
    return content


# ============================================================================
# PHASE 2: THE ARTIST — SiliconFlow API (FLUX.1-schnell)
# ============================================================================

def generate_image_with_siliconflow(image_prompt: str, output_dir: str, niche: str = "nails") -> str:
    """
    Send the image prompt to SiliconFlow's Kolors model.
    Downloads the generated vertical image to a local file.
    Uses niche-specific prompt prefixes and negative prompts.
    Returns the path to the downloaded image.
    """
    print(f"\n🎨 Phase 2: Generating image with SiliconFlow (niche: {niche})...")

    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }

    prefix = IMAGE_PROMPT_PREFIXES.get(niche, IMAGE_PROMPT_PREFIXES["nails"])
    negative = IMAGE_NEGATIVE_PROMPTS.get(niche, IMAGE_NEGATIVE_PROMPTS["nails"])
    enhanced_prompt = prefix + image_prompt + ", highly detailed, masterpiece, best quality"
    
    payload = {
        "model": SILICONFLOW_MODEL,
        "prompt": enhanced_prompt,
        "negative_prompt": negative,
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

def design_pin_image(image_path: str, overlay_text: str, output_dir: str) -> str:
    """
    Open the raw image, apply a sophisticated overlay, and render the text
    in a premium font with better typography, plus a CTA and branding.
    """
    print("\n🎨 Phase 3: Designing the Pinterest pin with Pillow (Premium Style)...")

    # Clean the overlay_text to avoid tofu characters
    overlay_text = clean_text_for_rendering(overlay_text)

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
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "Montserrat-Bold.ttf")

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

    # Dynamic text wrapping using PIL textbbox
    margin = int(width * 0.08)
    max_text_width = width - (2 * margin)
    
    # Scale down font if there's a huge word
    longest_word = max(overlay_text.split(), key=len) if overlay_text.split() else ""
    while font_size > 20: # Prevent font from getting completely unreadable
        bbox = draw.textbbox((0, 0), longest_word, font=font)
        if (bbox[2] - bbox[0]) < max_text_width:
            break
        font_size -= 4
        try:
            if hasattr(font, 'path'): # if it's a FreeTypeFont
                font = ImageFont.truetype(font.path, font_size)
        except:
            break

    words = overlay_text.split()
    wrapped_lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        line_text = " ".join(current_line)
        bbox = draw.textbbox((0, 0), line_text, font=font)
        line_width = bbox[2] - bbox[0]
        
        if line_width > max_text_width:
            if len(current_line) == 1:
                wrapped_lines.append(current_line.pop())
            else:
                current_line.pop()
                wrapped_lines.append(" ".join(current_line))
                current_line = [word]
                
    if current_line:
        wrapped_lines.append(" ".join(current_line))

    # Text Layout Refinement
    line_spacing = 1.15
    line_height = int(font_size * line_spacing)
    total_text_height = len(wrapped_lines) * line_height
    # Leave room at bottom for CTA and branding
    text_y_start = height - total_text_height - int(height * 0.18)

    for i, line in enumerate(wrapped_lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2
        text_y = text_y_start + (i * line_height)

        # Subtle shadow for depth
        draw.text((text_x + 2, text_y + 2), line, font=font, fill=(0, 0, 0, 100))
        # Main white text
        draw.text((text_x, text_y), line, font=font, fill=(255, 255, 255, 255))

    # --- Add Call to Action (CTA) ---
    cta_niche = getattr(design_pin_image, '_current_niche', 'nails')
    cta_list = CTA_OPTIONS.get(cta_niche, CTA_OPTIONS["nails"])
    cta_text = random.choice(cta_list)
    try:
        cta_font_size = int(width * 0.045)
        cta_font_path = os.path.join(os.path.dirname(__file__), "fonts", "Montserrat-Bold.ttf")
        cta_font = ImageFont.truetype(cta_font_path, cta_font_size) if os.path.exists(cta_font_path) else font
        
        cta_bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
        cta_w = cta_bbox[2] - cta_bbox[0]
        cta_x = (width - cta_w) // 2
        cta_y = text_y_start + total_text_height + int(height * 0.03)
        
        draw.text((cta_x + 1, cta_y + 1), cta_text, font=cta_font, fill=(0, 0, 0, 150))
        draw.text((cta_x, cta_y), cta_text, font=cta_font, fill=(255, 220, 220, 255)) # Soft pink CTA
    except: pass

    # --- Add Branding Badge (Nailosmetic) ---
    try:
        brand_font_size = int(width * 0.035)
        brand_font_path = os.path.join(os.path.dirname(__file__), "fonts", "Montserrat-Regular.ttf")
        brand_font = ImageFont.truetype(brand_font_path, brand_font_size) if os.path.exists(brand_font_path) else font
        if brand_font:
            brand_text = "Aesthetic Daily"
            brand_bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
            bw, bh = brand_bbox[2] - brand_bbox[0], brand_bbox[3] - brand_bbox[1]

            bx = (width - bw) // 2
            by = height - bh - int(height * 0.03)
            # Use regular spacing and subtle opacity
            draw.text((bx, by), brand_text, font=brand_font, fill=(255, 255, 255, 160))
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

def select_niche_weighted() -> str:
    """Select a niche using weighted random distribution."""
    niches = list(NICHE_WEIGHTS.keys())
    weights = list(NICHE_WEIGHTS.values())
    return random.choices(niches, weights=weights, k=1)[0]


def main():
    """Execute the full automation pipeline."""
    print("=" * 60)
    print("✨ Aesthetic Daily — Pinterest Automation Bot v2.0")
    print("=" * 60)

    # Validate environment
    validate_env_vars()

    # Create a temporary directory for image processing
    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"\n📁 Working directory: {tmp_dir}")

        # --- TOPIC & LINK RESOLUTION ---
        queue_path = Path("shared/links_queue.json")
        topic_bank_path = Path("shared/topic_bank.json")
        used_topics_path = Path("shared/used_topics.json")
        
        chosen_topic = None
        chosen_niche = None
        destination_link = None
        
        # 1. Try to get topic and link from WordPress Queue
        if queue_path.exists():
            try:
                with open(queue_path, "r") as f:
                    queue = json.load(f)
                if queue:
                    queued_item = queue.pop(0)  # FIFO
                    destination_link = queued_item.get("url")
                    chosen_topic = queued_item.get("topic")
                    # Determine niche from the queued category
                    queued_category = queued_item.get("category", "").lower()
                    if "hair" in queued_category or "beauty" in queued_category:
                        chosen_niche = "hair_beauty"
                    elif "home" in queued_category or "garden" in queued_category:
                        chosen_niche = "home_garden"
                    elif "fashion" in queued_category or "style" in queued_category:
                        chosen_niche = "fashion_style"
                    else:
                        chosen_niche = "nails"
                    print(f"   🔥 Synchronizing with WordPress Article: {destination_link}")
                    print(f"   🎯 Topic from Queue: \"{chosen_topic}\" (niche: {chosen_niche})")
                    
                    # Update queue file
                    with open(queue_path, "w") as f:
                        json.dump(queue, f, indent=4)
            except Exception as e:
                print(f"   ⚠️ Error reading links_queue.json: {e}")

        # 2. If no queued item, pick a niche and fresh topic from the bank
        if not chosen_topic and topic_bank_path.exists():
            try:
                with open(topic_bank_path, "r") as f:
                    topic_bank = json.load(f)
                
                used_topics = []
                if used_topics_path.exists():
                    with open(used_topics_path, "r") as f:
                        used_topics = json.load(f)
                
                # New niche-aware topic bank format (dict of niche -> list)
                if isinstance(topic_bank, dict):
                    # Select niche via weighted random
                    chosen_niche = select_niche_weighted()
                    niche_topics = topic_bank.get(chosen_niche, [])
                    
                    # Also merge gardening into home_garden
                    if chosen_niche == "home_garden":
                        niche_topics = niche_topics + topic_bank.get("gardening", [])
                    
                    available_topics = [t for t in niche_topics if t not in used_topics]
                    if available_topics:
                        chosen_topic = random.choice(available_topics)
                        print(f"   🎯 Niche: {chosen_niche} | Topic: \"{chosen_topic}\"")
                    else:
                        # Niche exhausted, try any available topic
                        all_available = []
                        for niche_key, topics in topic_bank.items():
                            for t in topics:
                                if t not in used_topics:
                                    all_available.append((niche_key, t))
                        if all_available:
                            chosen_niche, chosen_topic = random.choice(all_available)
                            print(f"   📋 {chosen_niche} exhausted. Fallback topic: \"{chosen_topic}\"")
                        else:
                            print("   📋 All topics exhausted! Picking random.")
                            chosen_niche = select_niche_weighted()
                            niche_topics = topic_bank.get(chosen_niche, [])
                            chosen_topic = random.choice(niche_topics) if niche_topics else None
                else:
                    # Legacy flat list format (backwards compatible)
                    chosen_niche = "nails"
                    available_topics = [t for t in topic_bank if t not in used_topics]
                    if available_topics:
                        chosen_topic = random.choice(available_topics)
                        print(f"   🎯 High-demand topic selected: \"{chosen_topic}\"")
                    else:
                        chosen_topic = random.choice(topic_bank)
            except Exception as e:
                print(f"   ⚠️ Error loading topic bank: {e}")

        # Default niche if not set
        if not chosen_niche:
            chosen_niche = "nails"

        # Phase 1: Generate content with Gemini (niche-aware)
        content = generate_content_with_gemini(topic=chosen_topic, niche=chosen_niche)

        # Resolve the target board
        category = content["board_category"]
        board_info = BOARD_MAP.get(category, BOARD_MAP[DEFAULT_BOARD_CATEGORY])

        # If the chosen board isn't configured, fall back to default
        if not board_info["board_id"]:
            print(f"   ⚠️  Board for '{category}' not configured, falling back to '{DEFAULT_BOARD_CATEGORY}'")
            category = DEFAULT_BOARD_CATEGORY
            board_info = BOARD_MAP[category]

        # Use fallback link if not set by queue
        if not destination_link:
            destination_link = board_info["link"]
            print(f"   🔗 Using default board link: {destination_link}")

        target_board_id = board_info["board_id"]
        print(f"\n   🎯 Routing pin to: {board_info['name']} (niche: {chosen_niche})")

        # Phase 2: Generate image with SiliconFlow (niche-aware)
        raw_image_path = generate_image_with_siliconflow(
            content["image_prompt"], tmp_dir, niche=chosen_niche
        )

        # Phase 3: Design the pin with Pillow
        # Pass niche info to design function via attribute for CTA selection
        design_pin_image._current_niche = chosen_niche
        final_image_path = design_pin_image(
            raw_image_path, content["overlay_text"], tmp_dir
        )

        # Phase 4: Publish to Pinterest
        result = publish_to_pinterest(
            final_image_path, content["title"], content["description"],
            board_id=target_board_id, destination_link=destination_link
        )

        # Mark topic as used so we don't repeat it soon
        if chosen_topic:
            try:
                used_topics = []
                if used_topics_path.exists():
                    with open(used_topics_path, "r") as f:
                        used_topics = json.load(f)
                
                if chosen_topic not in used_topics:
                    used_topics.append(chosen_topic)
                    with open(used_topics_path, "w") as f:
                        json.dump(used_topics, f, indent=4)
                    print(f"   📋 Topic \"{chosen_topic}\" marked as used.")
            except Exception as e:
                print(f"   ⚠️ Error updating used topics: {e}")

    print("\n" + "=" * 60)
    print(f"✨ Pipeline complete! Your {chosen_niche} pin is live on Pinterest.")
    print("=" * 60)


if __name__ == "__main__":
    main()
