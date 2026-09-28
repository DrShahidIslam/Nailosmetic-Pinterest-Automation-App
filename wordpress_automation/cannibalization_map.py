"""
cannibalization_map.py — Keyword and topic cannibalization detector for nailosmetic.com.

Identifies groups of published articles that target the same or overlapping search
intents (e.g., multiple posts about "back to school nails", "september nails", "hoco hair").

Cannibalization harms SEO because competing URLs from the same domain split link equity,
confuse Google's ranking algorithms, and frequently cause Google to demote or drop them
into "crawled - currently not indexed".

READ-ONLY: This script NEVER deletes, redirects, or modifies anything on WordPress.
It clusters competing articles, identifies the strongest candidate to serve as the
primary pillar, and provides recommendations for your manual review.

Usage:
    python wordpress_automation/cannibalization_map.py
    python wordpress_automation/cannibalization_map.py --source csv
    python wordpress_automation/cannibalization_map.py --source api
    python wordpress_automation/cannibalization_map.py --min-cluster-size 2
"""

import argparse
from collections import defaultdict
import csv
from datetime import datetime
from html import unescape
import io
import json
import os
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Set, Tuple
import requests

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, io.UnsupportedOperation):
        pass

# Fluff / stop words commonly found in SEO titles that dilute topic intent
STOP_WORDS = {
    "a", "about", "above", "after", "again", "all", "almost", "also", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "if", "in", "into", "is",
    "it", "its", "itself", "just", "me", "more", "most", "my", "myself",
    "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or",
    "other", "our", "ours", "ourselves", "out", "over", "own", "s", "same",
    "she", "should", "so", "some", "such", "t", "than", "that", "the",
    "their", "theirs", "them", "themselves", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "you", "your", "yours",
    # Editorial fluff words
    "ideas", "idea", "designs", "design", "inspo", "inspiration", "trends",
    "trend", "trendy", "look", "looks", "looking", "aesthetic", "tutorial",
    "tutorials", "hacks", "hack", "tips", "tip", "secrets", "secret",
    "ways", "way", "guide", "guides", "simple", "cute", "easy", "viral",
    "stylish", "style", "styles", "gorgeous", "stunning", "chic", "best",
    "top", "ultimate", "must", "have", "need", "elevate", "obsess",
    "everyday", "instant", "instantly", "picturesque", "moments", "pro",
    "fresh", "dazzling", "perfect", "season", "bloom", "score", "big",
    "budget", "friendly", "diy", "unveil", "unlock", "effortless",
    "revitalize", "essential", "expensive", "game", "changing",
    # Years and numbers
    "2023", "2024", "2025", "2026", "2027", "2028"
}

# Normalization map for synonyms and common nail/beauty variations
SYNONYMS = {
    "hoco": "homecoming",
    "pedicures": "pedicure",
    "manicures": "manicure",
    "nails": "nail",
    "hairstyles": "hair",
    "haircuts": "hair",
    "haircut": "hair",
    "outfits": "outfit",
    "clothes": "outfit",
    "wardrobe": "outfit",
    "attire": "outfit",
    "fall": "autumn",
    "short": "short",
    "chrome": "chrome",
    "gel": "gel",
    "acrylic": "acrylic",
    "press-on": "press-on",
}


def clean_html(text: str) -> str:
    """Decodes HTML entities and strips unwanted markup."""
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def singularize(word: str) -> str:
    """Basic plural to singular normalization."""
    word = word.lower()
    if word in SYNONYMS:
        return SYNONYMS[word]
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 4 and word[-3] in "shxz":
        return word[:-2]
    if word.endswith("s") and len(word) > 3 and not word.endswith("ss"):
        return word[:-1]
    return word


def extract_topic_tokens(title: str, slug: str) -> Set[str]:
    """
    Extracts core keyword intent tokens from a post's title and slug,
    ignoring formatting fluff and numbers.
    """
    # Prefer slug if clean, but combine with title for full semantic context
    slug_text = (slug or "").replace("-", " ")
    combined = f"{title} {slug_text}".lower()
    raw_tokens = re.findall(r"[a-z0-9]+", combined)

    tokens = set()
    for tok in raw_tokens:
        if tok.isdigit() or len(tok) <= 2:
            continue
        tok = singularize(tok)
        if tok in STOP_WORDS:
            continue
        tokens.add(tok)

    return tokens


def extract_core_topic_signature(title: str, slug: str) -> Tuple[str, str]:
    """
    Identifies the primary topic category and signature.
    Returns (topic_name, signature_key).
    """
    slug_text = (slug or "").replace("-", " ")
    combined = f"{slug_text} {title}".lower()

    # Pre-defined primary intent patterns
    patterns = [
        (r"back to school|school nail", "Back to School Nails"),
        (r"september nail|september 2026 nail|nail.*september", "September Nails"),
        (r"fall nail|autumn nail|summer (to|into) fall nail", "Fall & Autumn Nails"),
        (r"halloween nail|spooky nail", "Halloween Nails"),
        (r"pumpkin nail|pumpkin spice nail", "Pumpkin & Pumpkin Spice Nails"),
        (r"french tip|french nail", "French Tip Nails"),
        (r"almond nail", "Almond Nails"),
        (r"coffin nail", "Coffin Nails"),
        (r"chrome nail|glazed nail", "Chrome & Glazed Nails"),
        (r"cat eye nail", "Cat Eye Nails"),
        (r"aura nail", "Aura Nails"),
        (r"prom nail", "Prom Nails"),
        (r"spring nail", "Spring Nails"),
        (r"summer nail|summer toe", "Summer Nails & Pedicures"),
        (r"winter nail|christmas nail", "Winter & Holiday Nails"),
        (r"pedicure|toe nail", "Pedicure & Toe Nails"),
        (r"press on nail", "Press-On Nails"),
        (r"hoco hair|homecoming hair|hoco hairstyle", "Homecoming (Hoco) Hairstyles"),
        (r"hoco makeup|homecoming makeup", "Homecoming (Hoco) Makeup"),
        (r"halloween makeup|spooky makeup|skull makeup", "Halloween Makeup"),
        (r"shaggy bob|bob haircut", "Bob & Shaggy Haircuts"),
        (r"curly hair|wash and go", "Curly Hair & Wash-and-Go"),
        (r"prom makeup|prom look", "Prom Makeup"),
        (r"prom picture|prom pose|prom outfit", "Prom Outfits & Poses"),
        (r"fall outfit|autumn outfit", "Fall & Autumn Outfits"),
        (r"legging outfit|legging look", "Leggings Outfits"),
        (r"tulip farm outfit", "Tulip Farm Outfits"),
        (r"baseball outfit|game outfit|texas rangers", "Game Day & Sports Outfits"),
        (r"vacation outfit", "Vacation Outfits"),
        (r"concrete block garden|garden bed", "Concrete Block & Raised Garden Beds"),
        (r"deer proof garden|garden fence", "Deer Proof Garden Fences"),
        (r"mailbox garden", "Mailbox Garden Ideas"),
        (r"tire garden", "Tire Garden Ideas"),
        (r"front yard landscaping|curb appeal", "Front Yard & Curb Appeal Landscaping"),
        (r"fall centerpiece|table centerpiece", "Fall Table Centerpieces"),
        (r"halloween window|window painting", "Halloween Window Painting"),
    ]

    for regex, name in patterns:
        if re.search(regex, combined):
            return (name, name.lower().replace(" ", "_"))

    # Fallback to top token pair signature
    tokens = sorted(list(extract_topic_tokens(title, slug)))
    if len(tokens) >= 2:
        top_pair = f"{tokens[0]}_{tokens[1]}"
        name = f"{tokens[0].capitalize()} & {tokens[1].capitalize()}"
        return (name, top_pair)
    elif len(tokens) == 1:
        return (tokens[0].capitalize(), tokens[0])
    return ("General / Uncategorized", "uncategorized")


def calculate_jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Calculates Jaccard token overlap between two sets of tokens."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return intersection / union if union > 0 else 0.0


def fetch_posts_from_csv(csv_path: Path) -> List[Dict]:
    """Loads posts from local triage CSV."""
    if not csv_path.exists():
        return []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def fetch_posts_from_api(base_url: str = "https://nailosmetic.com") -> List[Dict]:
    """Fetches posts live from WordPress REST API."""
    posts = []
    page = 1
    per_page = 100
    print(f"🌐 Fetching live posts from {base_url}/wp-json/wp/v2/posts...")

    while True:
        try:
            url = f"{base_url.rstrip('/')}/wp-json/wp/v2/posts"
            resp = requests.get(url, params={"page": page, "per_page": per_page, "status": "publish"}, timeout=20)
            if resp.status_code == 400:
                break
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            for p in batch:
                title_raw = p.get("title", {}).get("rendered", "") if isinstance(p.get("title"), dict) else str(p.get("title", ""))
                content_raw = p.get("content", {}).get("rendered", "") if isinstance(p.get("content"), dict) else ""
                clean_content = clean_html(content_raw)
                words = len(clean_content.split()) if clean_content else 0

                posts.append({
                    "id": str(p.get("id", "")),
                    "title": clean_html(title_raw),
                    "link": p.get("link", ""),
                    "date": p.get("date", "")[:10],
                    "slug": p.get("slug", ""),
                    "words": str(words),
                    "score": "N/A"
                })
            sys.stdout.write(f"\r   Fetched {len(posts)} posts so far...")
            sys.stdout.flush()
            total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
            if page >= total_pages:
                break
            page += 1
        except Exception as e:
            print(f"\n   ⚠️ API fetch error on page {page}: {e}")
            break

    print(f"\n   ✅ Fetched {len(posts)} posts from WordPress API.")
    return posts


def cluster_posts(posts: List[Dict], min_size: int = 2) -> List[Dict]:
    """
    Groups posts into topic cannibalization clusters.
    Each cluster identifies:
      - topic_name: High level search intent
      - primary_pillar: The strongest article (highest word count / score)
      - competitors: The redundant articles splitting search traffic
      - suggested_action: Strategy to resolve (Redirect / Consolidate / Re-angle)
    """
    grouped_by_signature = defaultdict(list)

    for p in posts:
        title = p.get("title", "")
        slug = p.get("slug", "")
        topic_name, sig_key = extract_core_topic_signature(title, slug)
        tokens = extract_topic_tokens(title, slug)

        p_enriched = dict(p)
        p_enriched["tokens"] = tokens
        p_enriched["topic_name"] = topic_name
        p_enriched["sig_key"] = sig_key
        # Parse word count cleanly
        try:
            p_enriched["word_count"] = int(p.get("words", 0) or 0)
        except (ValueError, TypeError):
            p_enriched["word_count"] = 0

        grouped_by_signature[sig_key].append(p_enriched)

    # Secondary fuzzy pass: merge clusters that share high token overlap
    clusters = []
    for sig_key, cluster_items in grouped_by_signature.items():
        if len(cluster_items) < min_size:
            continue

        # Sort posts within the cluster by word count / depth descending
        cluster_items.sort(key=lambda x: x["word_count"], reverse=True)
        primary = cluster_items[0]
        competitors = cluster_items[1:]

        topic_label = cluster_items[0]["topic_name"]

        # Determine best resolution strategy
        avg_words = sum(x["word_count"] for x in cluster_items) / len(cluster_items)
        if len(cluster_items) >= 4 and avg_words < 500:
            action = "MERGE & 301 REDIRECT: Consolidate content into the primary pillar, then 301 redirect secondary URLs."
        elif any(x["word_count"] < 350 for x in competitors):
            action = "301 REDIRECT THIN POSTS: Thin competitor posts (<350 words) should be 301-redirected to the primary pillar."
        else:
            action = "DIFFERENTIATE OR CONSOLIDATE: Adjust H1s and focus keywords for distinct sub-intents (e.g. short vs coffin, acrylic vs gel) or merge."

        clusters.append({
            "topic_name": topic_label,
            "signature": sig_key,
            "total_posts": len(cluster_items),
            "primary_pillar": primary,
            "competitors": competitors,
            "suggested_action": action,
            "all_posts": cluster_items
        })

    # Sort clusters by size descending (largest cannibalization problem first)
    clusters.sort(key=lambda c: c["total_posts"], reverse=True)
    return clusters


def main():
    root_dir = Path(__file__).parent.parent

    parser = argparse.ArgumentParser(description="Find keyword cannibalization clusters on nailosmetic.com (READ-ONLY).")
    parser.add_argument("--source", choices=["auto", "api", "csv"], default="auto",
                        help="Data source: 'auto', 'api', or 'csv'.")
    parser.add_argument("--csv-path", default="triage_output/all_posts.csv",
                        help="Path to all_posts.csv.")
    parser.add_argument("--output-dir", default="triage_output",
                        help="Directory to save reports.")
    parser.add_argument("--min-cluster-size", type=int, default=2,
                        help="Minimum number of competing posts to form a cluster (default: 2).")
    args = parser.parse_args()

    csv_file = root_dir / args.csv_path
    out_dir = root_dir / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    posts = []
    source_used = ""

    if args.source == "api":
        posts = fetch_posts_from_api()
        source_used = "WordPress REST API (Live)"
    elif args.source == "csv":
        posts = fetch_posts_from_csv(csv_file)
        source_used = f"Local CSV ({csv_file.name})"
    else:  # auto
        if csv_file.exists():
            posts = fetch_posts_from_csv(csv_file)
            source_used = f"Local CSV cache ({csv_file.name})"
        else:
            posts = fetch_posts_from_api()
            source_used = "WordPress REST API (Live)"

    if not posts:
        print("❌ No posts found. Ensure triage_output/all_posts.csv exists or use --source api.")
        sys.exit(1)

    print(f"\n🗺️  Analyzing {len(posts)} posts from {source_used} for keyword cannibalization clusters...\n")

    clusters = cluster_posts(posts, min_size=args.min_cluster_size)
    total_cannibalizing_posts = sum(c["total_posts"] for c in clusters)

    print("=" * 80)
    print("📊 CANNIBALIZATION AUDIT SUMMARY (READ-ONLY — NO CHANGES MADE)")
    print("=" * 80)
    print(f"Total Posts Audited              : {len(posts)}")
    print(f"Cannibalization Clusters Found   : {len(clusters)}")
    print(f"Total Competing Posts in Clusters: {total_cannibalizing_posts} ({(total_cannibalizing_posts/len(posts)*100):.1f}% of total posts)")
    print("=" * 80)

    # Print top clusters to terminal
    print("\nTOP CANNIBALIZATION CLUSTERS (RANKED BY SIZE):")
    print("-" * 80)
    for i, cluster in enumerate(clusters[:15], 1):
        print(f"[{i:02d}] 🏷️ Topic: {cluster['topic_name']} ({cluster['total_posts']} competing posts)")
        primary = cluster["primary_pillar"]
        print(f"     ⭐ RECOMMENDED PILLAR : [{primary['id']}] \"{primary['title']}\" ({primary['word_count']} words, Date: {primary.get('date', 'N/A')})")
        print(f"        🔗 URL: {primary.get('link', 'N/A')}")
        print(f"     ⚔️  COMPETING POSTS   :")
        for comp in cluster["competitors"][:4]:
            print(f"        • [{comp['id']}] \"{comp['title']}\" ({comp['word_count']} words, Date: {comp.get('date', 'N/A')})")
        if len(cluster["competitors"]) > 4:
            print(f"        ... and {len(cluster['competitors']) - 4} more competing posts in this cluster.")
        print(f"     💡 Strategy: {cluster['suggested_action']}")
        print()

    if len(clusters) > 15:
        print(f"... and {len(clusters) - 15} more clusters. See full report files below.")

    # Write Markdown Report
    md_path = out_dir / "cannibalization_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 🗺️ Nailosmetic Keyword Cannibalization Audit Map\n\n")
        f.write(f"- **Generated At**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **Data Source**: {source_used}\n")
        f.write(f"- **Total Posts Audited**: {len(posts)}\n")
        f.write(f"- **Total Cannibalization Clusters**: {len(clusters)}\n")
        f.write(f"- **Total Posts Involved**: {total_cannibalizing_posts}\n\n")
        f.write("> **SAFETY NOTE**: This report is **READ-ONLY**. No posts have been redirected, consolidated, or deleted. All actions are recommendations for your manual decision.\n\n")
        f.write("## 📌 Summary of All Clusters\n\n")
        f.write("| # | Topic Cluster | Size | Recommended Pillar (Strongest Post) | Words | Competing URLs Count | Suggested Strategy |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for i, c in enumerate(clusters, 1):
            p = c["primary_pillar"]
            p_title = p["title"].replace("|", "-")
            p_link = f"[{p_title}]({p.get('link', '#')})" if p.get("link") else p_title
            strat_short = c["suggested_action"].split(":")[0]
            f.write(f"| {i} | **{c['topic_name']}** | {c['total_posts']} | {p_link} | {p['word_count']} | {len(c['competitors'])} | {strat_short} |\n")

        f.write("\n\n## 🔍 Detailed Cluster Breakdown\n\n")
        for i, c in enumerate(clusters, 1):
            f.write(f"### Cluster {i}: {c['topic_name']} ({c['total_posts']} Posts)\n\n")
            f.write(f"**Recommended Action**: {c['suggested_action']}\n\n")
            f.write("| Role | ID | Title | Word Count | Publish Date | Link |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
            p = c["primary_pillar"]
            p_link_md = f"[View]({p.get('link', '')})" if p.get("link") else "N/A"
            f.write(f"| ⭐ **Pillar** | {p['id']} | **{p['title'].replace('|', '-')}** | {p['word_count']} | {p.get('date', 'N/A')} | {p_link_md} |\n")
            for comp in c["competitors"]:
                c_link_md = f"[View]({comp.get('link', '')})" if comp.get("link") else "N/A"
                f.write(f"| ⚔️ Competitor | {comp['id']} | {comp['title'].replace('|', '-')} | {comp['word_count']} | {comp.get('date', 'N/A')} | {c_link_md} |\n")
            f.write("\n---\n\n")

    # Write CSV Export
    csv_path = out_dir / "cannibalization_map.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "cluster_id", "cluster_topic", "cluster_size",
            "role", "post_id", "post_title", "slug", "link",
            "word_count", "date", "suggested_action"
        ])
        for c_idx, c in enumerate(clusters, 1):
            # Write Pillar row
            p = c["primary_pillar"]
            writer.writerow([
                c_idx, c["topic_name"], c["total_posts"],
                "PILLAR", p["id"], p["title"], p.get("slug", ""), p.get("link", ""),
                p["word_count"], p.get("date", ""), c["suggested_action"]
            ])
            # Write Competitor rows
            for comp in c["competitors"]:
                writer.writerow([
                    c_idx, c["topic_name"], c["total_posts"],
                    "COMPETITOR", comp["id"], comp["title"], comp.get("slug", ""), comp.get("link", ""),
                    comp["word_count"], comp.get("date", ""), c["suggested_action"]
                ])

    print("\n💾 Full reports saved successfully:")
    print(f"   📄 Markdown Map : {md_path}")
    print(f"   📊 CSV Dataset  : {csv_path}")
    print("\n🔒 Purely diagnostic. No changes were made to your site.\n")


if __name__ == "__main__":
    main()
