# query/engine.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from query.cypher import (
    get_top_concepts, get_top_authors, get_most_similar_papers,
    get_papers_by_concept, get_papers_by_author, get_recent_papers,
    get_graph_stats, get_co_occurring_concepts
)
from query.rag import answer_with_rag

def route_query(question: str):
    """
    Simple keyword router: decide if question needs Cypher or RAG.
    Returns (mode, result_string)
    """
    q = question.lower().strip()

    if q in ("help", "?", "commands"):
        lines = [
            "📖 Example queries:",
            "  graph stats                          — node/edge counts",
            "  top concepts                         — most frequent concepts",
            "  top authors                          — most prolific authors",
            "  show recent papers                   — latest additions",
            "  papers similar to <title/concept>   — semantic neighbours",
            "  papers by <author name>              — all papers by someone",
            "  concepts with <concept name>         — co-occurring concepts",
            "  <anything else>                      — RAG answer from graph",
        ]
        return "cypher", "\n".join(lines)

    # --- Graph structure queries (Cypher) ---
    if any(x in q for x in ["stats", "how many", "total", "graph size", "overview"]):
        stats = get_graph_stats()
        lines = [
            "📊 Graph Statistics",
            f"  Papers:    {stats['papers']}",
            f"  Authors:   {stats['authors']}",
            f"  Concepts:  {stats['concepts']}",
            f"  SIMILAR_TO edges: {stats['similar_to']}",
            f"  CO_OCCURS_WITH:   {stats['co_occurs_with']}",
            f"  SAME_AUTHOR:      {stats['same_author']}",
        ]
        return "cypher", "\n".join(lines)

    elif any(x in q for x in ["top concept", "common concept", "frequent concept", "main concept", "key concept"]):
        results = get_top_concepts(10)
        lines = ["🔑 Top Concepts:"]
        for r in results:
            lines.append(f"  {r['concept']} — {r['count']} papers")
        return "cypher", "\n".join(lines)

    elif any(x in q for x in ["top author", "most author", "prolific", "active researcher", "most papers"]):
        results = get_top_authors(10)
        lines = ["👤 Top Authors:"]
        for r in results:
            lines.append(f"  {r['author']} — {r['count']} papers")
        return "cypher", "\n".join(lines)

    elif any(x in q for x in ["recent", "latest", "newest", "this week", "this month"]):
        results = get_recent_papers(10)
        lines = ["📅 Most Recent Papers:"]
        for r in results:
            lines.append(f"  [{r['published'][:10]}] {r['title']}")
            if r['url']:
                lines.append(f"    {r['url']}")
        return "cypher", "\n".join(lines)

    # Replace the "similar to" block in route_query() in query/engine.py

    elif any(x in q for x in ["similar to", "related to", "like the paper"]):
        for phrase in ["similar to", "related to", "like the paper"]:
            if phrase in q:
                fragment = question[q.index(phrase) + len(phrase):].strip().strip('"\'?')
                break
        results = get_most_similar_papers(fragment, limit=5)
        if not results:
            return "cypher", f"No similar papers found for: '{fragment}'\nTip: try a concept name like 'sparse autoencoders' or an exact title word."
        source = results[0].get("source", fragment)
        lines = [f"🔗 Papers similar to '{source}':"]
        for r in results:
            lines.append(f"  [{r['score']}] {r['title']}")
        return "cypher", "\n".join(lines)

    elif any(x in q for x in ["by author", "papers by", "written by", "published by"]):
        for phrase in ["papers by", "by author", "written by", "published by"]:
            if phrase in q:
                name = question[q.index(phrase) + len(phrase):].strip()
                break
        results = get_papers_by_author(name, limit=8)
        if not results:
            return "cypher", f"No papers found for author: '{name}'"
        lines = [f"📄 Papers by '{name}':"]
        for r in results:
            lines.append(f"  [{r['published'][:10] if r['published'] else '????'}] {r['title']}")
        return "cypher", "\n".join(lines)

    elif any(x in q for x in ["co-occur", "concept related", "concepts with"]):
        # extract concept name
        for phrase in ["concepts with", "co-occur with", "concept related to"]:
            if phrase in q:
                concept = question[q.index(phrase) + len(phrase):].strip()
                break
        else:
            concept = q.split()[-1]
        results = get_co_occurring_concepts(concept, limit=8)
        if not results:
            return "cypher", f"No co-occurring concepts found for: '{concept}'"
        lines = [f"🔀 Concepts co-occurring with '{concept}':"]
        for r in results:
            lines.append(f"  {r['concept']} — {r['count']} co-occurrences")
        return "cypher", "\n".join(lines)

    else:
        # Fall through to RAG for everything else
        answer = answer_with_rag(question)
        return "rag", answer


def main():
    print("=" * 60)
    print("  MI Knowledge Graph — Query Engine")
    print("  Type your question. Type 'quit' to exit.")
    print("=" * 60)
    print()
    print("Example questions:")
    print("  - what are the top concepts?")
    print("  - papers similar to induction heads")
    print("  - what are the open problems in MI?")
    print("  - show recent papers")
    print("  - graph stats")
    print()

    while True:
        try:
            question = input("❓ Your question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        mode, result = route_query(question)
        label = "📊 [Graph Query]" if mode == "cypher" else "🤖 [RAG Answer]"
        print(f"\n{label}\n{result}\n")
        print("-" * 60)


if __name__ == "__main__":
    main()