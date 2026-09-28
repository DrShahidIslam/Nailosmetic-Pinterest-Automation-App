"""
topic_gate.py — Pre-generation duplicate and cannibalization gate for Nailosmetic.

Runs BEFORE Gemini generates any new blog post in main.py.
Prevents publishing duplicate topics (e.g. 15 variations of "september nails")
that split keyword equity and cause Google to demote posts into
"crawled - currently not indexed".

Logic:
  1. Clean candidate topic: lowercase, remove filler words (viral, stunning, chic,
     gorgeous, amazing, best, top, ideas, designs, trends), strip numbers and years.
     "15 Chic September Nail Ideas" -> "september nail"
  2. Compare against cleaned titles & slugs of all existing published posts.
  3. Sub-niche Modifier Rule:
     If a candidate contains a specific distinguishing modifier (e.g., "floral",
     "french", "chrome", "almond", "skull", "braid"), it is NOT rejected under
     the 45-day recency rule unless the existing post ALSO shares that modifier.
  4. Survivor Map Routing:
     If an existing match is a deprecated cannibalized URL in shared/survivor_map.json,
     it automatically reroutes the refresh action to the canonical pillar post.
  5. Word-overlap matching:
     - If >= 80% overlap with an older post (>45 days): REJECT and queue canonical pillar
       in refresh_queue.json -> returns "refresh:<pillar_post_id>".
     - Recency rule: If matched post was published in the last 45 days, REJECT
       even if overlap is below 80% (>= 50% overlap or shared core intent) -> returns "duplicate".
     - Otherwise -> returns "ok".
  6. Log all rejections to rejected_topics.log.

Usage:
    from topic_gate import check_topic
    result = check_topic("15 Chic September Nail Ideas")
    # returns: "ok", "duplicate", or "refresh:<post_id>"

CLI Testing:
    python wordpress_automation/topic_gate.py --test
    python wordpress_automation/topic_gate.py --check "15 Chic September Nail Ideas"
"""

import argparse
import csv
from datetime import datetime
from html import unescape
import io
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Dict, List, Optional, Set, Tuple
import requests

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, io.UnsupportedOperation):
        pass

# Filler / fluff words that must be stripped to isolate core topic intent
FILLER_WORDS = {
    "viral", "stunning", "chic", "gorgeous", "amazing", "best", "top",
    "ideas", "idea", "designs", "design", "trends", "trend", "trendy",
    "look", "looks", "style", "styles", "stylish", "simple", "cute",
    "easy", "inspo", "inspiration", "aesthetic", "tutorial", "tutorials",
    "hacks", "hack", "tips", "tip", "secrets", "secret", "ways", "way",
    "guide", "guides", "ultimate", "must", "have", "need", "for", "in",
    "to", "and", "the", "a", "an", "of", "with", "by", "on", "at",
    "your", "over", "everyday", "instant", "instantly", "picturesque",
    "moments", "pro", "fresh", "dazzling", "perfect", "season", "bloom",
    "score", "big", "budget", "friendly", "diy", "unveil", "unlock",
    "effortless", "revitalize", "essential", "expensive", "game",
    "changing", "that", "you", "will", "this", "from", "into"
}

# Distinctive sub-niche modifiers (shapes, patterns, techniques, specific elements)
# If a candidate topic contains one of these, it represents a differentiated search intent
# and will NOT be falsely rejected under the recency rule unless the existing post ALSO
# shares this specific distinguishing modifier.
SUB_NICHE_MODIFIERS = {
    # Nail styles, shapes & techniques
    "floral", "flower", "french", "chrome", "glazed", "almond", "coffin",
    "square", "stiletto", "short", "acrylic", "gel", "press-on", "marble",
    "glitter", "matte", "ombre", "aura", "cat-eye", "cat", "eye", "3d",
    "abstract", "pearl", "burgundy", "brown", "pink", "blue", "green",
    "red", "pastel", "neon", "checkered", "checker", "swirl", "spider",
    "web", "spider-web", "rhinestone", "gem", "velvet", "seashell", "sunflower",
    # Hair techniques & styles
    "braid", "braids", "bob", "shaggy", "updo", "curly", "wavy", "straight",
    "balayage", "highlight", "lowlight", "pixie", "bangs", "bun", "ponytail",
    "wash-and-go", "bandana", "butterfly", "clip",
    # Makeup & aesthetics
    "skull", "latte", "pumpkin", "spice", "clean-girl", "goth", "porcelain",
    # Specific fashion / home elements
    "mom", "baggy", "wide-leg", "legging", "concrete", "deer", "mailbox",
    "tire", "balcony", "modular", "scandinavian", "centerpiece"
}

# Common noun singularizations
PLURAL_MAP = {
    "nails": "nail",
    "pedicures": "pedicure",
    "manicures": "manicure",
    "hairstyles": "hair",
    "haircuts": "hair",
    "haircut": "hair",
    "outfits": "outfit",
    "clothes": "outfit",
    "braids": "braid",
    "colors": "color",
    "trends": "trend",
    "beds": "bed",
    "fences": "fence",
}

# Cache for published posts so we don't hammer the API on every candidate check
_CACHED_POSTS: Optional[List[Dict]] = None
_CACHE_TIMESTAMP: float = 0.0
CACHE_TTL_SECONDS = 300  # 5 minutes in-memory cache


def clean_html(text: str) -> str:
    """Decodes HTML entities and strips markup."""
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def singularize(word: str) -> str:
    """Normalizes word to singular form."""
    w = word.lower()
    if w in PLURAL_MAP:
        return PLURAL_MAP[w]
    if w.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if w.endswith("es") and len(word) > 4 and w[-3] in "shxz":
        return word[:-2]
    if w.endswith("s") and len(word) > 3 and not w.endswith("ss"):
        return word[:-1]
    return w


def clean_topic(topic: str) -> str:
    """
    Cleans a candidate or existing post topic:
      - Lowercase
      - Removes numbers and years (e.g. 15, 2024, 2026)
      - Strips filler words (viral, stunning, chic, ideas, designs, etc.)
      - Normalizes plurals to singular
    Example: "15 Chic September Nail Ideas" -> "september nail"
    """
    if not topic:
        return ""
    text = clean_html(topic).lower()

    # Strip numbers and years (e.g. "15+", "2024", "2026")
    text = re.sub(r"\b20[12]\d\b|\b\d+\b|\d+\+?", " ", text)

    # Extract alphanumeric words
    raw_words = re.findall(r"[a-z]+", text)
    filtered = []
    for w in raw_words:
        if len(w) <= 1:
            continue
        w_sing = singularize(w)
        if w in FILLER_WORDS or w_sing in FILLER_WORDS:
            continue
        filtered.append(w_sing)

    return " ".join(filtered)


def get_topic_tokens(cleaned_topic_str: str) -> Set[str]:
    """Returns set of words from a cleaned topic string."""
    return set(cleaned_topic_str.split()) if cleaned_topic_str else set()


def calculate_overlap(tokens_a: Set[str], tokens_b: Set[str]) -> Tuple[float, float, float]:
    """
    Calculates overlap metrics between candidate tokens (A) and existing post tokens (B):
      - containment_a: proportion of candidate covered by existing (|A & B| / |A|)
      - dice_score: harmonic overlap (2 * |A & B| / (|A| + |B|))
      - jaccard: standard intersection over union (|A & B| / |A | B|)
    """
    if not tokens_a or not tokens_b:
        return (0.0, 0.0, 0.0)
    inter = len(tokens_a.intersection(tokens_b))
    containment = inter / len(tokens_a)
    dice = (2.0 * inter) / (len(tokens_a) + len(tokens_b))
    union = len(tokens_a.union(tokens_b))
    jaccard = inter / union if union > 0 else 0.0
    return (containment, dice, jaccard)


def load_survivor_map() -> Dict[str, str]:
    """Loads cannibalization loser_slug -> survivor_slug mapping."""
    root_dir = Path(__file__).parent.parent
    map_file = root_dir / "shared" / "survivor_map.json"
    if map_file.exists():
        try:
            with open(map_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def load_published_posts(force_refresh: bool = False) -> List[Dict]:
    """
    Loads all published posts on the site.
    Tries local cache (all_posts.csv / published_links.json) first for speed,
    falls back to live WordPress REST API.
    """
    global _CACHED_POSTS, _CACHE_TIMESTAMP
    now = datetime.now().timestamp()

    if _CACHED_POSTS is not None and not force_refresh and (now - _CACHE_TIMESTAMP) < CACHE_TTL_SECONDS:
        return _CACHED_POSTS

    root_dir = Path(__file__).parent.parent
    csv_file = root_dir / "triage_output" / "all_posts.csv"
    posts = []

    # 1. Try local CSV cache
    if csv_file.exists():
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    words_val = r.get("words", 0)
                    try:
                        w_int = int(words_val or 0)
                    except Exception:
                        w_int = 0
                    posts.append({
                        "id": str(r.get("id", "")),
                        "title": r.get("title", ""),
                        "slug": r.get("slug", ""),
                        "link": r.get("link", ""),
                        "date": r.get("date", "2026-01-01"),
                        "words": w_int
                    })
        except Exception as e:
            print(f"   ⚠️ Could not read all_posts.csv: {e}")

    # 2. If CSV missing or empty, fetch from live WP REST API
    if not posts:
        base_url = os.getenv("WORDPRESS_URL", "https://nailosmetic.com").rstrip("/")
        page = 1
        while True:
            try:
                resp = requests.get(
                    f"{base_url}/wp-json/wp/v2/posts",
                    params={"page": page, "per_page": 100, "status": "publish"},
                    timeout=20
                )
                if resp.status_code == 400:
                    break
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                for p in batch:
                    t_raw = p.get("title", {}).get("rendered", "") if isinstance(p.get("title"), dict) else str(p.get("title", ""))
                    posts.append({
                        "id": str(p.get("id", "")),
                        "title": clean_html(t_raw),
                        "slug": p.get("slug", ""),
                        "link": p.get("link", ""),
                        "date": p.get("date", "")[:10],
                        "words": 0
                    })
                total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
                if page >= total_pages:
                    break
                page += 1
            except Exception as e:
                print(f"   ⚠️ WP API fetch error on page {page}: {e}")
                break

    # Pre-compute cleaned topics and tokens
    for p in posts:
        clean_t = clean_topic(p["title"])
        slug_clean = clean_topic(p.get("slug", "").replace("-", " "))
        combined_cleaned = f"{clean_t} {slug_clean}".strip()
        tokens = set(combined_cleaned.split())
        p["cleaned_topic"] = clean_t
        p["tokens"] = tokens

    _CACHED_POSTS = posts
    _CACHE_TIMESTAMP = now
    return posts


def log_rejection(candidate_topic: str, cleaned_topic: str, matched_post: Dict, score: float, reason: str):
    """Appends rejection details to rejected_topics.log."""
    root_dir = Path(__file__).parent.parent
    log_path = root_dir / "rejected_topics.log"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{now_str}] REJECTED TOPIC: \"{candidate_topic}\"\n")
        f.write(f"   Cleaned Topic  : \"{cleaned_topic}\"\n")
        f.write(f"   Matched Post   : [ID: {matched_post.get('id', 'N/A')}] \"{matched_post.get('title', '')}\"\n")
        f.write(f"   Post URL       : {matched_post.get('link', '')}\n")
        f.write(f"   Post Date      : {matched_post.get('date', 'N/A')}\n")
        f.write(f"   Match Overlap  : {score * 100:.1f}%\n")
        f.write(f"   Reason         : {reason}\n")
        f.write("-" * 80 + "\n")


def add_to_refresh_queue(matched_post: Dict, candidate_topic: str, reason: str):
    """Adds candidate post to shared/refresh_queue.json for future content revamp."""
    root_dir = Path(__file__).parent.parent
    queue_path = root_dir / "shared" / "refresh_queue.json"
    queue_path.parent.mkdir(parents=True, exist_ok=True)

    items = []
    if queue_path.exists():
        try:
            with open(queue_path, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception:
            items = []

    post_id = str(matched_post.get("id", ""))
    # Avoid duplicate queue entries for the same post ID
    if any(str(x.get("id")) == post_id for x in items):
        return

    items.append({
        "id": post_id,
        "title": matched_post.get("title", ""),
        "slug": matched_post.get("slug", ""),
        "link": matched_post.get("link", ""),
        "date": matched_post.get("date", ""),
        "candidate_attempted": candidate_topic,
        "reason": reason,
        "queued_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    try:
        with open(queue_path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)
    except Exception as e:
        print(f"   ⚠️ Could not write to refresh_queue.json: {e}")


def check_topic_detailed(candidate_topic: str) -> Tuple[str, Optional[Dict], float, str]:
    """
    Detailed Topic Gate evaluation.
    Applies:
      1. Normalization & token extraction
      2. Sub-niche modifier differentiation (prevents false positives)
      3. 45-day recency guardrail
      4. >= 80% cannibalization threshold with Survivor Map rerouting
    Returns: (verdict, matched_post, score, reason)
    """
    cleaned_candidate = clean_topic(candidate_topic)
    candidate_tokens = get_topic_tokens(cleaned_candidate)

    if not candidate_tokens:
        return ("ok", None, 0.0, "No semantic tokens found in topic.")

    candidate_modifiers = candidate_tokens.intersection(SUB_NICHE_MODIFIERS)

    published_posts = load_published_posts()
    survivor_map = load_survivor_map()
    now_dt = datetime.now()

    best_match: Optional[Dict] = None
    best_score: float = 0.0
    best_reason: str = ""
    verdict: str = "ok"

    for post in published_posts:
        post_tokens = post.get("tokens", set())
        if not post_tokens:
            continue

        containment, dice, jaccard = calculate_overlap(candidate_tokens, post_tokens)
        score = max(containment, dice)

        # Calculate days since publication
        post_date_str = post.get("date", "")
        days_old = 999
        if post_date_str:
            try:
                p_dt = datetime.strptime(post_date_str[:10], "%Y-%m-%d")
                days_old = (now_dt - p_dt).days
            except Exception:
                days_old = 999

        post_modifiers = post_tokens.intersection(SUB_NICHE_MODIFIERS)

        # Rule 6: Recency Rule (Last 45 days)
        if days_old <= 45:
            # Sub-niche Modifier Guardrail:
            # If candidate specifies a sub-niche modifier (e.g. "floral") that the existing
            # post does NOT possess (e.g. general spring short nails), do NOT reject as duplicate.
            if candidate_modifiers and not candidate_modifiers.intersection(post_modifiers):
                # Distinct sub-niche intent — exempt from generic recency rejection
                continue

            is_same_core = (cleaned_candidate == post.get("cleaned_topic")) or (score >= 0.50)
            if is_same_core:
                reason = f"Recency rule: '{post['title']}' published {days_old} days ago (<= 45 days) with {score*100:.1f}% topic match."
                if score > best_score:
                    best_score = score
                    best_match = post
                    best_reason = reason
                    verdict = "duplicate"

        # Rule 4 & 5: High overlap (>= 80%) with existing post
        elif score >= 0.80:
            # Also respect sub-niche differentiation unless overlap is truly overwhelming (>= 90%)
            if candidate_modifiers and not candidate_modifiers.intersection(post_modifiers) and score < 0.90:
                continue

            reason = f"High topic overlap ({score*100:.1f}% >= 80%) with existing post [ID: {post['id']}] '{post['title']}'."
            if score > best_score:
                best_score = score
                best_match = post
                best_reason = reason
                verdict = f"refresh:{post['id']}"

    # Survivor Map Rerouting
    # If the matched post is a cannibalized loser, route to its canonical pillar survivor post
    if best_match and verdict.startswith("refresh:"):
        post_slug = best_match.get("slug", "")
        if post_slug in survivor_map:
            survivor_slug = survivor_map[post_slug]
            survivor_post = next((p for p in published_posts if p.get("slug") == survivor_slug), None)
            if survivor_post:
                reroute_reason = (
                    f"Rerouted via survivor map from '{post_slug}' to canonical pillar '{survivor_slug}' "
                    f"[ID: {survivor_post['id']}]."
                )
                best_match = survivor_post
                best_reason = f"{best_reason} | {reroute_reason}"
                verdict = f"refresh:{survivor_post['id']}"

    if verdict != "ok" and best_match:
        log_rejection(
            candidate_topic=candidate_topic,
            cleaned_topic=cleaned_candidate,
            matched_post=best_match,
            score=best_score,
            reason=best_reason
        )
        if verdict.startswith("refresh:"):
            add_to_refresh_queue(best_match, candidate_topic, best_reason)

    return (verdict, best_match, best_score, best_reason)


def check_topic(candidate_topic: str) -> str:
    """
    Authoritative Topic Gatekeeper:
    Returns:
      - "ok" : Topic is fresh and approved for generation.
      - "duplicate" : Matches a post published in the last 45 days (recency rule). Blocked.
      - "refresh:<post_id>" : Matches an older existing post (>45 days, >=80% overlap).
                              Blocked from new post creation; old post added to refresh_queue.json.
    """
    verdict, _, _, _ = check_topic_detailed(candidate_topic)
    return verdict


def run_test_suite() -> List[Dict]:
    """
    Runs topic gate against 10 test topics to demonstrate rejection & survivor behavior.
    """
    test_topics = [
        "15 Chic September Nail Ideas",
        "Back to School Nail Art for Campus",
        "Cute Fall Nails Burgundy Style",
        "Fall Nails Brown Chrome 2026",
        "Spooky Halloween Skull Makeup",
        "7 Fresh Spring Floral Nail Designs",
        "How to Style Baggy Mom Jeans for Everyday Wear",
        "Bio-Synthetic Hybrid Hair Extensions 2027",
        "10 Viral Cyberpunk Neon Green Nails",
        "Minimalist Scandinavian Living Room Decor"
    ]

    print("\n" + "=" * 80)
    print("🧪 TOPIC GATE TEST SUITE — WITH SUB-NICHE & SURVIVOR MAP RULES")
    print("=" * 80 + "\n")

    results = []
    for i, topic in enumerate(test_topics, 1):
        cleaned = clean_topic(topic)
        verdict, best_match, score, reason = check_topic_detailed(topic)

        matched_title = best_match.get("title", "") if best_match else "None"
        matched_id = best_match.get("id", "N/A") if best_match else "N/A"
        matched_slug = best_match.get("slug", "") if best_match else ""
        matched_date = best_match.get("date", "N/A") if best_match else "N/A"

        status_emoji = "✅ APPROVED" if verdict == "ok" else ("🛑 DUPLICATE (Recency Rule)" if verdict == "duplicate" else f"🔄 REFRESH [Pillar ID: {matched_id}]")

        print(f"[{i:02d}] Candidate: \"{topic}\"")
        print(f"     Cleaned  : \"{cleaned}\"")
        print(f"     Verdict  : {status_emoji} ({verdict})")
        if verdict != "ok":
            print(f"     Target   : [{matched_id}] \"{matched_title}\" (slug: {matched_slug}, Date: {matched_date})")
            print(f"     Overlap  : {score * 100:.1f}%")
            print(f"     Reason   : {reason}")
        print("-" * 80)

        results.append({
            "candidate": topic,
            "cleaned": cleaned,
            "verdict": verdict,
            "matched_id": matched_id,
            "matched_slug": matched_slug,
            "matched_title": matched_title,
            "matched_date": matched_date,
            "overlap": score,
            "reason": reason
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="Pre-generation topic gatekeeper (READ-ONLY test & check).")
    parser.add_argument("--test", action="store_true", help="Run diagnostic test suite on 10 realistic topics.")
    parser.add_argument("--check", type=str, help="Check a specific topic string.")
    args = parser.parse_args()

    if args.test:
        run_test_suite()
    elif args.check:
        verdict, best_match, score, reason = check_topic_detailed(args.check)
        cleaned = clean_topic(args.check)
        print(f"Candidate: \"{args.check}\"")
        print(f"Cleaned  : \"{cleaned}\"")
        print(f"Verdict  : {verdict}")
        if best_match:
            print(f"Matched  : [{best_match.get('id')}] \"{best_match.get('title')}\"")
            print(f"Score    : {score*100:.1f}%")
            print(f"Reason   : {reason}")
    else:
        print("Usage:")
        print("  python wordpress_automation/topic_gate.py --test")
        print("  python wordpress_automation/topic_gate.py --check \"15 Chic September Nail Ideas\"")


if __name__ == "__main__":
    main()
