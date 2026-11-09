import os
import re
import json
import re
import time
from typing import List, Dict
from bs4 import BeautifulSoup

BOILERPLATE_TAGS = ["script", "style", "noscript", "svg", "nav", "header", "footer",
                    "aside", "form", "button", "select", "option"]

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from llm import chat  # noqa: E402

# Table Schema Definition
TABLES = {
    "Pricing": ["item_name", "price", "currency", "price_category"],
    "Uniqueness": ["specialty", "unique_selling_point"],
    "Ambience": ["interior_style", "facilities", "atmosphere", "view_or_location"],
    "Reviews": ["rating", "top_complaint", "top_praise"]
}

# Broadened to cover gyms, spas, wellness and hospitality vocabulary (FR + EN)
SYNONYMS = {
    "Pricing": ["prix", "tarif", "price", "rate", "cost", "coût", "cout", "€", "eur", "usd",
                "fee", "fees", "billing", "amount", "pass", "day pass", "membership",
                "abonnement", "forfait", "formule", "package", "pack", "offer", "deal",
                "admission", "entrée", "entree", "session", "treatment", "soin", "soins",
                "massage", "subscription"],
    "Uniqueness": ["specialty", "spécialité", "specialite", "unique", "signature", "exclusive",
                   "exclusif", "famous", "célèbre", "celebre", "distinctive", "award", "best",
                   "only", "first", "premier", "expert", "renowned", "luxury", "luxe", "premium",
                   "authentic", "authentique", "tradition", "savoir-faire", "ritual", "rituel",
                   "récompense", "recompense"],
    "Ambience": ["décor", "decor", "ambiance", "ambience", "atmosphere", "intérieur", "interieur",
                 "interior", "design", "architecture", "lighting", "lumière", "lumiere", "terrace",
                 "terrasse", "rooftop", "view", "vue", "seating", "lounge", "zen", "calm", "calme",
                 "relax", "détente", "detente", "serene", "cozy", "cosy", "luxurious", "luxueux",
                 "pool", "piscine", "sauna", "hammam", "jacuzzi", "steam", "spa", "wellness",
                 "bien-être", "bien-etre", "treatment room", "cabine", "massage", "candle", "scent",
                 "music", "musique", "facility", "facilities", "equipment", "équipement",
                 "equipement", "studio", "locker", "vestiaire", "shower", "douche", "hydrotherapy"],
    "Reviews": ["rating", "review", "reviews", "complaint", "praise", "stars", "star", "experience",
                "avis", "note", "critique", "testimonial", "témoignage", "temoignage", "feedback",
                "recommended", "recommandé", "recommande", "rated", "satisfaction", "customer",
                "client", "google", "trustpilot"]
}

CURRENCY_MAP = {
    "euro": "EUR", "euros": "EUR", "eur": "EUR", "€": "EUR",
    "dollar": "USD", "dollars": "USD", "usd": "$", "$": "USD",
    "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "£": "GBP"
}


def html_to_text(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(BOILERPLATE_TAGS):
        tag.decompose()

    candidates = []
    for selector in ("main", "article"):
        node = soup.find(selector)
        if node:
            candidates.append(node.get_text(" "))
    candidates.append((soup.body or soup).get_text(" "))

    text = max(candidates, key=len)
    text = html_lib.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def split_sentences(text: str) -> List[str]:
    parts = re.split(r'(?<=[.!?])\s+|\s*[|•·]\s*', text)
    return [p.strip() for p in parts if len(p.strip()) >= 8]


def select_relevant_text(text: str, table_name: str, max_chars: int = 12000) -> str:
    text = re.sub(r'\((?:https?://)[^)]*\)', ' ', text)
    text = re.sub(r'https?://\S+', ' ', text)
    sentences = [s for s in split_sentences(text) if len(s) <= 1200]
    if not sentences:
        return ""

    keywords = SYNONYMS.get(table_name, [])
    scored = []
    for sentence in sentences:
        low = sentence.lower()
        hits = sum(low.count(kw) for kw in keywords)
        if hits:
            scored.append((hits, len(sentence), sentence))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)

    selected: List[str] = []
    total = 0
    for _, _, sentence in scored:
        if sentence in selected:
            continue
        if total + len(sentence) > max_chars:
            continue
        selected.append(sentence)
        total += len(sentence) + 1
        if total >= max_chars * 0.9:
            break

    # Thin-text fallback: rank by length so the LLM still gets substantive prose
    if total < 800:
        for sentence in sorted(sentences, key=len, reverse=True):
            if sentence in selected:
                continue
            if total + len(sentence) > max_chars:
                continue
            selected.append(sentence)
            total += len(sentence) + 1
            if total >= max_chars * 0.9:
                break

    return "\n".join(selected)[:max_chars]


def filter_by_synonyms(html_content: str, table_name: str, max_chars: int = 12000) -> str:
    return select_relevant_text(html_to_text(html_content), table_name, max_chars)


def call_llm(prompt: str) -> str:
    try:
        return chat([{"role": "user", "content": prompt}], model=config.NVIDIA_MODEL).strip()
    except Exception as e:
        print(f"❌ LLM Error: {type(e).__name__}: {e}")
        return ""


def parse_json_response(res: str):
    if not res:
        return None
    clean = res.strip()
    if clean.startswith("```"):
        clean = re.sub(r'^```(?:json)?\s*|```$', '', clean, flags=re.MULTILINE).strip()
    if not clean:
        return None

    data = None
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', clean, flags=re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

    if isinstance(data, list):
        data = data[0] if data else None
    return data if isinstance(data, dict) else None


def normalize_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        items = [normalize_value(v) for v in value]
        return ", ".join(i for i in items if i)
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            norm = normalize_value(v)
            if norm:
                parts.append(f"{k}: {norm}")
        return ", ".join(parts)
    text = str(value).strip()
    if text.lower() in {"unknown", "n/a", "na", "none", "null", "not found", "not available"}:
        return ""
    return text


def normalize_currency(value) -> str:
    text = normalize_value(value)
    if not text:
        return ""
    return CURRENCY_MAP.get(text.lower(), text)


def infer_currency(text: str) -> str:
    low = text.lower()
    if "€" in text or re.search(r'\beur\b', low):
        return "EUR"
    if "£" in text or re.search(r'\bgbp\b', low):
        return "GBP"
    if "$" in text or re.search(r'\busd\b', low):
        return "USD"
    return ""


def build_prompt(fields: List[str], filtered_text: str) -> str:
    return (
        "SYSTEM: You are a precise data extraction analyst. The TEXT is scraped from a "
        "business website and may be in French or English.\n"
        f"Extract values for these keys: {json.dumps(fields)}.\n"
        "Rules:\n"
        "- Only use facts explicitly present in the TEXT.\n"
        '- Use an empty string "" for any key the TEXT does not support.\n'
        "- Return ONLY a valid JSON object. No markdown, no backticks, no commentary.\n\n"
        f"TEXT:\n{filtered_text}"
    )


def run_extraction_pipeline(business_folder: str, only_tables=None):
    master_file = os.path.join(business_folder, "master_leads.csv")
    if not os.path.exists(master_file):
        return

    with open(master_file, 'r', encoding='utf-8') as f:
        leads = list(csv.DictReader(f))

    for table_name, fields in TABLES.items():
        if only_tables and table_name not in only_tables:
            continue
        rows: Dict[str, Dict] = {}
        for lead in leads:
            lead_id = lead['lead_id']
            evidence_path = os.path.join(business_folder, "evidence", f"{lead_id}_{table_name}.txt")
            if not os.path.exists(evidence_path):
                continue

            with open(evidence_path, 'r', encoding='utf-8') as ef:
                raw_html = ef.read()

            if len(raw_html) < 1500 and "Access Denied" in raw_html:
                print(f"⚠️  Skipping {lead_id} {table_name}: bot-blocked evidence")
                continue
            if len(raw_html) < 200:
                print(f"⚠️  Skipping {lead_id} {table_name}: evidence too small")
                continue

            filtered_text = filter_by_synonyms(raw_html, table_name)

            if table_name == "Reviews":
                ext_path = os.path.join(business_folder, "evidence", f"{lead_id}_Reviews_external.txt")
                if os.path.exists(ext_path):
                    with open(ext_path, 'r', encoding='utf-8') as extf:
                        external = select_relevant_text(extf.read(), table_name)
                    if external:
                        filtered_text = (filtered_text + "\n" + external).strip()

            if not filtered_text.strip():
                print(f"⚠️  Skipping {lead_id} {table_name}: no matching text")
                continue

            print(f"🚀 Extracting {lead_id} → {table_name} ({len(filtered_text)} chars)")
            res = call_llm(build_prompt(fields, filtered_text))
            data = parse_json_response(res)
            if data is None:
                print(f"❌ JSON Error for {lead_id} {table_name}")
                continue

            row = {"lead_id": lead_id}
            for field in fields:
                value = normalize_value(data.get(field, ""))
                if field == "currency":
                    value = normalize_currency(value) or infer_currency(filtered_text)
                if table_name == "Reviews" and field == "rating" and value:
                    match = re.search(r'\d+(?:[.,]\d+)?', value)
                    if match:
                        value = match.group(0).replace(',', '.')
                row[field] = value
            rows[lead_id] = row
            time.sleep(0.3)

        csv_path = os.path.join(business_folder, f"{table_name}.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8') as cf:
            writer = csv.DictWriter(cf, fieldnames=["lead_id"] + fields)
            writer.writeheader()
            for row in rows.values():
                writer.writerow(row)
        print(f"✅ {table_name}: {len(rows)}/{len(leads)} rows written")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        tables = sys.argv[2].split(",") if len(sys.argv) > 2 else None
        run_extraction_pipeline(sys.argv[1], tables)
