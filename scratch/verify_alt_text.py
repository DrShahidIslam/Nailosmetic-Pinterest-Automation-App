import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

def verify_pinterest_alt_text():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEYS").split(",")[0]
    client = genai.Client(api_key=api_key)
    
    # Mock system prompt extract from main.py after my changes
    niche = "nails"
    image_guide = "A highly detailed image generation prompt (200-400 chars). MANDATORY RULE: The image MUST show a real woman's hand/fingers with painted nails as the PRIMARY SUBJECT."
    
    system_prompt = f"""You are a creative social media strategist...
    RETURN ONLY VALID JSON with these exact keys:
    {{
      "board_category": "aesthetic_nail_art",
      "title": "A short Pinterest title",
      "overlay_text": "Catchy phrase",
      "description": "SEO description with hashtags",
      "image_prompt": "{image_guide}",
      "alt_text": "A highly descriptive 1-2 sentence description of the visual elements (colors, textures, subjects) for Pinterest accessibility. Focus on visual details, not SEO keywords."
    }}
    Topic: "midnight velvet nails"
    """
    
    print("\n--- Verifying Pinterest Alt-Text Generation ---")
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=system_prompt,
        )
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw_text)
        if "alt_text" in data:
            print(f"   SUCCESS: Alt-Text generated!")
            print(f"   📝 Alt-Text: {data['alt_text']}")
        else:
            print(f"   FAILURE: Alt-Text missing from JSON response.")
    except Exception as e:
        print(f"   Error during verification: {e}")

if __name__ == "__main__":
    verify_pinterest_alt_text()
