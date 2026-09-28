"""
quality_gate.py — Publish QA gate for the Nailosmetic WordPress pipeline.

Runs BEFORE any image generation / publishing. Fail-closed: if the generated
article does not meet minimum quality bars, main.py saves it as a DRAFT for
manual review instead of publishing thin or skeleton content live.

Checks (failures — block publishing):
  1. Minimum section count (>= MIN_SECTIONS)
  2. Introduction / conclusion present and non-trivial
  3. Every section meets MIN_SECTION_WORDS (catches empty skeleton sections
     like the "The Vibe:/Technique:/Pro-Tip:" template bullets with no body)
  4. Total article word count >= MIN_TOTAL_WORDS
  5. Image placeholder count matches sections flagged for images
     (catches prompt/HTML drift)
  6. No lorem ipsum / TODO / [insert ...] / "coming soon" filler

Checks (warnings — logged, do not block):
  - SEO title length, meta description length

Usage in main.py:
    from quality_gate import run_quality_gate
    passed, failures, warnings = run_quality_gate(plan, html_content)
"""

import re
from html import unescape

MIN_SECTIONS = 6
MIN_SECTION_WORDS = 80
MIN_TOTAL_WORDS = 1200
MIN_INTRO_WORDS = 40
MIN_CONCLUSION_WORDS = 30

# Filler / placeholder signals (case-insensitive). NOTE: the
# "<!-- IMAGE_PLACEHOLDER_" pattern is checked separately by count,
# because placeholders are EXPECTED before image generation runs.
FILLER_PATTERNS = [
    r"lorem ipsum",
    r"\bTODO\b",
    r"\[insert[^\]]*\]",
    r"coming soon",
    r"write .* here",
]

# Template labels that shipped empty in past skeleton posts — flagged
# explicitly so the failure reason is actionable.
SKELETON_LABELS = ["the vibe:", "technique:", "pro-tip:", "pro tip:"]


def _strip_html(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _words(text: str) -> int:
    stripped = _strip_html(text)
    return len(stripped.split()) if stripped else 0


def run_quality_gate(plan: dict, html_content: str):
    """
    Returns (passed: bool, failures: list[str], warnings: list[str]).
    """
    failures, warnings = [], []
    sections = plan.get("sections", []) or []

    # 1. Section count
    if len(sections) < MIN_SECTIONS:
        failures.append(
            f"Only {len(sections)} sections generated (minimum {MIN_SECTIONS})."
        )

    # 2. Intro / conclusion
    intro_words = _words(plan.get("introduction", ""))
    if intro_words < MIN_INTRO_WORDS:
        failures.append(
            f"Introduction is {intro_words} words (minimum {MIN_INTRO_WORDS})."
        )
    conclusion_words = _words(plan.get("conclusion", ""))
    if conclusion_words < MIN_CONCLUSION_WORDS:
        failures.append(
            f"Conclusion is {conclusion_words} words (minimum {MIN_CONCLUSION_WORDS})."
        )

    # 3 + 4. Per-section depth and total words
    total_words = intro_words + conclusion_words
    for i, sec in enumerate(sections):
        heading = sec.get("heading", f"section {i + 1}")
        body_words = _words(sec.get("content", ""))
        total_words += body_words
        if body_words < MIN_SECTION_WORDS:
            failures.append(
                f"Section '{heading[:50]}' has only {body_words} words "
                f"(minimum {MIN_SECTION_WORDS}) — possible skeleton/template content."
            )
        lowered = _strip_html(sec.get("content", "")).lower()
        if any(lbl in lowered for lbl in SKELETON_LABELS) and body_words < MIN_SECTION_WORDS * 2:
            failures.append(
                f"Section '{heading[:50]}' contains skeleton template labels "
                f"(The Vibe:/Technique:/Pro-Tip:) with thin body text."
            )

    if total_words < MIN_TOTAL_WORDS:
        failures.append(
            f"Total article is {total_words} words (minimum {MIN_TOTAL_WORDS})."
        )

    # 5. Image placeholder parity (placeholders exist pre-image-generation)
    expected_placeholders = sum(
        1 for s in sections
        if s.get("image_prompt") and s.get("image_prompt") != "NONE"
    )
    actual_placeholders = html_content.count("<!-- IMAGE_PLACEHOLDER_")
    if actual_placeholders != expected_placeholders:
        failures.append(
            f"Image placeholder mismatch: {actual_placeholders} placeholders in HTML "
            f"but {expected_placeholders} sections flagged for images."
        )

    # 6. Filler text scan
    html_lower = _strip_html(html_content).lower()
    for pat in FILLER_PATTERNS:
        if re.search(pat, html_lower, re.I):
            failures.append(f"Filler/placeholder text detected matching pattern: {pat}")

    # Warnings: SEO meta lengths (logged, never block)
    seo = plan.get("seo", {}) or {}
    seo_title = seo.get("title", "")
    if not seo_title:
        warnings.append("SEO title is empty — RankMath will fall back to post title.")
    elif len(seo_title) > 60:
        warnings.append(f"SEO title is {len(seo_title)} chars (>60, may truncate in SERPs).")
    seo_desc = seo.get("description", "")
    if not seo_desc:
        warnings.append("Meta description is empty.")
    elif not (120 <= len(seo_desc) <= 160):
        warnings.append(
            f"Meta description is {len(seo_desc)} chars (ideal 120-160)."
        )
    if not seo.get("focus_keyword"):
        warnings.append("Focus keyword is empty.")

    return (len(failures) == 0, failures, warnings)
