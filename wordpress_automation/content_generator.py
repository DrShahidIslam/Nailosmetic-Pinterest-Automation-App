import json
import random
import re
import time
from typing import Dict, Any, List, Optional
from google import genai

class ContentGenerator:
    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]

    def generate_article_plan(self, existing_categories: List[str], previous_slugs: List[str]) -> Dict[str, Any]:
        """
        Use Gemini to generate the article structure, title, and image prompts.
        Includes robust retry logic and multi-key support.
        """
        categories_str = ", ".join(existing_categories)
        internal_link_slug = random.choice(previous_slugs) if previous_slugs else "spring-nail-designs-inspo"
        
        system_prompt = f"""You are a luxury beauty editor for 'Nailosmetic'. 
Your task is to create a high-quality nail art listicle article following a specific framework.

Available WordPress Categories: {categories_str}
Internal Link Target: https://nailosmetic.com/{internal_link_slug}/

FRAMEWORK REQUIREMENTS:
1. Title: Catchy, SEO-optimized (e.g., '25+ Stunning Spring Nail Designs...').
2. Featured Image: Wide (16:9) 'luxury holiday' aesthetic prompt + Alt Text.
3. Introduction: 2-3 paragraphs. You MUST include exactly one internal link to 'https://nailosmetic.com/{internal_link_slug}/' using natural anchor text.
4. Content Blocks: A list of 3 to 7 items. Each item must have:
   - Image Prompt: Macro photography, vertical (4:5) aspect ratio.
   - Image Alt Text: Descriptive.
   - Heading (H2): Trendy name for the design.
   - Paragraph: Engaging description.
   - Bullet Points: 3 specific points (e.g., Vibe, Tip, Products).
5. Conclusion: A summary encouraging interaction.
6. Category: Pick the BEST existing category or suggest 1 NEW category only if none fit.

RETURN ONLY VALID JSON:
{{
  "title": "string",
  "category_suggestion": "string (name of category)",
  "is_new_category": boolean,
  "featured_image": {{
    "prompt": "string (16:9 prompt)",
    "alt_text": "string"
  }},
  "introduction": "string (HTML allowed, include the internal link)",
  "blocks": [
    {{
      "heading": "string",
      "prompt": "string (4:5 prompt)",
      "alt_text": "string",
      "paragraph": "string",
      "bullets": ["string", "string", "string"]
    }}
  ],
  "conclusion": "string"
}}

AESTHETIC NOTE: High definition, aesthetic, luxury editorial vibe. Focus on textures and vibrant colors.
"""
        
        success = False
        raw_text = ""
        max_retries_per_model = 3

        for api_key in self.api_keys:
            key_preview = f"...{api_key[-4:]}" if len(api_key) > 4 else "***"
            print(f"   🔄 Attempting generation with API Key ending in {key_preview}")
            client = genai.Client(api_key=api_key)
            
            for current_model in self.models_to_try:
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
                        # Handle model unavailability or quota exhaustion (permanent per model)
                        if "404" in error_str or "limit: 0" in error_str:
                            print(f"   ⚠️  Model {current_model} unavailable or zero quota, skipping...")
                            break
                        
                        # Handle rate limiting with backoff
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
            raise Exception("❌ Gemini API failed permanently across all provided API keys and models.")

        # Clean potential markdown fences
        raw_text = re.sub(r"```json\s*|\s*```", "", raw_text)
        
        try:
            return json.loads(raw_text)
        except Exception as e:
            print(f"Error parsing Gemini response: {e}")
            print(f"Raw response: {raw_text[:500]}...")
            raise e

    def build_html_content(self, plan: Dict[str, Any]) -> str:
        """
        Convert the JSON plan into structured HTML for WordPress.
        """
        html = f"<div class='article-intro'>{plan['introduction']}</div>\n\n"
        
        for block in plan['blocks']:
            html += f"<div class='wp-block-image-text'>\n"
            html += f"  <!-- IMAGE_PLACEHOLDER_{block['heading']} -->\n" # Placeholder for image replacement later
            html += f"  <h2>{block['heading']}</h2>\n"
            html += f"  <p>{block['paragraph']}</p>\n"
            html += "  <ul>\n"
            for bullet in block['bullets']:
                html += f"    <li>{bullet}</li>\n"
            html += "  </ul>\n"
            html += "  <div style='height:40px' aria-hidden='true' class='wp-block-spacer'></div>\n"
            html += f"</div>\n\n"
            
        html += f"<div class='article-conclusion'>{plan['conclusion']}</div>"
        return html
