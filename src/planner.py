import os
import re
import json
from typing import Dict, Any


def parse_json_object(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r'^```(?:json)?\s*|```$', '', clean, flags=re.MULTILINE).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', clean, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from llm import chat  # noqa: E402

def plan_search_strategy(user_prompt: str) -> Dict[str, Any]:
    """
    Analyzes the user prompt and generates a refined search strategy
    to ensure high-quality, official business leads.
    """
    system_prompt = (
        "You are a Strategic Lead Generation Planner. Your goal is to transform a vague user request "
        "into a pinpoint search strategy for Firecrawl. \n\n"
        "RULES:\n"
        "1. Identify the core Industry, Geography, and Target Entity.\n"
        "2. Create a 'Refined Query' that forces search engines to find OFFICIAL business websites.\n"
        "3. Define 'Negative Constraints' (what to exclude, e.g., blogs, directories, job boards).\n"
        "4. Output ONLY a JSON object.\n\n"
        "EXAMPLE:\n"
        "User: 'Cinemas in Paris'\n"
        "Output: {\n"
        "  'refined_query': 'official websites of movie theaters and cinemas in Paris, France',\n"
        "  'constraints': 'exclude yelp, tripadvisor, blogs, tourism guides, news articles',\n"
        "  'industry': 'Cinema/Entertainment',\n"
        "  'geography': 'Paris, France'\n"
        "}"
    )

    prompt = f"{system_prompt}\n\nUser Prompt: {user_prompt}"

    try:
        text = chat([{"role": "user", "content": prompt}], model=config.NVIDIA_MODEL)
        return parse_json_object(text)
    except Exception as e:
        print(f"❌ Planner Error: {e}")
        # Fallback to basic refinement if AI fails
        return {
            "refined_query": f"{user_prompt} official website",
            "constraints": "exclude directories",
            "industry": "Unknown",
            "geography": "Unknown"
        }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        user_input = sys.argv[1]
        strategy = plan_search_strategy(user_input)
        print(json.dumps(strategy, indent=2))
