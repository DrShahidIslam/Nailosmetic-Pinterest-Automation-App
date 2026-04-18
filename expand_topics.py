"""
Expand the topic bank by harvesting more Pinterest trends for thin niches (especially hair_beauty).
Also adds manually curated high-volume keywords to ensure each niche has 40+ topics.
"""
import json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    print("requests not installed")
    sys.exit(1)

# Load existing bank
with open("shared/topic_bank.json", "r") as f:
    bank = json.load(f)

print("=== Current Topic Bank ===")
for niche, topics in bank.items():
    print(f"  {niche}: {len(topics)} topics")

# =========================================================
# STEP 1: Try to harvest more from Pinterest API
# =========================================================
TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN", "")
if not TOKEN:
    try:
        with open(".env") as f:
            for line in f:
                if line.startswith("PINTEREST_ACCESS_TOKEN"):
                    TOKEN = line.split("=", 1)[1].strip().strip('"')
    except:
        pass

api_trends = {"hair_beauty": [], "home_garden": []}

if TOKEN:
    print(f"\nPinterest token found: ...{TOKEN[-8:]}")
    BASE = "https://api.pinterest.com/v5"
    HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    
    hair_seeds = [
        "hairstyles", "hair color", "braids", "hair trends",
        "balayage", "curtain bangs", "bob haircut", "hair accessories",
        "natural hair", "curly hair", "updo", "ponytail styles",
        "skincare routine", "makeup looks", "glowy skin", "lip gloss",
        "blonde hair ideas", "brunette hair", "layered haircut", "pixie cut",
        "wedding hair", "bridal hair", "summer hair", "spring hair"
    ]
    
    home_seeds = [
        "living room decor", "bedroom aesthetic", "kitchen design",
        "bathroom renovation", "cozy bedroom", "minimalist home",
        "boho living room", "modern farmhouse", "small space design",
        "apartment decor", "wall art ideas", "bookshelf styling"
    ]
    
    for seed in hair_seeds:
        try:
            resp = requests.get(
                f"{BASE}/trends/suggestions",
                headers=HEADERS,
                params={"region": "US", "trend_type": "growing", "query": seed},
                timeout=10
            )
            if resp.status_code == 200:
                for t in resp.json().get("trends", []):
                    kw = t.get("keyword", "")
                    if kw and kw not in api_trends["hair_beauty"]:
                        api_trends["hair_beauty"].append(kw)
            time.sleep(0.3)
        except Exception as e:
            print(f"  Error on '{seed}': {e}")
    
    for seed in home_seeds:
        try:
            resp = requests.get(
                f"{BASE}/trends/suggestions",
                headers=HEADERS,
                params={"region": "US", "trend_type": "growing", "query": seed},
                timeout=10
            )
            if resp.status_code == 200:
                for t in resp.json().get("trends", []):
                    kw = t.get("keyword", "")
                    if kw and kw not in api_trends["home_garden"]:
                        api_trends["home_garden"].append(kw)
            time.sleep(0.3)
        except Exception as e:
            print(f"  Error on '{seed}': {e}")
    
    print(f"\nAPI harvest: hair_beauty={len(api_trends['hair_beauty'])}, home_garden={len(api_trends['home_garden'])}")
else:
    print("\nNo Pinterest token — skipping API harvest")

# =========================================================
# STEP 2: Manually curated high-volume keywords
# These are known high-traffic Pinterest searches for 2026
# =========================================================
curated_topics = {
    "hair_beauty": [
        # Hairstyles
        "balayage hair ideas", "curtain bangs hairstyle", "layered haircut medium length",
        "bob haircut 2026", "pixie cut ideas", "wolf cut hairstyle", "butterfly haircut",
        "long layers haircut", "shaggy bob haircut", "french bob haircut",
        "money piece hair color", "copper hair color", "strawberry blonde hair",
        "mushroom brown hair", "platinum blonde hair ideas", "chocolate brown hair",
        "auburn hair color ideas", "honey blonde highlights", "caramel balayage",
        "face framing highlights", "lowlights and highlights", "ombre hair ideas",
        # Braids and updos
        "boho braids hairstyle", "waterfall braid tutorial", "fishtail braid styles",
        "dutch braid hairstyle", "goddess braids", "knotless braids ideas",
        "box braids styles", "french braid updo", "messy bun hairstyle",
        "elegant updo hairstyle", "half up half down hairstyle", "wedding updo ideas",
        # Natural hair
        "natural hair styles", "twist out natural hair", "wash and go curly hair",
        "protective styles natural hair", "loc styles for women", "bantu knots hairstyle",
        # Beauty
        "clean girl makeup look", "soft glam makeup", "natural no makeup look",
        "glass skin routine", "korean skincare routine", "dewy makeup look",
        "summer makeup trends", "spring makeup looks", "bridal makeup ideas",
        "lip liner tutorial", "fluffy brows tutorial", "latte makeup look",
    ],
    "home_garden": [
        "cozy living room ideas", "modern bedroom design", "small bathroom makeover",
        "kitchen island ideas", "open shelving kitchen", "farmhouse kitchen decor",
        "reading nook ideas", "home office setup", "gallery wall ideas",
        "accent wall ideas", "floating shelves styling", "console table decor",
        "entryway decor ideas", "mudroom organization", "laundry room makeover",
        "pantry organization ideas", "closet organization", "under stairs storage",
        "window seat ideas", "bay window decor", "fireplace mantel decor",
        "dining room table centerpiece", "outdoor dining area",
        "bathroom vanity ideas", "powder room decor", "guest bedroom ideas",
    ],
    "fashion_style": [
        "capsule wardrobe spring", "work outfit ideas", "date night outfit",
        "airport outfit ideas", "concert outfit ideas", "graduation outfit",
        "garden party outfit", "vacation outfit ideas", "beach vacation outfits",
        "summer dress outfit", "linen pants outfit", "white sneakers outfit",
        "maxi skirt outfit", "midi dress outfit", "blazer outfit women",
    ]
}

# =========================================================
# STEP 3: Merge everything into the bank
# =========================================================
for niche in ["hair_beauty", "home_garden", "fashion_style"]:
    existing = set(bank.get(niche, []))
    added = 0
    
    # Add API trends
    for t in api_trends.get(niche, []):
        if t.lower() not in {x.lower() for x in existing}:
            bank[niche].append(t)
            existing.add(t)
            added += 1
    
    # Add curated topics
    for t in curated_topics.get(niche, []):
        if t.lower() not in {x.lower() for x in existing}:
            bank[niche].append(t)
            existing.add(t)
            added += 1
    
    print(f"  {niche}: +{added} new topics")

# Save
with open("shared/topic_bank.json", "w") as f:
    json.dump(bank, f, indent=4, ensure_ascii=False)

print("\n=== Final Topic Bank ===")
total = 0
for niche, topics in bank.items():
    print(f"  {niche}: {len(topics)} topics")
    total += len(topics)
print(f"  TOTAL: {total} topics")
