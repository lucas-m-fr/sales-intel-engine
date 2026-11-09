import os
import asyncio
import csv
from firecrawl import FirecrawlApp

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import load_api_key  # noqa: E402
TABLES = {
    "Pricing": ["item_name", "price", "currency", "price_category"],
    "Uniqueness": ["specialty", "unique_selling_point"],
    "Ambience": ["interior_style", "facilities", "atmosphere", "view_or_location"],
    "Reviews": ["rating", "top_complaint", "top_praise"]
}


def firecrawl_fallback(url: str) -> str:
    try:
        app = FirecrawlApp(api_key=load_api_key())
        doc = app.scrape(url, formats=["html"], only_main_content=False, timeout=60000)
        if isinstance(doc, dict):
            return doc.get("html") or doc.get("raw_html") or ""
        return getattr(doc, "html", None) or getattr(doc, "raw_html", None) or ""
    except Exception as e:
        print(f"❌ Firecrawl fallback error: {type(e).__name__}: {e}")
        return ""


async def capture_page(page, url: str):
    best_content = ""
    last_error = None
    for wait_until, timeout, settle in (("domcontentloaded", 60000, 3000), ("load", 45000, 5000)):
        try:
            await page.goto(url, timeout=timeout, wait_until=wait_until)
            await page.wait_for_timeout(settle)
            content = await page.content()
            if len(content) > len(best_content):
                best_content = content
            if len(content) > 1000:
                return content, None
        except Exception as e:
            last_error = e
    return best_content, last_error


def capture_all_firecrawl(business_folder: str, leads=None):
    """Firecrawl-only capture (used by Streamlit where browsers are unavailable)."""
    if leads is None:
        master_file = os.path.join(business_folder, "master_leads.csv")
        if not os.path.exists(master_file):
            return
        with open(master_file, "r", encoding="utf-8") as f:
            leads = list(csv.DictReader(f))

    evidence_dir = os.path.join(business_folder, "evidence")
    os.makedirs(evidence_dir, exist_ok=True)

    for lead in leads:
        url = lead.get("website_url")
        lead_id = lead["lead_id"]
        if not url:
            continue
        content = firecrawl_fallback(url)
        if len(content) < 1000 or "Access Denied" in content[:2000]:
            print(f"⚠️  Firecrawl thin/blocked for {lead_id}: {len(content)} chars")
            continue
        for table_name in TABLES:
            evidence_path = os.path.join(evidence_dir, f"{lead_id}_{table_name}.txt")
            with open(evidence_path, "w", encoding="utf-8") as ef:
                ef.write(content)
        print(f"✅ Captured {lead_id} ({len(content)} chars) → {len(TABLES)} evidence files")


async def main(business_folder: str):
    master_file = os.path.join(business_folder, "master_leads.csv")
    if not os.path.exists(master_file):
        return

    with open(master_file, 'r', encoding='utf-8') as f:
        leads = list(csv.DictReader(f))

    evidence_dir = os.path.join(business_folder, "evidence")
    os.makedirs(evidence_dir, exist_ok=True)

    current_ids = {lead['lead_id'] for lead in leads}
    for name in os.listdir(evidence_dir):
        if name.endswith(".txt") and name.split("_")[0] not in current_ids:
            os.remove(os.path.join(evidence_dir, name))

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed; using Firecrawl capture.")
        capture_all_firecrawl(business_folder, leads=leads)
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )

        for lead in leads:
            url = lead.get('website_url')
            lead_id = lead['lead_id']
            if not url:
                continue
            try:
                content, error = await capture_page(page, url)
            except Exception as e:
                print(f"❌ Capture Error for {lead_id}: {type(e).__name__}: {e}")
                continue

            if len(content) < 1000 or "Access Denied" in content[:2000]:
                detail = f" ({type(error).__name__}: {error})" if error else ""
                print(f"⚠️  Playwright thin/blocked for {lead_id}: {len(content)} chars{detail}; trying Firecrawl...")
                fallback = firecrawl_fallback(url)
                if len(fallback) > len(content) and "Access Denied" not in fallback[:2000]:
                    content = fallback
                    print(f"↩️  Firecrawl recovered {lead_id}: {len(content)} chars")
                elif not content:
                    continue

            for table_name in TABLES:
                evidence_path = os.path.join(evidence_dir, f"{lead_id}_{table_name}.txt")
                with open(evidence_path, 'w', encoding='utf-8') as ef:
                    ef.write(content)
            print(f"✅ Captured {lead_id} ({len(content)} chars) → {len(TABLES)} evidence files")

        await browser.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        asyncio.run(main(sys.argv[1]))
