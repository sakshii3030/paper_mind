# app.py
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

import csv
import html as _html
import io
import json
import tempfile
import concurrent.futures
from datetime import datetime
import arxiv
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from query.cypher import (
    get_graph_stats, get_top_concepts, get_top_authors,
    get_recent_papers,
    get_papers_by_author,
    get_papers_by_concept,
)
from query.rag import answer_with_rag
from graph.writer import write_papers_to_graph
from graph.connector import get_driver

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="PaperMind", page_icon="🔬", layout="wide")

TOPICS_PATH       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "topics.json")
SENTINEL_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sentinel_log.json")

# ── Theme + CSS ────────────────────────────────────────────────────────────────
st.html("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
  .stApp { background-color: #07071200; }
  .block-container { padding-top: 1.5rem; max-width: 1200px; }

  .stButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.15s ease !important;
  }
  .stButton > button[kind="primary"] {
    background: #7c6af7 !important;
    border: none !important;
    color: white !important;
  }
  .stButton > button[kind="primary"]:hover {
    background: #6a5be3 !important;
    box-shadow: 0 4px 14px rgba(124,106,247,0.35) !important;
  }
  .stDownloadButton > button {
    border-radius: 8px !important;
    font-size: 0.82rem !important;
    font-family: 'Inter', sans-serif !important;
  }

  .stTextInput > div > div > input,
  .stTextArea > div > div > textarea {
    background: #11111e !important;
    border: 1px solid #2a2a45 !important;
    border-radius: 8px !important;
    color: #e0e0ff !important;
    font-family: 'Inter', sans-serif !important;
  }
  .stTextInput > div > div > input:focus,
  .stTextArea > div > div > textarea:focus {
    border-color: #7c6af7 !important;
    box-shadow: 0 0 0 2px rgba(124,106,247,0.15) !important;
  }

  .stTabs [data-baseweb="tab-list"] {
    background: #11111e;
    border-radius: 10px;
    padding: 4px;
    gap: 2px;
    border: 1px solid #2a2a45;
  }
  .stTabs [data-baseweb="tab"] {
    border-radius: 7px !important;
    color: #555 !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    padding: 8px 18px !important;
  }
  .stTabs [aria-selected="true"] {
    background: #7c6af7 !important;
    color: white !important;
  }

  [data-testid="metric-container"] {
    background: #11111e;
    border: 1px solid #2a2a45;
    border-radius: 12px;
    padding: 1rem;
  }
  [data-testid="metric-container"] [data-testid="metric-value"] {
    color: #7c6af7 !important;
    font-weight: 700 !important;
  }
  [data-testid="metric-container"] label {
    color: #555 !important;
    font-size: 0.72rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  hr { border-color: #2a2a45 !important; }
  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #2a2a45; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #7c6af7; }

  .section-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: #7c6af7;
    margin-bottom: 0.9rem;
  }
  .row-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 0;
    border-bottom: 1px solid #1e1e2e;
    font-size: 0.84rem;
    color: #ccc;
  }
  .row-item:last-child { border-bottom: none; }
  .accent { color: #7c6af7; font-weight: 500; }

  .paper-card {
    background: #11111e;
    border: 1px solid #2a2a45;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 10px;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .paper-card:hover {
    border-color: #7c6af7;
    box-shadow: 0 0 0 1px rgba(124,106,247,0.15);
  }
  .paper-card-title a {
    font-size: 0.93rem;
    font-weight: 600;
    color: #e0e0ff;
    text-decoration: none;
    line-height: 1.45;
  }
  .paper-card-title a:hover { color: #9b8fff; }
  .paper-card-title span {
    font-size: 0.93rem;
    font-weight: 600;
    color: #e0e0ff;
    line-height: 1.45;
  }
  .paper-card-meta { font-size: 0.76rem; color: #555; margin: 4px 0 8px; }
  .paper-card-summary {
    font-size: 0.84rem;
    color: #aaa;
    line-height: 1.6;
    margin-bottom: 10px;
  }
  .arxiv-link {
    font-size: 0.78rem;
    color: #7c6af7;
    text-decoration: none;
    font-weight: 500;
  }
  .arxiv-link:hover { color: #9b8fff; text-decoration: underline; }

  .answer-box {
    background: #11111e;
    border: 1px solid #2a2a45;
    border-left: 3px solid #7c6af7;
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    font-size: 0.9rem;
    line-height: 1.7;
    color: #ddd;
    white-space: pre-wrap;
    margin-bottom: 1rem;
  }
  .source-box {
    background: #0e0e1c;
    border: 1px solid #2a2a45;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    margin-bottom: 1rem;
  }
  .source-row {
    display: flex;
    align-items: baseline;
    gap: 10px;
    padding: 5px 0;
    border-bottom: 1px solid #1a1a2e;
    font-size: 0.82rem;
  }
  .source-row:last-child { border-bottom: none; }
  .source-num { color: #7c6af7; font-weight: 700; min-width: 16px; }
  .source-title { color: #ccc; flex: 1; }
  .source-title a { color: #9b8fff; text-decoration: none; }
  .source-title a:hover { text-decoration: underline; }
  .source-date { color: #555; font-size: 0.75rem; white-space: nowrap; }

  .empty-state { text-align: center; padding: 3rem 2rem; }
  .empty-icon { font-size: 2.2rem; margin-bottom: 0.5rem; }
  .empty-title { font-size: 0.95rem; font-weight: 600; color: #666; margin-bottom: 0.3rem; }
  .empty-hint { font-size: 0.82rem; color: #444; }

  .cypher-preset {
    background: #11111e;
    border: 1px solid #2a2a45;
    border-radius: 8px;
    padding: 0.6rem 0.9rem;
    margin-bottom: 6px;
    font-size: 0.8rem;
    color: #aaa;
    cursor: pointer;
  }
  .graph-legend {
    display: flex;
    gap: 16px;
    font-size: 0.78rem;
    color: #888;
    margin-top: 8px;
  }
  .legend-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 5px;
  }
</style>
""")


# ── Helpers ────────────────────────────────────────────────────────────────────
def paper_card(p, show_summary=True):
    title   = _html.escape(p.get("title") or "Untitled")
    url     = p.get("url") or ""
    pub     = (p.get("published") or "")[:10]
    summary = p.get("summary") or ""
    t_html  = (f'<a href="{url}" target="_blank">{title}</a>' if url else f'<span>{title}</span>')
    s_html  = (f'<div class="paper-card-summary">{_html.escape(summary[:300])}{"…" if len(summary) > 300 else ""}</div>'
               if show_summary and summary else "")
    l_html  = (f'<a href="{url}" target="_blank" class="arxiv-link">View on arXiv ↗</a>' if url else "")
    st.markdown(f"""
    <div class="paper-card">
      <div class="paper-card-title">{t_html}</div>
      <div class="paper-card-meta">{pub}</div>
      {s_html}
      {l_html}
    </div>""", unsafe_allow_html=True)


def empty_state(icon, title, hint=""):
    hint_html = f'<div class="empty-hint">{hint}</div>' if hint else ""
    st.markdown(f"""
    <div class="empty-state">
      <div class="empty-icon">{icon}</div>
      <div class="empty-title">{title}</div>
      {hint_html}
    </div>""", unsafe_allow_html=True)


def load_topics():
    with open(TOPICS_PATH) as f:
        return json.load(f)


def save_topics(topics):
    with open(TOPICS_PATH, "w") as f:
        json.dump(topics, f, indent=2)


def papers_to_csv(papers):
    out = io.StringIO()
    fields = ["title", "published", "url", "summary"]
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(papers)
    return out.getvalue()


def get_sentinel_status():
    if not os.path.exists(SENTINEL_LOG_PATH):
        return None
    try:
        with open(SENTINEL_LOG_PATH) as f:
            log = json.load(f)
        return log[-1] if log else None
    except Exception:
        return None


def run_cypher_query(query: str):
    """Execute a Cypher query and return (records, error)."""
    driver = get_driver()
    try:
        with driver.session() as session:
            result = session.run(query)
            records = []
            for record in result:
                row = {}
                for key, val in record.items():
                    if isinstance(val, list):
                        row[key] = ", ".join(str(v) for v in val)
                    else:
                        row[key] = val
                records.append(row)
            return records, None
    except Exception as e:
        return None, str(e)
    finally:
        driver.close()


# ── Header ─────────────────────────────────────────────────────────────────────
stats     = get_graph_stats()
topics    = load_topics()
last_run  = get_sentinel_status()

st.markdown("## 🔬 PaperMind")

if last_run:
    last_ts    = datetime.fromisoformat(last_run["timestamp"])
    hours_ago  = (datetime.now() - last_ts).total_seconds() / 3600
    indicator  = "🟢" if hours_ago < 26 else "🔴"
    sync_text  = f"{hours_ago:.0f}h ago · +{last_run['papers_added']} papers added"
    st.caption(f"Autonomous research knowledge graph · {indicator} Last sentinel run: {sync_text}")
else:
    st.caption("Autonomous research knowledge graph · auto-updates every 24 h across all tracked topics")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Papers",           stats["papers"])
c2.metric("Authors",          stats["authors"])
c3.metric("Concepts",         stats["concepts"])
c4.metric("Similarity edges", stats["similar_to"])
c5.metric("Co-occur edges",   stats["co_occurs_with"])
c6.metric("Tracked topics",   len(topics))

st.divider()

# ── Session state ──────────────────────────────────────────────────────────────
for k in ["asked_question", "search_concept", "search_author", "cypher_query"]:
    if k not in st.session_state:
        st.session_state[k] = None

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["🔍 Ask", "🔗 Explore", "🕸 Graph", "⚡ Query", "➕ Manage"]
)

# ═══════════════════════════════════════════════
# TAB 1 — Ask
# ═══════════════════════════════════════════════
with tab1:
    st.markdown("#### Ask anything about your research graph")
    st.caption("Answers are grounded in papers already in the graph.")

    question = st.text_area(
        "q",
        placeholder=(
            "Which papers oppose the idea of superposition?\n"
            "What methods are used to study attention heads?\n"
            "What are the open problems in mechanistic interpretability?"
        ),
        height=110,
        label_visibility="collapsed",
    )
    if st.button("Ask ↗", use_container_width=True, type="primary"):
        if question.strip():
            st.session_state["asked_question"] = question.strip()

    if st.session_state.get("asked_question"):
        with st.spinner("Searching graph · generating answer..."):
            answer, sources = answer_with_rag(st.session_state["asked_question"])

        st.markdown("---")
        st.markdown("**Answer**")
        st.markdown(
            f'<div class="answer-box">{_html.escape(answer)}</div>',
            unsafe_allow_html=True,
        )

        if sources:
            st.markdown("**Sources**")
            rows_html = ""
            for i, s in enumerate(sources, 1):
                t      = _html.escape(s["title"])
                url    = s.get("url", "")
                pub    = (s.get("published") or "")[:10]
                t_html = f'<a href="{url}" target="_blank">{t}</a>' if url else t
                rows_html += f"""
                <div class="source-row">
                  <span class="source-num">{i}</span>
                  <span class="source-title">{t_html}</span>
                  <span class="source-date">{pub}</span>
                </div>"""
            st.markdown(
                f'<div class="source-box">{rows_html}</div>',
                unsafe_allow_html=True,
            )

# ═══════════════════════════════════════════════
# TAB 2 — Explore
# ═══════════════════════════════════════════════
with tab2:
    # ── Quick stats ──────────────────────────────
    ex1, ex2 = st.columns(2)
    with ex1:
        st.markdown('<div class="section-label">Top Concepts</div>', unsafe_allow_html=True)
        for c in get_top_concepts(10):
            st.markdown(f"""
            <div class="row-item">
              <span>{_html.escape(c['concept'])}</span>
              <span class="accent">{c['count']}</span>
            </div>""", unsafe_allow_html=True)

    with ex2:
        st.markdown('<div class="section-label">Top Authors</div>', unsafe_allow_html=True)
        for a in get_top_authors(10):
            st.markdown(f"""
            <div class="row-item">
              <span>{_html.escape(a['author'])}</span>
              <span class="accent">{a['count']}</span>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Search ───────────────────────────────────
    s1, s2 = st.columns(2)

    with s1:
        st.markdown("**Find papers by concept**")
        concept_input = st.text_input(
            "Concept name:", placeholder="e.g. sparse autoencoders", key="ci"
        )
        if st.button("Search concept", use_container_width=True):
            st.session_state["search_concept"] = concept_input.strip()

        if st.session_state.get("search_concept"):
            results = get_papers_by_concept(st.session_state["search_concept"], limit=10)
            if results:
                st.caption(f"{len(results)} papers found")
                st.download_button(
                    "⬇ Export CSV",
                    data=papers_to_csv(results),
                    file_name=f"papers_{st.session_state['search_concept'].replace(' ', '_')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
                for p in results:
                    paper_card(p)
            else:
                empty_state(
                    "🔭",
                    f"No papers for '{st.session_state['search_concept']}'",
                    "Try a broader term like 'attention' or 'features'.",
                )

    with s2:
        st.markdown("**Find papers by author**")
        author_input = st.text_input(
            "Author name:", placeholder="e.g. Elhage", key="ai"
        )
        if st.button("Search author", use_container_width=True):
            st.session_state["search_author"] = author_input.strip()

        if st.session_state.get("search_author"):
            results = get_papers_by_author(st.session_state["search_author"], limit=10)
            if results:
                st.caption(f"{len(results)} papers found")
                for p in results:
                    paper_card(p, show_summary=False)
            else:
                empty_state(
                    "👤",
                    f"No papers for '{st.session_state['search_author']}'",
                    "Try a partial last name.",
                )

    st.markdown("---")
    st.markdown('<div class="section-label">Recent Papers</div>', unsafe_allow_html=True)
    recent = get_recent_papers(15)
    if recent:
        for p in recent:
            paper_card(p, show_summary=False)
    else:
        empty_state("📭", "No papers in the graph yet", "Add papers via the Manage tab.")

# ═══════════════════════════════════════════════
# TAB 3 — Graph
# ═══════════════════════════════════════════════
with tab3:
    st.markdown("#### Interactive Knowledge Graph")

    graph_mode = st.selectbox(
        "Visualization mode",
        [
            "Paper → Concept  (papers linked to their concepts)",
            "Paper Similarity  (papers linked by semantic similarity)",
            "Concept Co-occurrence  (concepts that appear together)",
        ],
        index=0,
    )

    mode_key = graph_mode.split("(")[0].strip()

    if mode_key == "Paper → Concept":
        st.caption("Purple = papers · Blue = concepts · Node size = number of connections")
    elif mode_key == "Paper Similarity":
        st.caption("Purple = papers · Edge thickness = similarity score · Requires linker to have been run")
    else:
        st.caption("Blue = concepts · Edge thickness = co-occurrence count · Requires linker to have been run")

    try:
        from pyvis.network import Network

        if st.button("Load graph", type="primary", use_container_width=True):
            with st.spinner("Building graph visualization…"):
                driver = get_driver()

                net = Network(
                    height="660px", width="100%",
                    bgcolor="#07071a", font_color="#cccccc",
                    directed=False,
                )
                net.set_options("""{
                  "physics": {
                    "stabilization": {"iterations": 150},
                    "barnesHut": {"gravitationalConstant": -8000, "springLength": 120}
                  },
                  "nodes": {"font": {"size": 11}},
                  "edges": {"smooth": {"type": "continuous"}}
                }""")

                papers_seen   = set()
                concepts_seen = set()
                edge_count    = 0

                with driver.session() as session:

                    if mode_key == "Paper → Concept":
                        rows = list(session.run("""
                            MATCH (p:Paper)-[:HAS_CONCEPT]->(c:Concept)
                            RETURN p.title AS paper, p.url AS url, c.name AS concept
                            LIMIT 500
                        """))
                        paper_degree   = {}
                        concept_degree = {}
                        for row in rows:
                            paper_degree[row["paper"]]     = paper_degree.get(row["paper"], 0) + 1
                            concept_degree[row["concept"]] = concept_degree.get(row["concept"], 0) + 1

                        for row in rows:
                            pk = row["paper"]
                            ck = row["concept"]
                            if pk not in papers_seen:
                                size  = max(12, min(40, 10 + paper_degree[pk] * 2))
                                label = pk[:40] + ("…" if len(pk) > 40 else "")
                                net.add_node(pk, label=label, color="#7c6af7",
                                             size=size, shape="dot", title=f"{pk}\n{paper_degree[pk]} concepts")
                                papers_seen.add(pk)
                            if ck not in concepts_seen:
                                size = max(8, min(30, 6 + concept_degree[ck] * 3))
                                net.add_node(ck, label=ck, color="#2d9cdb",
                                             size=size, shape="dot", title=f"{ck}\n{concept_degree[ck]} papers")
                                concepts_seen.add(ck)
                            net.add_edge(pk, ck, color="#2a2a45", width=0.8)
                            edge_count += 1

                        summary = f"{len(papers_seen)} papers · {len(concepts_seen)} concepts · {edge_count} edges"

                    elif mode_key == "Paper Similarity":
                        rows = list(session.run("""
                            MATCH (p1:Paper)-[r:SIMILAR_TO]->(p2:Paper)
                            WHERE r.score >= 0.65
                            RETURN p1.title AS paper1, p2.title AS paper2, r.score AS score
                            LIMIT 400
                        """))
                        if not rows:
                            st.warning("No SIMILAR_TO edges found. Run `python agents/linker.py` first.")
                            st.stop()

                        degree = {}
                        for row in rows:
                            degree[row["paper1"]] = degree.get(row["paper1"], 0) + 1
                            degree[row["paper2"]] = degree.get(row["paper2"], 0) + 1

                        for row in rows:
                            for pk in [row["paper1"], row["paper2"]]:
                                if pk not in papers_seen:
                                    size  = max(10, min(35, 8 + degree[pk] * 3))
                                    label = pk[:40] + ("…" if len(pk) > 40 else "")
                                    net.add_node(pk, label=label, color="#7c6af7",
                                                 size=size, shape="dot",
                                                 title=f"{pk}\n{degree[pk]} similar papers")
                                    papers_seen.add(pk)
                            width = max(0.5, round(row["score"] * 4, 1))
                            net.add_edge(row["paper1"], row["paper2"],
                                         color="#a78bfa", width=width,
                                         title=f"score: {row['score']:.3f}")
                            edge_count += 1

                        summary = f"{len(papers_seen)} papers · {edge_count} similarity edges (score ≥ 0.65)"

                    else:  # Concept Co-occurrence
                        rows = list(session.run("""
                            MATCH (c1:Concept)-[r:CO_OCCURS_WITH]->(c2:Concept)
                            WHERE r.count >= 2
                            RETURN c1.name AS c1, c2.name AS c2, r.count AS count
                            ORDER BY count DESC
                            LIMIT 300
                        """))
                        if not rows:
                            st.warning("No CO_OCCURS_WITH edges found. Run `python agents/linker.py` first.")
                            st.stop()

                        degree = {}
                        for row in rows:
                            degree[row["c1"]] = degree.get(row["c1"], 0) + row["count"]
                            degree[row["c2"]] = degree.get(row["c2"], 0) + row["count"]

                        for row in rows:
                            for ck in [row["c1"], row["c2"]]:
                                if ck not in concepts_seen:
                                    size = max(8, min(40, 6 + degree[ck]))
                                    net.add_node(ck, label=ck, color="#2d9cdb",
                                                 size=size, shape="dot",
                                                 title=f"{ck}\nco-occurrence weight: {degree[ck]}")
                                    concepts_seen.add(ck)
                            width = max(0.5, min(6, row["count"] * 0.8))
                            net.add_edge(row["c1"], row["c2"],
                                         color="#38bdf8", width=width,
                                         title=f"co-occurs in {row['count']} papers")
                            edge_count += 1

                        summary = f"{len(concepts_seen)} concepts · {edge_count} co-occurrence edges"

                with tempfile.NamedTemporaryFile(
                    suffix=".html", delete=False, mode="w", encoding="utf-8"
                ) as tmp:
                    net.save_graph(tmp.name)
                    tmp_path = tmp.name

                with open(tmp_path, "r", encoding="utf-8") as f:
                    graph_html = f.read()
                os.unlink(tmp_path)

            st.success(summary)
            components.html(graph_html, height=680, scrolling=False)

    except ImportError:
        st.info("Install pyvis to enable graph visualization:\n```\npip install pyvis\n```")
    except Exception as e:
        st.error(f"Graph error: {e}")

# ═══════════════════════════════════════════════
# TAB 4 — Query
# ═══════════════════════════════════════════════
with tab4:
    st.markdown("#### Cypher Query Editor")
    st.caption("Run any Cypher query directly against your Neo4j graph. Results appear as a table.")

    PRESETS = {
        "Papers with most concepts": (
            "MATCH (p:Paper)-[:HAS_CONCEPT]->(c:Concept)\n"
            "RETURN p.title AS paper, count(c) AS concept_count\n"
            "ORDER BY concept_count DESC\n"
            "LIMIT 15"
        ),
        "Top concept pairs (co-occurrence)": (
            "MATCH (c1:Concept)-[r:CO_OCCURS_WITH]->(c2:Concept)\n"
            "RETURN c1.name AS concept_1, c2.name AS concept_2, r.count AS shared_papers\n"
            "ORDER BY shared_papers DESC\n"
            "LIMIT 20"
        ),
        "Most similar paper pairs": (
            "MATCH (p1:Paper)-[r:SIMILAR_TO]->(p2:Paper)\n"
            "RETURN p1.title AS paper_1, p2.title AS paper_2, round(r.score, 3) AS score\n"
            "ORDER BY score DESC\n"
            "LIMIT 15"
        ),
        "Most prolific authors with paper titles": (
            "MATCH (a:Author)-[:AUTHORED]->(p:Paper)\n"
            "WITH a, collect(p.title)[..3] AS sample_papers, count(p) AS total\n"
            "RETURN a.name AS author, total, sample_papers\n"
            "ORDER BY total DESC\n"
            "LIMIT 10"
        ),
        "Papers sharing concepts with a specific paper": (
            "MATCH (p1:Paper {title: 'Toy Models of Superposition'})-[:HAS_CONCEPT]->(c:Concept)<-[:HAS_CONCEPT]-(p2:Paper)\n"
            "WHERE p1 <> p2\n"
            "RETURN p2.title AS related_paper, collect(c.name) AS shared_concepts, count(c) AS overlap\n"
            "ORDER BY overlap DESC\n"
            "LIMIT 10"
        ),
        "Graph node & edge counts": (
            "MATCH (n) RETURN labels(n)[0] AS type, count(n) AS count\n"
            "UNION ALL\n"
            "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count\n"
            "ORDER BY count DESC"
        ),
        "Papers published per year": (
            "MATCH (p:Paper)\n"
            "WHERE p.year IS NOT NULL\n"
            "RETURN p.year AS year, count(p) AS papers\n"
            "ORDER BY year DESC"
        ),
    }

    st.markdown("**Preset queries — click to load:**")
    preset_cols = st.columns(3)
    for i, name in enumerate(PRESETS):
        if preset_cols[i % 3].button(name, use_container_width=True, key=f"preset_{i}"):
            st.session_state["cypher_query"] = PRESETS[name]

    st.markdown("---")

    default_q = st.session_state.get("cypher_query") or "MATCH (n) RETURN labels(n)[0] AS type, count(n) AS count ORDER BY count DESC"
    query_input = st.text_area(
        "Cypher query:",
        value=default_q,
        height=130,
        key="cypher_input",
    )

    run_col, clear_col = st.columns([5, 1])
    run_btn   = run_col.button("Run query ▶", use_container_width=True, type="primary")
    clear_btn = clear_col.button("Clear", use_container_width=True)

    if clear_btn:
        st.session_state["cypher_query"] = None
        st.rerun()

    if run_btn and query_input.strip():
        with st.spinner("Running query…"):
            records, error = run_cypher_query(query_input.strip())

        if error:
            st.error(f"Query error: {error}")
        elif not records:
            st.info("Query returned no results.")
        else:
            st.success(f"{len(records)} rows returned")
            df = pd.DataFrame(records)
            st.dataframe(df, use_container_width=True)
            csv_data = df.to_csv(index=False)
            st.download_button(
                "⬇ Export CSV",
                data=csv_data,
                file_name="query_results.csv",
                mime="text/csv",
            )

    st.markdown("---")
    with st.expander("Cypher quick reference"):
        st.markdown("""
**Basic patterns**
```cypher
MATCH (n)                          -- all nodes
MATCH (p:Paper)                    -- nodes with label Paper
MATCH (a:Author)-[:AUTHORED]->(p)  -- relationship pattern
WHERE p.published > '2026-01-01'   -- filter
RETURN p.title, p.published        -- return fields
ORDER BY p.published DESC          -- sort
LIMIT 10                           -- cap results
```

**Aggregation**
```cypher
count(n)          -- count nodes
collect(p.title)  -- gather into list
avg(r.score)      -- average
```

**Relationships in this graph**
- `(Author)-[:AUTHORED]->(Paper)`
- `(Paper)-[:HAS_CONCEPT]->(Concept)`
- `(Paper)-[:SIMILAR_TO {score}]->(Paper)`
- `(Concept)-[:CO_OCCURS_WITH {count}]->(Concept)`
- `(Paper)-[:SAME_AUTHOR]->(Paper)`
""")

# ═══════════════════════════════════════════════
# TAB 5 — Manage
# ═══════════════════════════════════════════════
with tab5:
    col_a, col_b = st.columns([3, 2])

    with col_a:
        st.markdown("**Add a paper**")
        st.caption("Paste an arXiv URL, ID, or title. The paper is fetched, summarised, and written to the graph.")

        paper_input = st.text_input(
            "arXiv URL, ID, or title:",
            placeholder="e.g. 2406.04093  or  Toy Models of Superposition",
        )
        track_topic = st.checkbox(
            "Also track this topic (sentinel fetches more papers like this every 24 h)",
            value=False,
        )
        add_btn = st.button("Add to graph ↗", use_container_width=True, type="primary")

        if add_btn and paper_input.strip():
            raw      = paper_input.strip()
            arxiv_id = None
            if "arxiv.org/abs/" in raw:
                arxiv_id = raw.split("arxiv.org/abs/")[-1].split("v")[0].strip()
            elif raw.replace(".", "").replace("-", "").isalnum() and len(raw) < 20:
                arxiv_id = raw.strip()

            with st.spinner("Fetching and processing paper…"):
                try:
                    search = (
                        arxiv.Search(id_list=[arxiv_id])
                        if arxiv_id
                        else arxiv.Search(query=raw, max_results=1)
                    )
                    client = arxiv.Client(page_size=1, delay_seconds=3, num_retries=2)
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(lambda: list(client.results(search)))
                        try:
                            results_list = future.result(timeout=15)
                        except concurrent.futures.TimeoutError:
                            st.error("arXiv timed out after 15 s. Please try again.")
                            results_list = []

                    if not results_list:
                        st.error("Paper not found on arXiv. Try a different ID or title.")
                    else:
                        paper = results_list[0]
                        raw_paper = {
                            "title":     paper.title,
                            "abstract":  paper.summary,
                            "authors":   [a.name for a in paper.authors],
                            "published": str(paper.published.date()),
                            "url":       paper.entry_id,
                            "arxiv_id":  paper.entry_id.split("/abs/")[-1],
                        }
                        from agents.parser     import parse_paper
                        from agents.summarizer import summarize_paper
                        processed = summarize_paper(parse_paper(raw_paper))

                        if processed and processed.get("processed"):
                            write_papers_to_graph([processed])
                            st.success(f"Added: **{paper.title}**")
                            st.caption(f"Concepts: {', '.join(processed.get('concepts', []))}")

                            if track_topic:
                                paper_concepts = processed.get("concepts", [])
                                new_topic = (paper_concepts[0] if paper_concepts
                                             else " ".join(paper.title.split()[:3]))
                                current = load_topics()
                                if new_topic not in current:
                                    current.append(new_topic)
                                    save_topics(current)
                                    st.info(f"Now tracking: **{new_topic}**")
                                else:
                                    st.info(f"Already tracking: **{new_topic}**")
                        else:
                            st.error("Failed to process paper. Check your Groq API key.")
                except Exception as e:
                    st.error(f"Error: {e}")

    with col_b:
        st.markdown("**Track a topic directly**")
        st.caption("Sentinel will fetch new papers on this topic every 24 h.")
        new_topic_input = st.text_input(
            "Topic:", placeholder="e.g. in-context learning", key="new_topic"
        )
        if st.button("Track topic", use_container_width=True):
            t = new_topic_input.strip()
            if t:
                current = load_topics()
                if t not in current:
                    current.append(t)
                    save_topics(current)
                    st.success(f"Now tracking: **{t}**")
                    st.rerun()
                else:
                    st.warning("Already tracking this topic.")

        st.markdown("---")
        st.markdown("**Tracked topics**")
        managed = load_topics()
        if managed:
            for i, topic in enumerate(list(managed)):
                tc, dc = st.columns([6, 1])
                tc.markdown(f"• {topic}")
                if dc.button("✕", key=f"rm_{i}", help=f"Remove '{topic}'"):
                    managed.remove(topic)
                    save_topics(managed)
                    st.rerun()
        else:
            st.caption("No topics tracked yet.")

        st.markdown("---")
        st.markdown("**Sentinel history**")
        if os.path.exists(SENTINEL_LOG_PATH):
            try:
                with open(SENTINEL_LOG_PATH) as f:
                    log = json.load(f)
                for entry in reversed(log[-5:]):
                    ts  = entry["timestamp"][:16].replace("T", " ")
                    n   = entry["papers_added"]
                    st.caption(f"`{ts}` · +{n} papers")
            except Exception:
                st.caption("Could not read sentinel log.")
        else:
            st.caption("No sentinel runs logged yet. Run `python main.py` to start.")
