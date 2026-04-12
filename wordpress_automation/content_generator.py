import json
import random
import re
import time
import uuid
from typing import Dict, Any, List, Optional
from google import genai

class ContentGenerator:
    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]

    def _generate_kadence_id(self) -> str:
        """Generates a random Kadence-style unique ID."""
        return f"{random.randint(100, 999)}_{uuid.uuid4().hex[:6]}-{uuid.uuid4().hex[:2]}"

    def generate_article_plan(self, existing_categories: List[str], previous_slugs: List[str]) -> Dict[str, Any]:
        """
        Use Gemini to generate the article structure, title, image prompts, and SEO metadata.
        """
        categories_str = ", ".join(existing_categories)
        internal_link_slug = random.choice(previous_slugs) if previous_slugs else "spring-nail-designs-inspo"
        
        system_prompt = f"""You are a luxury beauty editor for 'Nailosmetic'. 
Your task is to create a high-quality, SEO-optimized nail art listicle article for a WordPress site using Kadence Blocks and RankMath SEO.

Available WordPress Categories: {categories_str}
Internal Link Target: https://nailosmetic.com/{internal_link_slug}/

FRAMEWORK REQUIREMENTS:
1. Title: Catchy, SEO-optimized (e.g., '25+ Stunning Spring Nail Designs...').
2. Slug: A short, SEO-friendly URL slug (3-5 words maximum, lowercase-with-dashes). It MUST include the primary focus keyword.
3. SEO Metadata (RankMath):
   - Focus Keyword: The primary keyword for the article.
   - SEO Title: Optimized title for search results (max 60 chars).
   - Meta Description: Compelling summary for search results (120-160 chars).
3. Featured Image: Wide (16:9) prompt focusing on a luxury lifestyle scene that includes a prominent view of a detailed manicure (e.g., 'A woman's hand holding a designer bag, focusing on the vibrant [color] nails').
4. Introduction: 2-3 paragraphs. You MUST include exactly one internal link to 'https://nailosmetic.com/{internal_link_slug}/' using natural anchor text.
5. Content Blocks: A list of 3 to 7 items. Each item must have:
   - Image Prompt: STRICT REQUIREMENT: Must be a macro, extreme closeup shot of a woman's hand/fingers showing the specific nail design in sharp detail. Vertical (4:5) aspect ratio.
   - Image Alt Text: Descriptive.
   - Heading (H2): Trendy name for the design.
   - Paragraph: Engaging description.
   - Details: 3 specific points (Vibe, Technique/Pro-Tip, Best Shape/Alternative).
6. Conclusion: A summary encouraging interaction.
7. Category: Pick the BEST existing category or suggest 1 NEW category only if none fit.

RETURN ONLY VALID JSON:
{{
  "title": "string",
  "slug": "string",
  "seo": {{
    "focus_keyword": "string",
    "title": "string",
    "description": "string"
  }},
  "category_suggestion": "string",
  "is_new_category": boolean,
  "featured_image": {{
    "prompt": "string",
    "alt_text": "string"
  }},
  "introduction": "string (plain text or simple HTML)",
  "blocks": [
    {{
      "heading": "string",
      "prompt": "string",
      "alt_text": "string",
      "paragraph": "string",
      "details": {{
         "vibe": "string",
         "technique": "string",
         "secondary": "string"
      }}
    }}
  ],
  "conclusion": "string"
}}
"""
        # ... logic for Gemini calls (unchanged but using system_prompt)
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
                        if "404" in error_str or "limit: 0" in error_str:
                            print(f"   ⚠️  Model {current_model} unavailable or zero quota, skipping...")
                            break
                        wait_time = 15 * (attempt + 1)
                        if "429" in error_str:
                            match = re.search(r"Please retry in ([\d\.]+)s", error_str)
                            if match:
                                requested_delay = float(match.group(1))
                                wait_time = max(wait_time, requested_delay + 2.0)
                        time.sleep(wait_time)
                if success: break
            if success: break
        if not success: raise Exception("❌ Gemini API failed permanently.")
        raw_text = re.sub(r"```json\s*|\s*```", "", raw_text)
        try:
            return json.loads(raw_text)
        except Exception as e:
            print(f"Error parsing Gemini response: {e}")
            raise e

    def build_html_content(self, plan: Dict[str, Any]) -> str:
        """
        Convert the JSON plan into Kadence Blocks BeautifulSoup-style HTML.
        """
        col_id_intro = self._generate_kadence_id()
        html = f"""<!-- wp:kadence/column {{"uniqueID":"{col_id_intro}"}} -->
<div class="wp-block-kadence-column kadence-column{col_id_intro}"><div class="kt-inside-inner-col">
<!-- wp:paragraph -->
{plan['introduction']}
<!-- /wp:paragraph -->
<!-- wp:kadence/tableofcontents {{"uniqueID":"{self._generate_kadence_id()}"}} /-->
</div></div>
<!-- /wp:kadence/column -->
"""
        
        for block in plan['blocks']:
            row_id = self._generate_kadence_id()
            h_id = self._generate_kadence_id()
            img_id = self._generate_kadence_id()
            list_id = self._generate_kadence_id()
            
            html += f"""
<!-- wp:kadence/column {{"uniqueID":"{self._generate_kadence_id()}"}} -->
<div class="wp-block-kadence-column"><div class="kt-inside-inner-col">
<!-- wp:kadence/rowlayout {{"uniqueID":"{row_id}","columns":1,"maxWidth":800}} -->
<!-- wp:kadence/column {{"uniqueID":"{self._generate_kadence_id()}"}} -->
<div class="wp-block-kadence-column"><div class="kt-inside-inner-col">

<!-- wp:kadence/advancedheading {{"uniqueID":"{h_id}"}} -->
<h2 class="kt-adv-heading{h_id} wp-block-kadence-advancedheading">{block['heading']}</h2>
<!-- /wp:kadence/advancedheading -->

<!-- wp:kadence/image {{"uniqueID":"{img_id}"}} -->
<figure class="wp-block-kadence-image kb-image{img_id}">
    <!-- IMAGE_PLACEHOLDER_{block['heading']} -->
</figure>
<!-- /wp:kadence/image -->

<!-- wp:paragraph -->
<p>{block['paragraph']}</p>
<!-- /wp:paragraph -->

<!-- wp:kadence/iconlist {{"uniqueID":"{list_id}"}} -->
<div class="wp-block-kadence-iconlist kt-svg-icon-list-items kt-svg-icon-list-items{list_id} kt-svg-icon-list-columns-1 alignnone"><ul class="kt-svg-icon-list"><!-- wp:kadence/listitem {{"uniqueID":"{self._generate_kadence_id()}"}} -->
<li class="wp-block-kadence-listitem kt-svg-icon-list-item-wrap kt-svg-icon-list-item-{list_id}"><span data-name="USE_PARENT_DEFAULT_ICON" data-stroke="USE_PARENT_DEFAULT_WIDTH" data-class="kt-svg-icon-list-single" class="kadence-dynamic-icon"></span><span class="kt-svg-icon-list-text"><strong>The Vibe:</strong> {block['details'].get('vibe', '')}</span></li>
<!-- /wp:kadence/listitem -->

<!-- wp:kadence/listitem {{"uniqueID":"{self._generate_kadence_id()}"}} -->
<li class="wp-block-kadence-listitem kt-svg-icon-list-item-wrap kt-svg-icon-list-item-{list_id}"><span data-name="USE_PARENT_DEFAULT_ICON" data-stroke="USE_PARENT_DEFAULT_WIDTH" data-class="kt-svg-icon-list-single" class="kadence-dynamic-icon"></span><span class="kt-svg-icon-list-text"><strong>Technique:</strong> {block['details'].get('technique', '')}</span></li>
<!-- /wp:kadence/listitem -->

<!-- wp:kadence/listitem {{"uniqueID":"{self._generate_kadence_id()}"}} -->
<li class="wp-block-kadence-listitem kt-svg-icon-list-item-wrap kt-svg-icon-list-item-{list_id}"><span data-name="USE_PARENT_DEFAULT_ICON" data-stroke="USE_PARENT_DEFAULT_WIDTH" data-class="kt-svg-icon-list-single" class="kadence-dynamic-icon"></span><span class="kt-svg-icon-list-text"><strong>Pro Tip:</strong> {block['details'].get('secondary', '')}</span></li>
<!-- /wp:kadence/listitem --></ul></div>
<!-- /wp:kadence/iconlist -->

</div></div>
<!-- /wp:kadence/column -->
<!-- /wp:kadence/rowlayout -->

<!-- wp:spacer {{"height":"40px"}} -->
<div style="height:40px" aria-hidden="true" class="wp-block-spacer"></div>
<!-- /wp:spacer -->
</div></div>
<!-- /wp:kadence/column -->
"""
        
        concl_id = self._generate_kadence_id()
        html += f"""
<!-- wp:kadence/column {{"uniqueID":"{concl_id}"}} -->
<div class="wp-block-kadence-column kadence-column{concl_id}"><div class="kt-inside-inner-col">
<!-- wp:kadence/advancedheading {{"uniqueID":"{self._generate_kadence_id()}"}} -->
<h2 class="wp-block-kadence-advancedheading">The Conclusion</h2>
<!-- /wp:kadence/advancedheading -->
<!-- wp:paragraph -->
<p>{plan['conclusion']}</p>
<!-- /wp:paragraph -->
</div></div>
<!-- /wp:kadence/column -->
"""
        return html
