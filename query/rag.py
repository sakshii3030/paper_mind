# query/rag.py
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from groq import Groq
from sentence_transformers import SentenceTransformer
from graph.connector import get_driver
import numpy as np

_model = None
_client = None

def get_model():
    global _model
    if _model is None:
        print("Loading embedding model...")
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model

def get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client

def fetch_all_summaries():
    """Pull all paper titles + summaries from Neo4j."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Paper)
            WHERE p.summary IS NOT NULL
            RETURN p.title AS title, p.summary AS summary, 
                   p.published AS published, p.url AS url
        """)
        return [{"title": r["title"], "summary": r["summary"],
                 "published": r["published"], "url": r["url"]} for r in result]

def semantic_search(query, top_k=6):
    """Embed query and find most relevant papers by cosine similarity."""
    model = get_model()
    papers = fetch_all_summaries()
    if not papers:
        return []

    query_vec = model.encode(query, normalize_embeddings=True)
    corpus = [f"{p['title']}. {p['summary']}" for p in papers]
    corpus_vecs = model.encode(corpus, normalize_embeddings=True, show_progress_bar=False)

    scores = np.dot(corpus_vecs, query_vec)
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for i in top_indices:
        results.append({**papers[i], "score": round(float(scores[i]), 3)})
    return results

def answer_with_rag(question):
    """Full RAG pipeline: retrieve relevant papers → LLM → natural language answer.
    Returns (answer_text, sources) where sources is a list of dicts with title/url/published."""
    print(f"\nSearching graph for: '{question}'")
    relevant = semantic_search(question, top_k=6)

    if not relevant:
        return "No papers found in the graph to answer this question.", []

    context_parts = []
    for i, p in enumerate(relevant, 1):
        context_parts.append(
            f"[{i}] Title: {p['title']}\n"
            f"    Published: {p.get('published', 'unknown')}\n"
            f"    Summary: {p['summary']}"
        )
    context = "\n\n".join(context_parts)

    prompt = f"""You are an expert research assistant for mechanistic interpretability (MI) and AI research.

Based on the following research papers retrieved from a knowledge graph, answer the user's question.
Be specific, cite paper titles when relevant, and synthesize insights across papers.
If the papers don't contain enough information, say so clearly.

RETRIEVED PAPERS:
{context}

USER QUESTION: {question}

Answer:"""

    client = get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=800
    )
    answer = response.choices[0].message.content.strip()
    sources = [{"title": p["title"], "url": p.get("url", ""), "published": p.get("published", "")}
               for p in relevant]
    return answer, sources