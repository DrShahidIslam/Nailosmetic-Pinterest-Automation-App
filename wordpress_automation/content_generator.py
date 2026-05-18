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
        
        # Niche-specific high-authority pillar fallbacks to guarantee 3 unique links
        niche_pillars = {
            "nails": [
                "nail-art-designs-ultimate-guide",
                "chrome-nails-complete-guide",
                "spring-nail-designs-inspo",
                "pearl-nail-designs-trends"
            ],
            "hair_beauty": [
                "hairstyles-for-women-ultimate-guide",
                "goddess-braids-ideas",
                "hair-highlights-trends",
                "wolf-cut-haircut-styling"
            ],
            "home_garden": [
                "home-decor-ideas-ultimate-guide",
                "bedscaping-ideas-home-decor",
                "color-drenching-bedroom-tips",
                "june-calendar-home-transformation"
            ],
            "fashion_style": [
                "spring-outfits-women-guide",
                "casual-brunch-outfits-aesthetic",
                "old-money-aesthetic-outfits",
                "festival-outfits-ideas-inspo"
            ]
        }
        
        pillars = niche_pillars.get(niche, niche_pillars["nails"])
        
        # Build available links using previous_slugs, deduplicating them
        available_links = list(dict.fromkeys(previous_slugs)) if previous_slugs else []
        
        # Pick unique links from available links
        internal_links = []
        for s in available_links:
            if s not in internal_links:
                internal_links.append(s)
                
        # Fill remaining slots using niche-specific authority pillars
        for p in pillars:
            if len(internal_links) >= 3:
                break
            if p not in internal_links:
                internal_links.append(p)
                
        # If still less than 3 (extremely unlikely), fall back to universal nails pillars
        for p in niche_pillars["nails"]:
            if len(internal_links) >= 3:
                break
            if p not in internal_links:
                internal_links.append(p)
                
        # Slice to exactly 3 unique slugs
        internal_links = internal_links[:3]
        
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
1. Title: Catchy, SEO-optimized, and hook-driven (e.g., '3 Secret Rules for Minimalist Nails', '7 Viral Hacks for...'). It should match the curiosity-gap style of Pinterest pins.
2. Slug: A short, SEO-friendly URL slug (3-5 words maximum, lowercase-with-dashes). It MUST include the primary focus keyword.
3. SEO Metadata (RankMath):
   - Focus Keyword: The primary keyword for the article.
   - SEO Title: Optimized title for search results (max 60 chars).
   - Meta Description: Compelling summary for search results (120-160 chars).
4. Featured Image: {config['featured_image_guide']}
5. Introduction: Return as a JSON array of exactly 2 paragraph strings. The first paragraph sets the scene and must be at least 80 words. The second paragraph MUST include exactly one internal link to '{link1}' using an HTML anchor tag with natural anchor text.
6. Content Blocks: A list of EXACTLY 7 items (no fewer). Each item must have:
   - Image Prompt: {config['block_image_guide']}
   - Image Alt Text: Descriptive.
   - Heading (H2): At least 3 of the 7 headings MUST be phrased as a question. The remaining headings can be trendy name-style.
   - Paragraph: Engaging description of at least 100 words per block. 
     - INTERNAL LINKS: Include 'INTERNAL LINK 2' ({link2}) and 'INTERNAL LINK 3' ({link3}) naturally across two different blocks (one link per block).
     - EXTERNAL LINKS: Include at least 3 external links across the full set of 7 blocks — link STRICTLY to authoritative {niche}-specific sources (e.g., {config['external_sources']}) using HTML anchor tags. Do NOT link to off-topic sources (e.g. no hair links in gardening or nails in decor).
     - Spread all links naturally so they don't look forced.
   - Details: 3 specific points ({config['block_details']}).
7. Conclusion: A strong summary of at least 80 words, encouraging interaction and reinforcing the focus keyword.
8. FAQ Section: Provide EXACTLY 5 Frequently Asked Questions relevant to the focus keyword and article topic. Each FAQ must have:
   - A question phrased exactly as a real user would type it into Google or ask an AI assistant.
   - A clear, direct answer of 2-4 sentences that fully answers the question without fluff.
   This section is critical for Google featured snippets and AI answer engines (ChatGPT, Perplexity, Gemini).
9. Category: You MUST select "{config['mandatory_category']}" as the category. 
   - CATEGORY RESTRICTION: The categories "Aesthetic & Art", "Chrome & Glazed", "Minimalist & Clean Girl", and "Seasonal Trends" are STRICTLY for NAIL content only. Do NOT use them for Hair, Fashion, or Home content under any circumstances.
   - If this is a NAIL article, you may use the specialized sub-categories, but "Styles & Fashion" or "Hair & Beauty" are strictly forbidden for nails.
10. Alt Text: For every "alt_text" field, provide a highly descriptive 1-2 sentence description of the visual elements (colors, textures, subjects, lighting). Avoid generic SEO padding; focus on helping a visually impaired user see the image in their mind.

WORD COUNT: The total article body (introduction + all 7 block paragraphs + conclusion) MUST be at least 1,200 words. Do not cut paragraphs short to save tokens — length and depth are required for SEO ranking.

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
  "category_logic": "Briefly explain why this category matches the niche and is not a nail-specific category (for non-nail articles).",
  "featured_image": {{
    "prompt": "string",
    "alt_text": "string"
  }},
  "introduction": ["string (first paragraph, 80+ words)", "string (second paragraph with internal link)"],
  "blocks": [
    {{
      "heading": "string (at least 3 of 7 must be question-format)",
      "prompt": "string",
      "alt_text": "string",
      "paragraph": "string (100+ words, include external authority links in 2 of the 7 blocks)",
      "details": {{
         "vibe": "string",
         "technique": "string",
         "secondary": "string"
      }}
    }}
  ],
  "faqs": [
    {{
      "question": "string (phrased as a real user search query)",
      "answer": "string (2-4 clear sentences that fully answer the question)"
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

<!-- wp:kadence/iconlist {{"uniqueID":"{list_id}"}} -->
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
