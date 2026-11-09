import os
import re
import csv
import json
import hashlib
from typing import List, Dict
from urllib.parse import urlsplit
from firecrawl import FirecrawlApp

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ARCHIVE_DIR, load_api_key  # noqa: E402

BLACKLIST_DOMAINS = [
    "reddit.com", "tripadvisor", "yelp", "blogspot.com", "wordpress.com", "medium.com",
    "facebook.com", "instagram.com", "youtube.com", "pinterest.com", "tiktok.com", "twitter.com",
    "x.com", "linkedin.com", "guide.michelin.com", "michelin.com", "timeout.com", "cntraveler.com",
    "cntraveller.com", "lonelyplanet.com", "fodors.com", "frommers.com", "theculturetrip.com",
    "culturetrip.com", "sortiraparis.com", "paris.com", "visitparisregion.com", "wikipedia.org",
    "booking.com", "expedia.com", "hotels.com", "kayak.com", "agoda.com", "trivago.com",
    "airbnb.com", "trip.com", "hotelscombined.com", "momondo.com", "skyscanner.com", "orbitz.com",
    "priceline.com", "hotwire.com", "foursquare.com", "mapquest.com", "trustpilot.com",
    "pagesjaunes.fr", "petitfute.com", "marieclaire.fr", "vogue.fr", "elle.fr", "yellowpages.com",
    "forbestravelguide.com", "parisinsidersguide.com", "pariswebservices.com", "parisbym.com",
    "europeupclose.com", "scrapehero.com", "halalzilla.com", "maps.apple.com", "global.kfc.com",
    "promoalert.com", "mappy.com", "mapcarta.com", "ubereats.com", "deliveroo", "just-eat",
    "doordash", "grubhub", "glassdoor", "indeed.com", "yonder-society.com", "esprit-de-france.com",
    "parisperfect.com", "theadventurouskate.com", "thebrokebackpacker.com", "hotelchatter.com"
]
BLACKLIST_PATHS = ["/article/", "/blog/", "/news/", "/guide/", "/things-to-do/", "/best-", "/top-",
                   "/best_", "/top_", "/tops/", "/gallery/", "/press-release", "/press/",
                   "the-best-", "best-boutique", "where-to-stay", "discover-the-best"]

WORD_STARS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
STAR_RE = re.compile(r'\b([1-5])\s*[- ]?(?:star|stars|étoile|étoiles|etoile|etoiles)\b', re.IGNORECASE)


def generate_unique_id(url: str) -> str:
    return "ID_" + hashlib.md5(url.encode()).hexdigest()[:8].upper()


def parse_target_stars(text: str):
    match = STAR_RE.search(text)
    if match:
        return int(match.group(1))
    low = text.lower()
    for word, value in WORD_STARS.items():
        if re.search(r'\b' + word + r'\s*[- ]?star', low):
            return value
    return None


def mentioned_stars(text: str) -> set:
    low = text.lower()
    found = set()
    for match in STAR_RE.finditer(low):
        found.add(int(match.group(1)))
    for word, value in WORD_STARS.items():
        if re.search(r'\b' + word + r'\s*[- ]?star', low):
            found.add(value)
    for match in re.finditer(r'(?<!\d)([1-5])\s*\*', low):
        found.add(int(match.group(1)))
    for run in re.findall(r'(?<!\d)(\*{1,5})(?!\d)', low):
        found.add(len(run))
    return found


def star_matches(title: str, snippet: str, target) -> bool:
    if not target:
        return True
    mentioned = mentioned_stars(f"{title} {snippet}")
    if not mentioned:
        return True
    return target in mentioned


def is_reputable_source(url: str) -> bool:
    lower = url.lower()
    host = urlsplit(lower).netloc
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    for domain in BLACKLIST_DOMAINS:
        if host == domain or host.endswith("." + domain) or domain in labels:
            return False
    path = urlsplit(lower).path
    if any(marker in path for marker in BLACKLIST_PATHS):
        return False
    return True


def lead_score(url: str, title: str, snippet: str, target) -> int:
    score = 0
    if target and target in mentioned_stars(f"{title} {snippet}"):
        score += 5
    if "hotel" in url.lower():
        score += 2
    return score


def discover_leads(query: str, limit: int = 5):
    print(f"🔎 Searching for official outlets: {query}...")
    api_key = load_api_key()
    if not api_key:
        print("❌ API Key missing.")
        return []

    target_stars = parse_target_stars(query)
    if target_stars:
        print(f"⭐ Requiring {target_stars}-star hotels")

    app = FirecrawlApp(api_key=api_key)
    search_result = app.search(query, limit=max(limit * 4, 20))
    leads_data = getattr(search_result, "web", None)
    if leads_data is None and isinstance(search_result, dict):
        leads_data = search_result.get("web", [])
    leads_data = leads_data or []

    candidates = []
    seen_urls = set()
    for result in leads_data:
        url = getattr(result, "url", "") or (result.get("url") if isinstance(result, dict) else "")
        title = getattr(result, "title", "") or ""
        snippet = getattr(result, "description", "") or ""
        if not url or not is_reputable_source(url):
            continue
        if re.search(r'\b(best|top)\b.{0,25}\d|\bguide\b|\bwhere to stay\b', title, re.IGNORECASE):
            continue
        if not star_matches(title, snippet, target_stars):
            continue
        key = urlsplit(url)._replace(query="", fragment="").geturl().rstrip("/").lower()
        if key in seen_urls:
            continue
        seen_urls.add(key)
        candidates.append({
            "score": lead_score(url, title, snippet, target_stars),
            "lead_id": generate_unique_id(url),
            "company_name": title or "Unknown",
            "website_url": url,
            "snippet": snippet,
            "address": "Pending",
            "phone": "Pending",
            "email": "Pending"
        })

    candidates.sort(key=lambda item: item["score"], reverse=True)
    processed_leads = []
    for item in candidates:
        if len(processed_leads) >= limit:
            break
        item.pop("score", None)
        processed_leads.append(item)

    return processed_leads


def save_leads_to_folder(leads: List[Dict], business_name: str):
    safe_name = "".join([c for c in business_name if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
    folder_path = os.path.join(ARCHIVE_DIR, safe_name)
    os.makedirs(folder_path, exist_ok=True)

    file_path = os.path.join(folder_path, "master_leads.csv")
    if not leads:
        print("⚠️ No reputable official leads found.")
        return

    keys = leads[0].keys()
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(leads)
    print(f"✅ {len(leads)} Official leads anchored in {file_path}")
    return folder_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.exit(1)

    USER_PROMPT = sys.argv[1]
    try:
        leads = discover_leads(USER_PROMPT)
        save_leads_to_folder(leads, USER_PROMPT)
    except Exception as e:
        print(f"❌ Error: {e}")
