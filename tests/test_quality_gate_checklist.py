"""
test_quality_gate_checklist.py — Unit tests for the new SEO Content Checklist rules in quality_gate.py.

Tests:
  - Failure 1: Missing FAQ section
  - Failure 2: Focus keyword not in first 100 words of intro
  - Failure 3: Focus keyword not in any H2 heading
  - Failure 4: Keyword stuffing (> 7 occurrences per 1000 words)
  - Warning 5: Missing outbound external links
  - Warning 6: Focus keyword absent from conclusion
  - Warning 7: Missing Table of Contents (jump links)
  - Passing Baseline: Fully compliant plan and HTML
"""

import io
import sys
from pathlib import Path

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, io.UnsupportedOperation):
        pass

# Add project root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "wordpress_automation"))

from wordpress_automation.quality_gate import run_quality_gate


def make_valid_plan_and_html(focus_kw="fall nails"):
    intro_text = (
        f"Discover the trendiest {focus_kw} of 2026. This comprehensive guide breaks down everything "
        "you need to achieve effortless salon-quality manicures right at home. " +
        "Explore rich colors, earthy textures, and modern minimalist accents that redefine your seasonal style. " * 6
    )

    toc_html = (
        "<nav class='toc'><ul>"
        "<li><a href='#fall-nails-guide'>Fall Nails Guide</a></li>"
        "<li><a href='#nail-care-tips'>Nail Care Tips</a></li>"
        "</ul></nav>"
    )

    sections = [
        {
            "heading": f"Why {focus_kw.title()} Are Dominating Seasonal Trends",
            "content": (
                "Deep berry, burgundy, and warm chocolate tones define the modern aesthetic this season. " * 18 +
                "For medical nail health standards, consult guidelines from <a href='https://www.aad.org/public/everyday-care/nail-care-secrets'>AAD.org</a>. "
            ),
            "preferred_format": "paragraph",
            "image_prompt": "A macro photograph of warm brown chrome fall nails with glossy finish."
        },
        {
            "heading": "Essential Techniques for Autumn Manicures",
            "content": "Proper prep and gentle cuticle care ensure long-lasting results without peeling. " * 20,
            "preferred_format": "list",
            "image_prompt": "A close up photo of manicured almond-shaped nails."
        },
        {
            "heading": "Selecting the Right Color Palette",
            "content": "Warm terracotta, olive green, and spiced caramel complement any wardrobe palette. " * 20,
            "preferred_format": "table",
            "image_prompt": "A flat lay palette of aesthetic autumnal nail polish bottles."
        },
        {
            "heading": "At-Home Maintenance Tips",
            "content": "Daily jojoba oil application keeps cuticles hydrated and prevents breakage. " * 20,
            "preferred_format": "paragraph"
        },
        {
            "heading": "Styling Accessories and Rings",
            "content": "Chunky gold jewelry and layered rings highlight minimalist polish lines perfectly. " * 20,
            "preferred_format": "paragraph"
        },
        {
            "heading": "Frequently Asked Questions",
            "content": (
                "How long do gel manicures last? Typically two to three weeks with proper aftercare. " * 10 +
                "What is the best way to remove polish safely? Use acetone with cotton pads and foil wraps. " * 10
            ),
            "preferred_format": "faq"
        }
    ]

    conclusion_text = (
        f"Embracing {focus_kw} allows you to experiment with cozy, sophisticated tones. "
        "Select your favorite seasonal palette and enjoy a flawless aesthetic all season long. " * 4
    )

    plan = {
        "title": f"15 Chic {focus_kw.title()} for Autumn 2026",
        "introduction": intro_text,
        "sections": sections,
        "conclusion": conclusion_text,
        "seo": {
            "title": f"15 Chic {focus_kw.title()} for Autumn 2026",
            "description": f"Discover chic {focus_kw} with expert guides, aesthetic photography, curated palettes, and pro nail care tips for autumn.",
            "focus_keyword": focus_kw
        }
    }

    html = (
        f"<p>{intro_text}</p>\n{toc_html}\n" +
        "".join([
            f"<h2>{s['heading']}</h2>\n" +
            (f"<!-- IMAGE_PLACEHOLDER_{s['heading']} -->\n" if s.get("image_prompt") else "") +
            f"<p>{s['content']}</p>\n"
            for s in sections
        ]) +
        f"<p>{conclusion_text}</p>"
    )

    return plan, html


def test_checklist():
    print("=" * 80)
    print("🧪 RUNNING SEO CONTENT CHECKLIST QUALITY GATE TESTS")
    print("=" * 80 + "\n")

    # 1. Baseline Compliant Plan
    plan, html = make_valid_plan_and_html()
    passed, fails, warns = run_quality_gate(plan, html)
    print(f"Test 1 [Baseline Compliant Plan]: Passed={passed}")
    print(f"   Failures ({len(fails)}): {fails}")
    print(f"   Warnings ({len(warns)}): {warns}")
    assert passed, f"Expected compliant plan to pass, got failures: {fails}"
    assert len(warns) == 0, f"Expected 0 warnings, got: {warns}"
    print("   ✅ PASS: Valid plan passed with zero failures and zero warnings.\n")

    # 2. Failure Check 1: Missing FAQ Section
    plan_no_faq, html_no_faq = make_valid_plan_and_html()
    for s in plan_no_faq["sections"]:
        if s.get("preferred_format") == "faq":
            s["preferred_format"] = "paragraph"
    passed, fails, warns = run_quality_gate(plan_no_faq, html_no_faq)
    print(f"Test 2 [Missing FAQ Section]: Passed={passed}")
    print(f"   Failures: {fails}")
    assert not passed, "Expected plan without FAQ to fail"
    assert any("Article has no FAQ section" in f for f in fails), "Expected FAQ failure message"
    print("   ✅ PASS: Missing FAQ section correctly blocked publishing.\n")

    # 3. Failure Check 2: Focus Keyword Missing in Intro (First 100 words)
    plan_no_intro_kw, html_no_intro_kw = make_valid_plan_and_html(focus_kw="fall nails")
    # Replace keyword in intro with generic words
    plan_no_intro_kw["introduction"] = (
        "Discover the trendiest seasonal aesthetics of 2026. This comprehensive guide breaks down everything "
        "you need to achieve effortless salon-quality manicures right at home. " * 3
    )
    passed, fails, warns = run_quality_gate(plan_no_intro_kw, html_no_intro_kw)
    print(f"Test 3 [Keyword Missing in Intro]: Passed={passed}")
    print(f"   Failures: {fails}")
    assert not passed, "Expected missing intro keyword to fail"
    assert any("not found in the first 100 words of the introduction" in f for f in fails)
    print("   ✅ PASS: Missing focus keyword in intro correctly blocked publishing.\n")

    # 4. Failure Check 3: Focus Keyword Missing in Section Headings (H2)
    plan_no_h2_kw, html_no_h2_kw = make_valid_plan_and_html(focus_kw="fall nails")
    for s in plan_no_h2_kw["sections"]:
        s["heading"] = s["heading"].replace("Fall Nails", "Seasonal Polish").replace("fall nails", "seasonal polish")
    passed, fails, warns = run_quality_gate(plan_no_h2_kw, html_no_h2_kw)
    print(f"Test 4 [Keyword Missing in All H2s]: Passed={passed}")
    print(f"   Failures: {fails}")
    assert not passed, "Expected missing H2 keyword to fail"
    assert any("does not appear in any section heading" in f for f in fails)
    print("   ✅ PASS: Missing focus keyword in H2s correctly blocked publishing.\n")

    # 5. Failure Check 4: Keyword Stuffing (> 7 per 1000 words)
    plan_stuffed, html_stuffed = make_valid_plan_and_html(focus_kw="fall nails")
    # Add repeated keyword to inflate density
    # Total article words is ~1300. Adding 20 occurrences gives > 15 per 1000 words
    stuffed_addition = " fall nails " * 20
    html_stuffed += f"<p>{stuffed_addition}</p>"
    passed, fails, warns = run_quality_gate(plan_stuffed, html_stuffed)
    print(f"Test 5 [Keyword Stuffing > 7 per 1000 words]: Passed={passed}")
    print(f"   Failures: {fails}")
    assert not passed, "Expected keyword-stuffed plan to fail"
    assert any("times per 1000 words (maximum 7)" in f for f in fails)
    print("   ✅ PASS: Keyword stuffing correctly detected and blocked.\n")

    # 6. Warnings Check: Outbound Links, Conclusion Keyword, Table of Contents
    plan_warns, html_warns = make_valid_plan_and_html(focus_kw="fall nails")
    # Strip outbound link from HTML
    html_warns = html_warns.replace("https://www.aad.org/public/everyday-care/nail-care-secrets", "https://nailosmetic.com/care")
    # Strip jump link from TOC
    html_warns = html_warns.replace("<a href='#fall-nails-guide'>", "<span>").replace("<a href='#nail-care-tips'>", "<span>")
    # Remove keyword from conclusion (while keeping length >= 30 words)
    plan_warns["conclusion"] = (
        "Embracing cozy seasonal styles allows you to experiment with rich, sophisticated tones and creative modern textures. "
        "Enjoy your brand new aesthetic manicure with loved ones and friends all season long and beyond!"
    )
    passed, fails, warns = run_quality_gate(plan_warns, html_warns)
    print(f"Test 6 [Warnings for Missing Outbound, TOC, and Conclusion Keyword]: Passed={passed}")
    print(f"   Failures: {fails}")
    print(f"   Warnings ({len(warns)}): {warns}")
    assert passed, f"Warnings should not block publishing: {fails}"
    assert any("No outbound external links" in w for w in warns)
    assert any("Focus keyword is absent from conclusion" in w for w in warns)
    assert any("No Table of Contents (jump links) detected" in w for w in warns)
    print("   ✅ PASS: All 3 warnings logged correctly without blocking publication.\n")

    print("=" * 80)
    print("🎉 ALL 6 UNIT TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 80)


if __name__ == "__main__":
    test_checklist()
