# Sales Intelligence Engine

Turn a plain-language target (e.g. *"Boutique 4 star hotels in Paris"*) into
**evidence-backed business intelligence tables** you can download as CSV.

The pipeline discovers businesses, captures their public web pages, enriches them
with external reviews, and extracts structured facts with an LLM. Every table is
derived from captured evidence, not from model memory.

## Live demo (Streamlit)

Deploy on [Streamlit Community Cloud](https://share.streamlit.io):

1. Push this repo to GitHub.
2. Create a new app, pick the repo, set **Main file path** to `streamlit_app.py`.
3. Open the app and paste your **Firecrawl** and **NVIDIA** API keys in the sidebar.

Keys are entered per session and are never stored in the repo or on disk.

## How it works

```
planner            NVIDIA NIM refines the target into a search query
   ↓
discovery          Firecrawl search + domain/path filtering, star matching
   ↓
interaction        Firecrawl scrape → 4 evidence files per lead
   ↓
review_enrichment  branch-aware TripAdvisor / Trustpilot / Yelp enrichment
   ↓
extractor          BeautifulSoup text reduction → NVIDIA NIM → normalized JSON
   ↓
validator          writes {Table}_verified.csv
```

Outputs (one folder per batch, `archive/{Batch_Name}/`):

| File | Columns |
| --- | --- |
| `Pricing.csv` | `lead_id, item_name, price, currency, price_category` |
| `Uniqueness.csv` | `lead_id, specialty, unique_selling_point` |
| `Ambience.csv` | `lead_id, interior_style, facilities, atmosphere, view_or_location` |
| `Reviews.csv` | `lead_id, rating, top_complaint, top_praise` |

## Local usage

```bash
pip install -r requirements.txt
cp .env.example .env        # add FIRECRAWL_API_KEY and NVIDIA_API_KEY
streamlit run streamlit_app.py
```

Optional command line (same pipeline, no UI):

```bash
python main.py "Boutique 4 star hotels in Paris" --limit 5
```

`main.py` uses Playwright when installed, otherwise it falls back to Firecrawl:

```bash
pip install playwright
playwright install chromium
```

## Configuration

| Variable | Default |
| --- | --- |
| `FIRECRAWL_API_KEY` | — (required) |
| `NVIDIA_API_KEY` | — (required) |
| `NVIDIA_MODEL` | `meta/llama-3.3-70b-instruct` |
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1/chat/completions` |

## Limitations

- **Dynamic pricing** (fast food, some luxury brands) is often not present in HTML,
  so Pricing rows can be sparse.
- **LLM paraphrase risk**: extracted values are normalized, but the model can
  still misread ambiguous text. Treat output as a research aid and spot-check
  high-value rows.
- **Review coverage** depends on public review sites; blocked or missing pages
  produce honest empty fields rather than guesses.
- Respect target sites' Terms of Service and `robots.txt` when running at scale.

## License

MIT — see [LICENSE](LICENSE).
