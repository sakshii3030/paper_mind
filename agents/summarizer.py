import json
import os
import re
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

def get_client():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY not found in environment")
    return Groq(api_key=key)

def _clean_json(raw: str) -> str:
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    # Strip control characters that break JSON parsing (keep \n \r \t)
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw)
    # Fix invalid escape sequences like \l, \p, etc.
    raw = re.sub(r'\\([^"\\/bfnrtu])', r'\1', raw)
    return raw.strip()

def _parse_rate_limit_wait(error_msg: str) -> float:
    """Extract wait seconds from a Groq 429 error message."""
    match = re.search(r'try again in (\d+)m([\d.]+)s', str(error_msg))
    if match:
        return int(match.group(1)) * 60 + float(match.group(2))
    match = re.search(r'try again in ([\d.]+)s', str(error_msg))
    if match:
        return float(match.group(1))
    return 60.0

def summarize_paper(paper: dict, retries: int = 2) -> dict:
    """Use LLM to summarize a paper and extract concepts."""

    prompt = f"""You are analyzing a mechanistic interpretability research paper.

Title: {paper['title']}
Abstract: {paper['abstract']}

Respond in JSON only, no extra text, no markdown:
{{
    "summary": "3 sentence summary of what this paper does and why it matters for MI",
    "concepts": ["concept1", "concept2", "concept3", "concept4", "concept5"],
    "methods": ["method1", "method2"],
    "contribution": "one sentence on the key contribution"
}}"""

    for attempt in range(retries + 1):
        try:
            client = get_client()
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )

            raw = response.choices[0].message.content.strip()
            raw = _clean_json(raw)
            result = json.loads(raw)
            paper["summary"] = result.get("summary", "")
            paper["concepts"] = result.get("concepts", [])
            paper["methods"] = result.get("methods", [])
            paper["contribution"] = result.get("contribution", "")
            paper["processed"] = True
            return paper

        except Exception as e:
            err = str(e)
            if "429" in err and attempt < retries:
                wait = _parse_rate_limit_wait(err)
                print(f"    Rate limit hit — waiting {wait:.0f}s before retry...")
                time.sleep(wait + 2)
                continue
            print(f"    Error: {e}")
            break

    paper["summary"] = ""
    paper["concepts"] = []
    paper["methods"] = []
    paper["contribution"] = ""
    paper["processed"] = False
    return paper


def summarize_all(papers: list, delay: float = 2.0) -> list:
    """Summarize all papers with delay to respect rate limits."""
    processed = []
    total = len(papers)

    for i, paper in enumerate(papers):
        print(f"  [{i+1}/{total}] {paper['title'][:65]}...")
        paper = summarize_paper(paper)
        if paper["processed"]:
            print(f"         concepts: {', '.join(paper['concepts'][:3])}")
        processed.append(paper)
        time.sleep(delay)

    return processed