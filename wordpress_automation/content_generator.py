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
        self.models_to_try = ["gemini-3.1-flash-lite-preview", "gemini-2.0-flash", "gemini-1.5-flash"]

    def _generate_kadence_id(self) -> str:
        """Generates a random Kadence-style unique ID."""
        return f"{random.randint(100, 999)}_{uuid.uuid4().hex[:6]}-{uuid.uuid4().hex[:2]}"

    def generate_article_plan(self, existing_categories: List[str], previous_slugs: List[str], topic: str = None, niche: str = "nails") -> Dict[str, Any]:
        """
        Use Gemini to generate the article structure, title, image prompts, and SEO metadata.
        If a topic is provided, the article will be based on that specific high-demand topic.
        The niche parameter controls the content style and image generation approach.
        """
        categories_str = ", ".join(existing_categories)
        
        # Define niche to primary pillar mapping (Hubs)
        niche_primary_pillars = {
            "nails": "nail-art-designs-ultimate-guide",
            "hair_beauty": "hairstyles-for-women-ultimate-guide",
            "home_garden": "home-decor-ideas-ultimate-guide",
            "fashion_style": "spring-outfits-women-guide"
        }
        
        # Hardcoded high-authority secondary pillars for fallback
        niche_secondary_pillars = {
            "nails": ["chrome-nails-complete-guide", "spring-nail-designs-inspo", "pearl-nail-designs-trends"],
            "hair_beauty": ["wolf-cut-hairstyles-guide", "goddess-braids-styles", "ultimate-box-braids-styles"],
            "home_garden": ["concrete-block-garden-beds", "small-bathroom-makeover-ideas", "front-yard-landscaping-ideas"],
            "fashion_style": ["chic-spring-outfits-women", "casual-spring-outfit-ideas", "perfect-leggings-outfits"]
        }
        
        # 1. Link 1 is always the primary pillar for the active niche (Hub-and-Spoke model)
        primary_pillar = niche_primary_pillars.get(niche, "nail-art-designs-ultimate-guide")
        
        # 2. Link 2 & Link 3 are dynamic same-niche sibling posts from published_links.json
        sibling_slugs = []
        try:
            from pathlib import Path
            published_links_path = Path(__file__).parent.parent / "shared" / "published_links.json"
            if published_links_path.exists():
                with open(published_links_path, "r", encoding="utf-8") as f:
                    published_data = json.load(f)
                # Select slugs from published_links belonging to the active niche
                sibling_slugs = [p["slug"] for p in published_data if p.get("niche") == niche and p.get("slug")]
        except Exception as e:
            print(f"   ⚠️ Error reading published_links.json for content generator: {e}")
            
        # Filter out the primary pillar to avoid duplicate links in the same post
        sibling_slugs = [s for s in sibling_slugs if s != primary_pillar]
        
        # Prioritize recently published sibling posts (newest first) by reversing
        sibling_slugs = list(dict.fromkeys(reversed(sibling_slugs)))
        
        # Extract up to 2 unique sibling posts
        additional_links = []
        for s in sibling_slugs:
            if len(additional_links) >= 2:
                break
            if s not in additional_links:
                additional_links.append(s)
                
        # Fallback to secondary pillars of the active niche if we need more links
        sec_pillars = niche_secondary_pillars.get(niche, niche_secondary_pillars["nails"])
        for p in sec_pillars:
            if len(additional_links) >= 2:
                break
            if p != primary_pillar and p not in additional_links:
                additional_links.append(p)
                
        # Final fallback to general previous slugs if still lacking links
        if len(additional_links) < 2:
            for s in previous_slugs:
                if len(additional_links) >= 2:
                    break
                if s != primary_pillar and s not in additional_links:
                    additional_links.append(s)
                    
        # Slice to ensure we have exactly 2 additional slugs
        additional_links = additional_links[:2]
        
        # Construct the final list of 3 unique slugs
        internal_links = [primary_pillar] + additional_links
        
        link1, link2, link3 = [f"https://nailosmetic.com/{s}/" for s in internal_links]
        
        topic_instruction = ""
        if topic:
            topic_instruction = f"""
MANDATORY TOPIC: You MUST write the article about "{topic}". 
The title, all content blocks, all image prompts, and SEO metadata must be directly about "{topic}".
Do NOT deviate from this topic. This is a high-demand search term that real users are searching for.
"""
        
        # Niche-specific prompt configurations with isolated external link targets
        niche_configs = {
            "nails": {
                "role": "a luxury beauty editor for 'Nailosmetic'",
                "article_type": "a high-quality, SEO-optimized nail art listicle article",
                "featured_image_guide": "Wide (16:9) prompt. MUST show a close-up of a real woman's beautifully manicured hand in a luxury setting (e.g., holding a cocktail, resting on marble). The NAILS with nail art must be the focal point — never generate flowers, objects, or textures without nails visible.",
                "block_image_guide": "MANDATORY RULE: Every prompt MUST show a real woman's hand/fingers with the specific nail art design as the PRIMARY SUBJECT. The nails must take up at least 60 percent of the image. If the heading mentions a theme (e.g., 'dew drop', 'butterfly', 'floral'), that theme must appear AS A DESIGN PAINTED ON THE NAILS, not as a standalone object. Describe: nail shape (almond/coffin/stiletto/square), colors, finish (glossy/matte/chrome), specific pattern ON the nails. Example: 'Extreme macro close-up of almond nails with glossy chrome rose gold finish, one accent nail with tiny dried flowers encapsulated in clear gel'.",
                "block_details": "Vibe, Technique/Pro-Tip, Best Shape/Alternative",
                "mandatory_category": "Aesthetic & Art, Chrome & Glazed, Minimalist & Clean Girl, or Seasonal Trends (Use 'Nails and Manicure' only as fallback)",
                "external_sources": "Allure (allure.com), Byrdie (byrdie.com), InStyle (instyle.com), Vogue (vogue.com), Harper's Bazaar (harpersbazaar.com)"
            },
            "hair_beauty": {
                "role": "a celebrity hairstylist and beauty editor for 'Nailosmetic'",
                "article_type": "a high-quality, SEO-optimized hairstyle and beauty listicle article",
                "featured_image_guide": "Wide (16:9) prompt. MUST show a portrait of a real person with stunning, styled hair as the focal point. Soft editorial lighting, salon-quality finish. The HAIR and hairstyle must be clearly visible.",
                "block_image_guide": "MANDATORY RULE: Every prompt MUST show a real person with their HAIRSTYLE as the PRIMARY SUBJECT. The hair must be clearly visible, styled, and take up the majority of the frame. If the heading names a style (e.g., 'fulani braids', 'prom updo'), the person must be WEARING that exact hairstyle. Describe: hair type/texture, length, color, specific styling details. Use terms like 'editorial beauty portrait', 'soft golden hour lighting', '85mm lens'.",
                "block_details": "The Vibe, Styling Technique, Best Face Shape/Hair Type",
                "mandatory_category": "Hair & Beauty",
                "external_sources": "Allure (allure.com), Byrdie (byrdie.com), InStyle (instyle.com), Vogue (vogue.com), Cosmopolitan (cosmopolitan.com)"
            },
            "home_garden": {
                "role": "an interior design and lifestyle editor for 'Nailosmetic'",
                "article_type": "a high-quality, SEO-optimized home decor or garden design listicle article",
                "featured_image_guide": "Wide (16:9) prompt. MUST show a beautifully designed, fully decorated interior space or garden. The SPACE must be the focal point, styled like Architectural Digest. Wide-angle composition, natural ambient lighting.",
                "block_image_guide": "MANDATORY RULE: Every prompt MUST show a real, fully decorated ROOM or GARDEN SPACE as the PRIMARY SUBJECT. The space must look realistic, lived-in, and styled — never an isolated object on a white background. If the heading names a specific element (e.g., 'front porch flower pots'), that element must be shown IN CONTEXT within a full space. Describe: room type, materials, color palette, furniture, plants, lighting mood. Use terms like 'Architectural Digest photography', 'wide-angle interior shot'.",
                "block_details": "The Vibe, DIY Difficulty/Pro-Tip, Budget Range/Alternative",
                "mandatory_category": "Home & Garden",
                "external_sources": "Architectural Digest (architecturaldigest.com), HGTV (hgtv.com), Better Homes & Gardens (bhg.com), The Spruce (thespruce.com), Good Housekeeping (goodhousekeeping.com)"
            },
            "fashion_style": {
                "role": "a fashion editor and trend forecaster for 'Nailosmetic'",
                "article_type": "a high-quality, SEO-optimized fashion and outfit listicle article",
                "featured_image_guide": "Wide (16:9) prompt. MUST show a real woman wearing a complete, stylish outfit in a clean editorial setting. The OUTFIT must be the focal point, fully visible from head to mid-thigh.",
                "block_image_guide": "MANDATORY RULE: Every prompt MUST show a real woman WEARING a complete outfit as the PRIMARY SUBJECT. The outfit must be fully visible. If the heading names a style (e.g., 'casual brunch outfit'), the woman must be wearing that EXACT style. Describe: specific garments (top, bottom, shoes), colors, accessories, fabrics. Use terms like 'editorial street style photography', 'full-body outfit shot', 'clean minimal backdrop'.",
                "block_details": "The Vibe, Styling Tip, Occasion/Season",
                "mandatory_category": "Styles & Fashion",
                "external_sources": "Vogue (vogue.com), Elle (elle.com), InStyle (instyle.com), Harper's Bazaar (harpersbazaar.com), Cosmopolitan (cosmopolitan.com)"
            },
            "gardening": {
                "role": "a garden design and outdoor living editor for 'Nailosmetic'",
                "article_type": "a high-quality, SEO-optimized gardening and outdoor living listicle article",
                "featured_image_guide": "Wide (16:9) prompt. MUST show a beautiful, real garden, patio, or outdoor space. Lush plants, natural sunlight, zen atmosphere. Wide-angle landscape photography. The GARDEN must be the focal subject.",
                "block_image_guide": "MANDATORY RULE: Every prompt MUST show a real garden space, plant arrangement, or outdoor design feature IN CONTEXT within a full landscape — never an isolated plant on a white background. Focus on plants, textures, hardscaping, and natural lighting. Describe: plant species, arrangement style, surrounding landscape, time of day lighting.",
                "block_details": "The Vibe, Growing/DIY Tip, Climate Zone/Alternative",
                "mandatory_category": "Home & Garden",
                "external_sources": "Better Homes & Gardens (bhg.com), The Spruce (thespruce.com), Fine Gardening (finegardening.com), RHS (rhs.org.uk), Gardeners' World (gardenersworld.com)"
            },
        }
        
        config = niche_configs.get(niche, niche_configs["nails"])
        
        system_prompt = f"""You are {config['role']}. 
Your task is to create {config['article_type']} for a WordPress site using Kadence Blocks and RankMath SEO.
{topic_instruction}
Available WordPress Categories: {categories_str}
INTERNAL LINK 1: {link1}
INTERNAL LINK 2: {link2}
INTERNAL LINK 3: {link3}
 
FRAMEWORK REQUIREMENTS:
1. Title: Catchy, SEO-optimized, and hook-driven.
2. Slug: A short, SEO-friendly URL slug (3-5 words maximum).
3. SEO Metadata (RankMath):
   - Focus Keyword: The primary keyword for the article.
   - SEO Title: Optimized title for search results (max 60 chars).
   - Meta Description: Compelling summary for search results (120-160 chars).
4. Featured Image: {config['featured_image_guide']}
5. Introduction: Return as a JSON array of exactly 2 paragraph strings. First paragraph 80+ words. Second paragraph MUST include an internal link to '{link1}'.
6. Key Takeaways: Provide EXACTLY 3 key takeaways (bullet points) that summarize the core value of the article.
7. Comparison Table: Provide a structured comparison table summarizing the 7 listicle items. Create 3 column headers (e.g., "Style/Item Name", "Difficulty/Cost", "Best For") and EXACTLY 7 rows (one for each block).
8. Content Blocks: A list of EXACTLY 7 items (no fewer). Each item must have:
   - Image Prompt: {config['block_image_guide']}
   - Image Alt Text: Highly descriptive.
   - Heading (H2): At least 3 must be questions.
   - Paragraph: Engaging description of at least 150 words per block. MUST use first-hand editorial phrasing (e.g., "In our testing", "Our editors found", "When we tried this...").
     - INTERNAL LINKS: Include '{link2}' and '{link3}' naturally across two different blocks.
     - EXTERNAL LINKS: Include at least 3 external links across the 7 blocks to authoritative {niche} sources (e.g., {config['external_sources']}).
   - Expert Quote: A compelling 1-2 sentence quote providing professional advice or an editorial verdict on this specific block's item.
   - Details: 3 specific points ({config['block_details']}).
9. Conclusion: A strong summary of at least 80 words.
10. FAQ Section: Provide EXACTLY 5 Frequently Asked Questions.
11. Category: You MUST select "{config['mandatory_category']}" as the category. Do NOT use Nail categories for non-nail articles.
12. COMPARISON GRID RULE: If the topic involves comparisons, structure image prompts as comparison grids.

WORD COUNT: The total article body MUST be at least 1,500 words. Do not cut paragraphs short to save tokens.

RETURN ONLY VALID JSON:
{{
  "title": "string",
  "slug": "string",
  "seo": {{
    "focus_keyword": "string",
    "title": "string",
    "description": "string"
  }},
  "category_suggestion": "MANDATORY: string",
  "is_new_category": "MANDATORY: boolean",
  "category_logic": "string",
  "featured_image": {{
    "prompt": "string",
    "alt_text": "string"
  }},
  "introduction": ["string", "string"],
  "key_takeaways": ["string", "string", "string"],
  "comparison_table": {{
    "headers": ["string", "string", "string"],
    "rows": [
      ["string", "string", "string"],
      ["string", "string", "string"],
      ["string", "string", "string"],
      ["string", "string", "string"],
      ["string", "string", "string"],
      ["string", "string", "string"],
      ["string", "string", "string"]
    ]
  }},
  "blocks": [
    {{
      "heading": "string",
      "prompt": "string",
      "alt_text": "string",
      "paragraph": "string (150+ words, first-hand editorial phrasing)",
      "expert_quote": "string (1-2 sentence professional advice/verdict)",
      "details": {{
         "vibe": "string",
         "technique": "string",
         "secondary": "string"
      }}
    }}
  ],
  "faqs": [
    {{
      "question": "string",
      "answer": "string"
    }}
  ],
  "conclusion": "string (80+ words)"
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
        
        # Handle introduction as array of paragraphs
        intro = plan['introduction']
        if isinstance(intro, list):
            intro_paragraphs = intro
        else:
            # Fallback: split on double newline or treat as single
            intro_paragraphs = [p.strip() for p in intro.split('\n\n') if p.strip()] or [intro]
        
        intro_html = ""
        for p in intro_paragraphs:
            # Wrap in <p> tags if not already wrapped
            text = p if p.startswith('<p>') else f'<p>{p}</p>'
            intro_html += f"""<!-- wp:paragraph -->
{text}
<!-- /wp:paragraph -->

"""
        
        html = f"""<!-- wp:kadence/column {{"uniqueID":"{col_id_intro}"}} -->
<div class="wp-block-kadence-column kadence-column{col_id_intro}"><div class="kt-inside-inner-col">
{intro_html}<!-- wp:kadence/tableofcontents {{"uniqueID":"{self._generate_kadence_id()}"}} /-->
"""
        
        # Add Key Takeaways
        takeaways = plan.get('key_takeaways', [])
        if takeaways:
            html += f"""<!-- wp:kadence/infobox {{"uniqueID":"{self._generate_kadence_id()}","containerBackground":"#f8fafc","containerBorderRadius":8,"containerBorderWidth":[1,1,1,1],"containerBorderColor":"#e2e8f0"}} -->
<div class="wp-block-kadence-infobox"><div class="kt-blocks-info-box-wrapper"><div class="kt-blocks-info-box-inner-wrap"><div class="kt-blocks-info-box-text-wrap"><h3 class="kt-blocks-info-box-title">Key Takeaways</h3><div class="kt-blocks-info-box-text"><ul>"""
            for ta in takeaways:
                html += f"<li>{ta}</li>"
            html += """</ul></div></div></div></div></div>
<!-- /wp:kadence/infobox -->
"""
        
        # Add Comparison Table
        comp_table = plan.get('comparison_table', {})
        if comp_table and 'headers' in comp_table and 'rows' in comp_table:
            html += f"""<!-- wp:table {{"className":"is-style-stripes"}} -->
<figure class="wp-block-table is-style-stripes"><table><thead><tr>"""
            for h in comp_table['headers']:
                html += f"<th>{h}</th>"
            html += "</tr></thead><tbody>"
            for row in comp_table['rows']:
                html += "<tr>"
                for cell in row:
                    html += f"<td>{cell}</td>"
                html += "</tr>"
            html += """</tbody></table></figure>
<!-- /wp:table -->
"""
            
        html += """</div></div>
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
<h2 class="kt-adv-heading{h_id} wp-block-kadence-advancedheading">{block.get('heading', 'Section Idea')}</h2>
<!-- /wp:kadence/advancedheading -->

<!-- wp:kadence/image {{"uniqueID":"{img_id}"}} -->
<figure class="wp-block-kadence-image kb-image{img_id}">
    <!-- IMAGE_PLACEHOLDER_{block.get('heading', 'no-heading')} -->
</figure>
<!-- /wp:kadence/image -->

<!-- wp:paragraph -->
<p>{block.get('paragraph', '')}</p>
<!-- /wp:paragraph -->
"""
            
            expert_quote = block.get('expert_quote')
            if expert_quote:
                html += f"""<!-- wp:quote {{"className":"is-style-large"}} -->
<blockquote class="wp-block-quote is-style-large"><p>{expert_quote}</p><cite>Editorial Verdict</cite></blockquote>
<!-- /wp:quote -->
"""
            
            html += f"""<!-- wp:kadence/iconlist {{"uniqueID":"{list_id}"}} -->
<div class="wp-block-kadence-iconlist kt-svg-icon-list-items kt-svg-icon-list-items{list_id} kt-svg-icon-list-columns-1 alignnone"><ul class="kt-svg-icon-list"><!-- wp:kadence/listitem {{"uniqueID":"{self._generate_kadence_id()}"}} -->
<li class="wp-block-kadence-listitem kt-svg-icon-list-item-wrap kt-svg-icon-list-item-{list_id}"><span data-name="USE_PARENT_DEFAULT_ICON" data-stroke="USE_PARENT_DEFAULT_WIDTH" data-class="kt-svg-icon-list-single" class="kadence-dynamic-icon"></span><span class="kt-svg-icon-list-text"><strong>The Vibe:</strong> {block.get('details', {}).get('vibe', '')}</span></li>
<!-- /wp:kadence/listitem -->

<!-- wp:kadence/listitem {{"uniqueID":"{self._generate_kadence_id()}"}} -->
<li class="wp-block-kadence-listitem kt-svg-icon-list-item-wrap kt-svg-icon-list-item-{list_id}"><span data-name="USE_PARENT_DEFAULT_ICON" data-stroke="USE_PARENT_DEFAULT_WIDTH" data-class="kt-svg-icon-list-single" class="kadence-dynamic-icon"></span><span class="kt-svg-icon-list-text"><strong>Technique:</strong> {block.get('details', {}).get('technique', '')}</span></li>
<!-- /wp:kadence/listitem -->

<!-- wp:kadence/listitem {{"uniqueID":"{self._generate_kadence_id()}"}} -->
<li class="wp-block-kadence-listitem kt-svg-icon-list-item-wrap kt-svg-icon-list-item-{list_id}"><span data-name="USE_PARENT_DEFAULT_ICON" data-stroke="USE_PARENT_DEFAULT_WIDTH" data-class="kt-svg-icon-list-single" class="kadence-dynamic-icon"></span><span class="kt-svg-icon-list-text"><strong>Pro-Tip:</strong> {block.get('details', {}).get('secondary', '')}</span></li>
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
<h2 class="wp-block-kadence-advancedheading">Final Thoughts</h2>
<!-- /wp:kadence/advancedheading -->
<!-- wp:paragraph -->
<p>{plan['conclusion']}</p>
<!-- /wp:paragraph -->
</div></div>
<!-- /wp:kadence/column -->
"""

        # ── FAQ Section (AEO / Featured Snippet optimised) ──────────────────
        faqs = plan.get("faqs", [])
        if faqs:
            faq_col_id = self._generate_kadence_id()
            faq_heading_id = self._generate_kadence_id()
            faq_accordion_id = self._generate_kadence_id()
            
            accordion_inner_html = ""
            for faq in faqs:
                faq_item_id = self._generate_kadence_id()
                q = faq.get("question", "").replace('"', '&quot;')
                a = faq.get("answer", "")
                accordion_inner_html += f"""<!-- wp:kadence/pane {{"uniqueID":"{faq_item_id}","title":"{q}"}} -->
<div class="wp-block-kadence-pane kt-accordion-pane kt-accordion-pane-{faq_item_id}">
<div class="kt-accordion-header-wrap">
<button class="kt-accordion-header kt-blocks-accordion-header kt-accordion-header-{faq_item_id}" aria-expanded="false">
<span class="kt-blocks-accordion-title">{faq.get('question', '')}</span>
</button>
</div>
<div class="kt-accordion-panel kt-accordion-panel-{faq_item_id}" role="region">
<div class="kt-accordion-panel-inner">
<!-- wp:paragraph -->
<p>{a}</p>
<!-- /wp:paragraph -->
</div>
</div>
</div>
<!-- /wp:kadence/pane -->

"""
            html += f"""
<!-- wp:kadence/column {{"uniqueID":"{faq_col_id}"}} -->
<div class="wp-block-kadence-column kadence-column{faq_col_id}"><div class="kt-inside-inner-col">
<!-- wp:kadence/advancedheading {{"uniqueID":"{faq_heading_id}"}} -->
<h2 class="wp-block-kadence-advancedheading">Frequently Asked Questions</h2>
<!-- /wp:kadence/advancedheading -->

<!-- wp:kadence/accordion {{"uniqueID":"{faq_accordion_id}"}} -->
<div class="wp-block-kadence-accordion kt-accordion-wrap-{faq_accordion_id}">
<style>
/* Scoped overrides to enforce high contrast and clean visual layout */
.kt-accordion-pane {{
    width: 100% !important;
    margin-bottom: 14px !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    overflow: hidden !important;
    background: #ffffff !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
}}
.kt-accordion-header-wrap {{
    width: 100% !important;
}}
.kt-blocks-accordion-header {{
    width: 100% !important;
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    padding: 16px 20px !important;
    background: #f8fafc !important;
    color: #1e293b !important;
    border: none !important;
    font-weight: 600 !important;
    font-size: 16px !important;
    text-align: left !important;
    cursor: pointer !important;
    transition: background 0.2s ease, color 0.2s ease !important;
}}
.kt-blocks-accordion-header:hover {{
    background: #f1f5f9 !important;
}}
/* WCAG AAA High Contrast Expanded Header */
.kt-blocks-accordion-header.active,
.kt-blocks-accordion-header[aria-expanded="true"] {{
    background: #e2e8f0 !important;
    color: #0f172a !important;
    border-bottom: 1px solid #e2e8f0 !important;
}}
/* Indicator Arrow Icon using CSS */
.kt-blocks-accordion-header::after {{
    content: '▼' !important;
    font-size: 12px !important;
    color: #64748b !important;
    transition: transform 0.2s ease !important;
}}
.kt-blocks-accordion-header.active::after,
.kt-blocks-accordion-header[aria-expanded="true"]::after {{
    transform: rotate(180deg) !important;
    color: #0f172a !important;
}}
/* Content Panel Styling with clean margins */
.kt-accordion-panel {{
    display: none !important; /* Hidden by default */
    padding: 18px 20px !important;
    background: #ffffff !important;
    font-size: 15px !important;
    line-height: 1.6 !important;
    color: #475569 !important;
}}
.kt-accordion-panel.show,
.kt-blocks-accordion-header.active + .kt-accordion-panel {{
    display: block !important;
}}
</style>

{accordion_inner_html}
<script>
document.addEventListener("DOMContentLoaded", function() {{
    // Select all our custom accordion buttons
    const headers = document.querySelectorAll(".kt-blocks-accordion-header");
    headers.forEach(header => {{
        // Enforce smooth dynamic toggling independent of WP script enqueues
        header.addEventListener("click", function(e) {{
            e.preventDefault();
            const pane = this.closest(".kt-accordion-pane");
            const panel = pane.querySelector(".kt-accordion-panel");
            
            const isActive = this.classList.contains("active") || this.getAttribute("aria-expanded") === "true";
            
            if (isActive) {{
                this.classList.remove("active");
                this.setAttribute("aria-expanded", "false");
                panel.classList.remove("show");
                panel.style.display = "none";
            }} else {{
                this.classList.add("active");
                this.setAttribute("aria-expanded", "true");
                panel.classList.add("show");
                panel.style.display = "block";
            }}
        }});
    }});
}});
</script>
</div>
<!-- /wp:kadence/accordion -->

</div></div>
<!-- /wp:kadence/column -->
"""
        return html
