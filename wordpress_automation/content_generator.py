import json
import random
import re
from typing import Dict, Any, List, Optional
from google import genai

class ContentGenerator:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.0-flash" # High speed/quality balance

    def generate_article_plan(self, existing_categories: List[str], previous_slugs: List[str]) -> Dict[str, Any]:
        """
        Use Gemini to generate the article structure, title, and image prompts.
        """
        categories_str = ", ".join(existing_categories)
        internal_link_slug = random.choice(previous_slugs) if previous_slugs else "spring-nail-designs-inspo"
        
        prompt = f"""You are a luxury beauty editor for 'Nailosmetic'. 
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
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        
        raw_text = response.text.strip()
        # Clean potential markdown fences
        raw_text = re.sub(r"```json\s*|\s*```", "", raw_text)
        
        try:
            return json.loads(raw_text)
        except Exception as e:
            print(f"Error parsing Gemini response: {e}")
            print(f"Raw response: {raw_text}")
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
