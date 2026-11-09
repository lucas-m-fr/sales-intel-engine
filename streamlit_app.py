import contextlib
import io
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from src import extractor, interaction, review_enrichment, validator
from src.discovery import discover_leads, save_leads_to_folder
from src.planner import plan_search_strategy

st.set_page_config(page_title="Sales Intelligence Engine", page_icon="🔎", layout="wide")
st.title("Sales Intelligence Engine")
st.caption("Turn a target into evidence-backed business intelligence tables.")

with st.sidebar:
    st.header("Credentials")
    firecrawl_key = st.text_input("Firecrawl API key", type="password")
    nvidia_key = st.text_input("NVIDIA API key", type="password")
    model = st.text_input("NVIDIA model", value="meta/llama-3.3-70b-instruct")
    limit = st.slider("Number of leads", 1, 10, 5)

target = st.text_input("Target", placeholder="e.g. Boutique 4 star hotels in Paris")
run = st.button("Run pipeline", type="primary")

if run:
    if not target or not firecrawl_key or not nvidia_key:
        st.error("Enter a target, a Firecrawl key, and an NVIDIA key.")
        st.stop()

    config.configure(
        firecrawl_api_key=firecrawl_key,
        nvidia_api_key=nvidia_key,
        nvidia_model=model,
    )

    log = io.StringIO()
    folder = None
    with st.status("Running pipeline...", expanded=True) as status:
        try:
            with contextlib.redirect_stdout(log):
                strategy = plan_search_strategy(target)
                query = strategy.get("refined_query", target)
                st.write(f"Refined query: {query}")
                leads = discover_leads(query, limit=limit)
                if not leads:
                    st.error("No leads found. Try a more specific target.")
                    st.stop()
                folder = save_leads_to_folder(leads, target)
                st.write(f"Leads: {len(leads)}")
                interaction.capture_all_firecrawl(folder)
                review_enrichment.main(folder)
                extractor.run_extraction_pipeline(folder)
                for table in extractor.TABLES:
                    validator.validate_table(folder, table)
            status.update(label="Done", state="complete")
        except Exception as exc:
            status.update(label="Failed", state="error")
            st.exception(exc)

    if folder:
        st.subheader("Results")
        for name in ("Pricing", "Uniqueness", "Ambience", "Reviews"):
            path = os.path.join(folder, f"{name}.csv")
            if not os.path.exists(path):
                continue
            df = pd.read_csv(path)
            st.markdown(f"**{name}**")
            st.dataframe(df, use_container_width=True)
            st.download_button(
                f"Download {name}.csv",
                df.to_csv(index=False).encode("utf-8"),
                file_name=f"{name}.csv",
                mime="text/csv",
            )
        with st.expander("Run log"):
            st.text(log.getvalue())
