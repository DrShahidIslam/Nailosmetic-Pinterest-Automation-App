"""
pillar_generator.py
===================
Generates long-form (3,500–4,500 word) SEO pillar posts for nailosmetic.com.

Key differences from content_generator.py:
- Section-by-section generation avoids Gemini token limits
- HuggingFace FLUX only for images (prefer_kolors=False, no SiliconFlow)
- Full Table of Contents block
- 10+ internal links to existing cluster posts
- FAQPage schema (5 Q&As) rendered as Kadence accordion
- Related Posts HTML section linking to cluster posts
"""

import json
import re
import time
import random
import uuid
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from google import genai


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Kadence block ID generator
# ─────────────────────────────────────────────────────────────────────────────
def _kid() -> str:
    return f"{random.randint(100, 999)}_{uuid.uuid4().hex[:6]}-{uuid.uuid4().hex[:2]}"


# ─────────────────────────────────────────────────────────────────────────────
# Gemini call wrapper with key-cycling and model fallback
# ─────────────────────────────────────────────────────────────────────────────
def _gemini_call(api_keys: List[str], prompt: str, label: str = "") -> str:
    models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.1-flash-lite-preview"]
    for key in api_keys:
        key_hint = f"...{key[-4:]}"
        client = genai.Client(api_key=key)
        for model in models:
            for attempt in range(3):
                try:
                    response = client.models.generate_content(model=model, contents=prompt)
                    raw = response.text.strip()
                    print(f"   ✅ [{label}] {model} ({key_hint})")
                    return raw
                except Exception as e:
                    err = str(e)
                    if "404" in err or "limit: 0" in err:
                        break  # try next model
                    wait = 15 * (attempt + 1)
                    m = re.search(r"retry in ([\d\.]+)s", err)
                    if m:
                        wait = max(wait, float(m.group(1)) + 2)
                    print(f"   ⚠️  [{label}] {model} attempt {attempt+1} failed — retry in {wait:.0f}s")
                    time.sleep(wait)
    raise Exception(f"Gemini API permanently failed for [{label}]")


def _parse_json(raw: str) -> Dict:
    cleaned = re.sub(r"```json\s*|\s*```", "", raw).strip()
    # Try to extract JSON object if there's surrounding text
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return json.loads(cleaned)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Generate Outline
# ─────────────────────────────────────────────────────────────────────────────
def generate_pillar_outline(api_keys: List[str], config: Dict) -> Dict:
    """
    Generate a structured outline for the pillar post.
    Returns: title, slug, seo, featured_image, sections[], conclusion, faqs[]
    """
    cluster_urls = "\n".join([f"  - {u}" for u in config.get("cluster_urls", [])])
    h2_outline = "\n".join([f"  {i+1}. {h}" for i, h in enumerate(config["h2_outline"])])

    prompt = f"""
You are an elite SEO content architect for 'Nailosmetic', a beauty, home, and style blog.

Create a detailed OUTLINE for a pillar post with these specifications:

PILLAR TITLE: {config['title']}
PRIMARY KEYWORD: {config['keyword']}
CATEGORY: {config['category']}
TARGET WORD COUNT: {config['word_count']}+ words

H2 STRUCTURE (MUST follow this exactly — you may only add H3 sub-sections):
{h2_outline}

CLUSTER POSTS TO LINK INTERNALLY (use these URLs naturally in the outline goals):
{cluster_urls}

REQUIREMENTS:
- At least 4 of the H2 headings must be phrased as a question (e.g., "How Do You...?", "What Is...?", "Which...?")
- Each section must have a clear content goal of 300-400 words
- Designate 3 sections as having an image (has_image: true)
- The introduction must be 120+ words and link to nailosmetic.com homepage
- Generate EXACTLY 5 FAQ Q&As relevant to the primary keyword
- External links: specify 2 sections where an external authority link should appear (Allure, Byrdie, Vogue, Healthline, InStyle, Good Housekeeping)

RETURN ONLY VALID JSON:
{{
  "title": "{config['title']}",
  "slug": "{config['slug']}",
  "seo": {{
    "focus_keyword": "{config['keyword']}",
    "title": "string (max 60 chars, include keyword)",
    "description": "string (120-160 chars, compelling, include keyword)"
  }},
  "introduction": "string (120+ words, hooks the reader, links to https://nailosmetic.com/ with natural anchor text)",
  "featured_image": {{
    "prompt": "string (detailed 16:9 image generation prompt for the pillar topic)",
    "alt_text": "string (descriptive, 1-2 sentences)"
  }},
  "sections": [
    {{
      "heading": "string (question-format for at least 4 sections)",
      "goal": "string (what to cover, 300-400 words, mention which cluster URL to link if any)",
      "has_image": false,
      "has_external_link": false,
      "preferred_format": "paragraph | list | table | faq",
      "image_prompt": "string or null",
      "image_alt": "string or null"
    }}
  ],
  "faqs": [
    {{
      "question": "string (phrased exactly as a user Google search query)",
      "answer": "string (2-4 direct, factual sentences)"
    }}
  ],
  "conclusion": "string (100+ words, reinforces keyword, encourages engagement)"
}}
"""
    raw = _gemini_call(api_keys, prompt, label="outline")
    return _parse_json(raw)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Generate each section body
# ─────────────────────────────────────────────────────────────────────────────
def generate_section_body(
    api_keys: List[str],
    pillar_title: str,
    keyword: str,
    section: Dict,
    previous_headings: List[str],
    cluster_urls: List[str],
    section_index: int
) -> str:
    """Generate 300-400 word body text for one section."""
    context = ", ".join(previous_headings) if previous_headings else "None yet"

    # Pick 1-2 cluster URLs to embed in this section (only if they are available)
    link_targets = cluster_urls[:2] if cluster_urls else []
    link_instruction = ""
    if link_targets and section_index % 2 == 0:  # alternate sections get links
        links_str = " and ".join([f'<a href="{u}">{Path(u.rstrip("/")).name.replace("-", " ").title()}</a>' for u in link_targets])
        link_instruction = f"INTERNAL LINKS: Naturally embed HTML anchor links to: {links_str} within the text."

    ext_link_instruction = ""
    if section.get("has_external_link"):
        ext_link_instruction = "EXTERNAL LINK: Include exactly one HTML anchor link to an authoritative beauty/lifestyle source (Allure.com, Byrdie.com, InStyle.com, Vogue.com, or Healthline.com). Link to a relevant, real URL pattern like 'https://www.allure.com/story/...' with natural anchor text."

    prompt = f"""
You are a premium human-voice writer for 'Nailosmetic'. Write ONE section of a long-form pillar post.

ARTICLE TITLE: {pillar_title}
PRIMARY KEYWORD: {keyword}
SECTION HEADING: {section['heading']}
SECTION GOAL: {section['goal']}
PREFERRED FORMAT: {section['preferred_format']}
SECTIONS ALREADY WRITTEN: {context}

WORD COUNT: Write 320-420 words for this section. Be verbose, specific, and genuinely helpful.

{link_instruction}
{ext_link_instruction}

WRITING RULES:
1. Voice: Conversational yet premium — like a knowledgeable friend, not a textbook.
2. NO AI-ISMS: No "delve into", "tapestry of", "unlock", "game-changer", "curated".
3. NO EM-DASHES: Never use — or –. Use commas, colons, or new sentences instead.
4. FORMAT: If format is "list", use HTML <ul><li> tags. If "table", use HTML <table> with <thead>.
5. KEYWORD DENSITY: Naturally include the primary keyword "{keyword}" 1-2 times in this section.
6. DO NOT repeat the section heading in the text.

RETURN ONLY THE RAW HTML TEXT (no JSON wrapper, no markdown fences, just the section body HTML):
"""
    return _gemini_call(api_keys, prompt, label=f"section:{section['heading'][:30]}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Build HTML for the full pillar
# ─────────────────────────────────────────────────────────────────────────────
def build_pillar_html(outline: Dict, section_bodies: List[str], media_map: Dict) -> str:
    """
    Assemble complete Kadence Blocks HTML for the pillar post.
    media_map: {"featured": media_id, "section_N": {"id": media_id, "url": url, "alt": alt}}
    """
    html = ""

    # ── Table of Contents ─────────────────────────────────────────────────
    toc_id = _kid()
    html += f"""<!-- wp:kadence/tableofcontents {{"uniqueID":"{toc_id}"}} /-->\n\n"""

    # ── Introduction ──────────────────────────────────────────────────────
    intro_col = _kid()
    html += f"""<!-- wp:kadence/column {{"uniqueID":"{intro_col}"}} -->
<div class="wp-block-kadence-column kadence-column{intro_col}"><div class="kt-inside-inner-col">
<!-- wp:paragraph -->
<p>{outline['introduction']}</p>
<!-- /wp:paragraph -->
</div></div>
<!-- /wp:kadence/column -->

"""

    # ── Sections ──────────────────────────────────────────────────────────
    img_section_counter = 0
    for i, (section, body) in enumerate(zip(outline["sections"], section_bodies)):
        sec_col = _kid()
        h_id = _kid()

        html += f"""<!-- wp:kadence/column {{"uniqueID":"{sec_col}"}} -->
<div class="wp-block-kadence-column kadence-column{sec_col}"><div class="kt-inside-inner-col">

<!-- wp:kadence/advancedheading {{"uniqueID":"{h_id}","level":2}} -->
<h2 class="kt-adv-heading{h_id} wp-block-kadence-advancedheading">{section['heading']}</h2>
<!-- /wp:kadence/advancedheading -->

"""
        # Image for this section if applicable
        if section.get("has_image"):
            img_key = f"section_{img_section_counter}"
            img_section_counter += 1
            if img_key in media_map:
                img_data = media_map[img_key]
                img_id = _kid()
                html += f"""<!-- wp:kadence/image {{"uniqueID":"{img_id}"}} -->
<figure class="wp-block-kadence-image kb-image{img_id}">
<img src="{img_data['url']}" alt="{img_data['alt']}" class="kb-img wp-image-{img_data['id']}"/>
</figure>
<!-- /wp:kadence/image -->

"""

        # Section body — wrap in wp:paragraph or wp:html depending on content
        body_stripped = body.strip()
        if any(tag in body_stripped for tag in ["<ul", "<ol", "<table", "<div"]):
            html += f"""<!-- wp:html -->
{body_stripped}
<!-- /wp:html -->

"""
        else:
            # Split on double newlines for multiple paragraphs
            paragraphs = [p.strip() for p in body_stripped.split("\n\n") if p.strip()]
            for para in paragraphs:
                p_text = para if para.startswith("<p>") else f"<p>{para}</p>"
                html += f"""<!-- wp:paragraph -->
{p_text}
<!-- /wp:paragraph -->

"""

        html += f"""</div></div>
<!-- /wp:kadence/column -->

<!-- wp:spacer {{"height":"30px"}} -->
<div style="height:30px" aria-hidden="true" class="wp-block-spacer"></div>
<!-- /wp:spacer -->

"""

    # ── Conclusion ────────────────────────────────────────────────────────
    concl_col = _kid()
    concl_h = _kid()
    html += f"""<!-- wp:kadence/column {{"uniqueID":"{concl_col}"}} -->
<div class="wp-block-kadence-column kadence-column{concl_col}"><div class="kt-inside-inner-col">
<!-- wp:kadence/advancedheading {{"uniqueID":"{concl_h}","level":2}} -->
<h2 class="wp-block-kadence-advancedheading">Final Thoughts</h2>
<!-- /wp:kadence/advancedheading -->
<!-- wp:paragraph -->
<p>{outline['conclusion']}</p>
<!-- /wp:paragraph -->
</div></div>
<!-- /wp:kadence/column -->

"""

    # ── Related Posts ─────────────────────────────────────────────────────
    related_col = _kid()
    related_h = _kid()
    cluster_urls = outline.get("_cluster_urls", [])
    if cluster_urls:
        related_items = ""
        for url in cluster_urls[:6]:  # show up to 6 related posts
            label = Path(url.rstrip("/")).name.replace("-", " ").title()
            related_items += f'<li><a href="{url}">{label}</a></li>\n'

        html += f"""<!-- wp:kadence/column {{"uniqueID":"{related_col}"}} -->
<div class="wp-block-kadence-column kadence-column{related_col}"><div class="kt-inside-inner-col">
<!-- wp:kadence/advancedheading {{"uniqueID":"{related_h}","level":2}} -->
<h2 class="wp-block-kadence-advancedheading">Related Posts You'll Love</h2>
<!-- /wp:kadence/advancedheading -->
<!-- wp:html -->
<ul class="related-posts-list">
{related_items}</ul>
<!-- /wp:html -->
</div></div>
<!-- /wp:kadence/column -->

"""

    # ── FAQ Section ───────────────────────────────────────────────────────
    faqs = outline.get("faqs", [])
    if faqs:
        faq_col = _kid()
        faq_h = _kid()
        html += f"""<!-- wp:kadence/column {{"uniqueID":"{faq_col}"}} -->
<div class="wp-block-kadence-column kadence-column{faq_col}"><div class="kt-inside-inner-col">
<!-- wp:kadence/advancedheading {{"uniqueID":"{faq_h}","level":2}} -->
<h2 class="wp-block-kadence-advancedheading">Frequently Asked Questions</h2>
<!-- /wp:kadence/advancedheading -->
"""
        for faq in faqs:
            pane_id = _kid()
            q = faq.get("question", "").replace('"', "&quot;")
            a = faq.get("answer", "")
            html += f"""<!-- wp:kadence/pane {{"uniqueID":"{pane_id}","title":"{q}"}} -->
<div class="wp-block-kadence-pane kt-accordion-pane kt-accordion-pane-{pane_id}">
<div class="kt-accordion-header-wrap">
<button class="kt-accordion-header kt-blocks-accordion-header kt-accordion-header-{pane_id}" aria-expanded="false">
<span class="kt-blocks-accordion-title">{faq.get('question', '')}</span>
</button>
</div>
<div class="kt-accordion-panel kt-accordion-panel-{pane_id}" role="region">
<div class="kt-accordion-panel-inner">
<!-- wp:paragraph -->
<p>{a}</p>
<!-- /wp:paragraph -->
</div>
</div>
</div>
<!-- /wp:kadence/pane -->

"""
        html += """</div></div>
<!-- /wp:kadence/column -->
"""

    return html
