import os
import re
import csv
import time
import unicodedata
import sys
from pathlib import Path
from firecrawl import FirecrawlApp

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import load_api_key  # noqa: E402
REVIEW_DOMAINS = ("tripadvisor.", "trustpilot.", "yelp.", "restaurantguru.", "thefork.",
                  "opentable.", "google.", "booking.", "expedia.", "hotels.", "agoda.")


def is_review_source(url: str) -> bool:
    low = url.lower()
    return any(domain in low for domain in REVIEW_DOMAINS)


def field(item, key):
    if isinstance(item, dict):
        return item.get(key) or ""
    return getattr(item, key, "") or ""


GENERIC_TOKENS = {"restaurant", "hotel", "the", "le", "la", "les", "de", "du", "des", "et",
                  "spa", "official", "website", "nos", "restaurants", "france", "sur", "sous"}


def strip_accents(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c))


def clean_name(company_name: str) -> str:
    name = re.sub(r'\|.*$', ' ', company_name)
    name = re.sub(r'\s*[-–]\s*(nos restaurants|kfc france|official website|site officiel).*$', ' ', name, flags=re.I)
    name = re.sub(r'^(restaurant|hôtel|hotel|spa)\s+', ' ', name.strip(), flags=re.I)
    name = re.sub(r'\s+', ' ', name).strip(" -–|")
    return name


def tokens(text: str):
    text = strip_accents(text.lower()).replace("'", "").replace("’", "")
    return [t for t in re.split(r'[^0-9a-z]+', text) if len(t) > 2]


def brand_token(company_name: str) -> str:
    for tok in tokens(clean_name(company_name)):
        if tok not in GENERIC_TOKENS:
            return tok
    return ""


def place_tokens(company_name: str, brand: str):
    return [t for t in tokens(clean_name(company_name)) if t != brand and t not in GENERIC_TOKENS]


def build_query(company_name: str, city: str) -> str:
    name = clean_name(company_name)
    return f'"{name}" {city} avis'


def url_score(url: str, brand: str, places) -> int:
    low = strip_accents(url.lower())
    if brand and brand not in low:
        return -99
    score = 0
    if "tripadvisor" in low:
        score += 5
    if "_review" in low:
        score += 4
    if "showuserreviews" in low:
        score += 2
    if brand and brand in low:
        score += 3
    if any(p in low for p in places):
        score += 2
    if "restaurants-g" in low or "hotels-g" in low or "things_to_do-g" in low:
        score -= 8
    if "hotel_feature" in low or "pictures" in low or "/photos" in low:
        score -= 6
    return score


def extract_city(folder_name: str) -> str:
    match = re.search(r'\bin_([A-Za-zÀ-ÿ\-]+)', folder_name)
    if match:
        return match.group(1).strip("_-")
    return folder_name.split("_")[-1]


def search_web(app: FirecrawlApp, query: str):
    for attempt in range(3):
        try:
            time.sleep(7)
            result = app.search(query, limit=6)
            return getattr(result, "web", None) or (result.get("web") if isinstance(result, dict) else []) or []
        except Exception as e:
            if "Rate Limit" in type(e).__name__ or "Rate Limit" in str(e):
                wait = 35 * (attempt + 1)
                print(f"⏳ Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"❌ Review search error: {type(e).__name__}: {e}")
            return []
    return []


def gather_review_evidence(app: FirecrawlApp, company_name: str, city: str) -> str:
    name = clean_name(company_name)
    brand = brand_token(company_name)
    places = place_tokens(company_name, brand)
    queries = [build_query(company_name, city),
               f"site:tripadvisor.com {name} {city}",
               f"{name} tripadvisor reviews"]

    snippets = []
    candidates = []
    seen = set()
    for query in queries:
        for item in search_web(app, query):
            url = field(item, "url")
            key = url.split("?")[0]
            if not url or key in seen:
                continue
            seen.add(key)
            if not is_review_source(url):
                continue
            title = field(item, "title")
            desc = field(item, "description")
            blob = strip_accents(f"{url} {title} {desc}".lower())
            blob_tokens = set(tokens(f"{url} {title} {desc}"))
            if brand and brand not in blob:
                continue
            if places and not all(p in blob_tokens for p in places):
                continue
            score = url_score(url, brand, places)
            if score > 0:
                candidates.append((score, url))
                if title or desc:
                    snippets.append(f"{title}\n{desc}".strip())
    candidates.sort(reverse=True)

    scraped = ""
    preferred_url = ""
    for _, url in candidates:
        try:
            doc = app.scrape(url, formats=["markdown"], only_main_content=True, timeout=90000)
            markdown = doc.get("markdown") if isinstance(doc, dict) else getattr(doc, "markdown", None)
            if markdown and len(markdown) > 500 and (not brand or brand in markdown.lower()):
                scraped = markdown
                preferred_url = url
                break
        except Exception as e:
            print(f"⚠️  Review scrape failed for {url} ({type(e).__name__})")
            continue

    parts = []
    if scraped:
        parts.append(f"SOURCE: {preferred_url}\n{scraped}")
    if snippets:
        parts.append("SEARCH SNIPPETS:\n" + "\n---\n".join(snippets))
    return "\n\n".join(parts)[:60000]


def main(business_folder: str):
    master_file = os.path.join(business_folder, "master_leads.csv")
    if not os.path.exists(master_file):
        return

    with open(master_file, 'r', encoding='utf-8') as f:
        leads = list(csv.DictReader(f))

    city = extract_city(os.path.basename(os.path.normpath(business_folder)))
    evidence_dir = os.path.join(business_folder, "evidence")
    os.makedirs(evidence_dir, exist_ok=True)

    app = FirecrawlApp(api_key=load_api_key())
    for lead in leads:
        lead_id = lead['lead_id']
        path = os.path.join(evidence_dir, f"{lead_id}_Reviews_external.txt")
        text = gather_review_evidence(app, lead['company_name'], city)
        if not text:
            print(f"⚠️  No review evidence for {lead_id}")
            if os.path.exists(path):
                os.remove(path)
            continue
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"✅ Review evidence for {lead_id}: {len(text)} chars")
        time.sleep(1)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        main(sys.argv[1])
