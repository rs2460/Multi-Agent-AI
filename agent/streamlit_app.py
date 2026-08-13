"""
3D Agent Rack — Streamlit UI for the multi-agent research pipeline
====================================================================
Drives the SAME functions your pipeline.py uses (build_search_agents,
build_reader_agents, writer_chain, critic_chain) but renders each stage
as a tilted 3D console panel that "flattens" toward you and lights up
as soon as that agent's result lands — like a rack of server blades
ejecting one by one as the pipeline runs.

Run with:  streamlit run app.py
(Keep this file in the same folder as agents.py / pipeline.py)
"""

import html as _html
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# Make sure the local project folder (where agents.py lives) is importable
sys.path.append(str(Path(__file__).resolve().parent))

try:
    from agents import build_search_agents, build_reader_agents, writer_chain, critic_chain
except ImportError as e:
    st.set_page_config(page_title="Research Pipeline // Agent Rack", layout="wide")
    st.error(
        "Couldn't import `agents.py`. Put this file (app.py) in the same "
        f"folder as your pipeline's `agents.py`.\n\nDetails: {e}"
    )
    st.stop()

st.set_page_config(page_title="Research Pipeline // Agent Rack", page_icon="🧩", layout="wide")

# ----------------------------------------------------------------------------
# Global styling — dark console / server-rack aesthetic with CSS 3D transforms
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

    .stApp {
        background: radial-gradient(ellipse at top, #0B0F1A 0%, #05070B 62%);
        color: #E7ECF3;
    }

    .hero-title { font-family:'Space Mono',monospace; font-size:1.8rem; font-weight:700;
        color:#E7ECF3; letter-spacing:2px; margin: 0.4rem 0 0.1rem; }
    .hero-sub { color:#6B7688; font-size:.8rem; letter-spacing:3px; text-transform:uppercase; }

    .console-label { color:#6B7688; font-size:.72rem; letter-spacing:3px;
        font-family:'Space Mono',monospace; margin: 1.6rem 0 .4rem; }

    div[data-testid="stTextInput"] input {
        background:#0A0D16; border:1px solid rgba(255,255,255,.1); color:#E7ECF3;
        font-family:'JetBrains Mono',monospace; border-radius:4px; padding:.7rem .9rem;
    }
    div[data-testid="stTextInput"] input:focus { border-color:#4FD1FF; box-shadow:0 0 0 1px #4FD1FF44; }

    .stButton>button {
        background: linear-gradient(160deg,#12321f,#0A0D16); border:1px solid #39FF8855;
        color:#39FF88; font-family:'Space Mono',monospace; letter-spacing:2px; font-weight:700;
        border-radius:4px; padding:.65rem 1rem; transition: all .25s; width:100%;
    }
    .stButton>button:hover { box-shadow:0 0 20px #39FF8855; border-color:#39FF88; color:#c9ffe0; }

    .stage-panel {
        background: linear-gradient(135deg, #0D1220, #0A0D16);
        border: 1px solid rgba(255,255,255,.08);
        border-left: 3px solid var(--accent);
        border-radius: 6px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1rem;
        transform-style: preserve-3d;
        transform: perspective(1000px) rotateY(-2.5deg) rotateX(0.8deg);
        transition: transform .4s cubic-bezier(.2,.8,.2,1), box-shadow .4s, opacity .4s;
        box-shadow: 8px 14px 30px rgba(0,0,0,.55);
    }
    .stage-panel:hover {
        transform: perspective(1000px) rotateY(0deg) rotateX(0deg) translateZ(6px);
        box-shadow: 0 16px 36px rgba(0,0,0,.6), 0 0 26px var(--glow);
    }
    .stage-panel.pending { opacity:.42; filter:grayscale(.5); }
    .stage-panel.active { animation: pulseGlow 1.5s ease-in-out infinite; }
    @keyframes pulseGlow {
        0%,100% { box-shadow:8px 14px 30px rgba(0,0,0,.55); }
        50% { box-shadow:0 0 30px var(--glow); }
    }
    .stage-panel.done { animation: flatten .55s ease-out; }
    @keyframes flatten {
        from { transform:perspective(1000px) rotateY(-14deg) translateZ(-30px); opacity:0; }
        to { transform:perspective(1000px) rotateY(-2.5deg); opacity:1; }
    }

    .panel-head { display:flex; align-items:center; gap:.6rem; margin-bottom:.55rem; }
    .panel-num { color:var(--accent); font-family:'Space Mono',monospace; font-size:.8rem; opacity:.85; }
    .panel-name { font-family:'Space Mono',monospace; font-size:.92rem; font-weight:700;
        letter-spacing:2px; color:#E7ECF3; flex:1; }
    .panel-led { width:8px; height:8px; border-radius:50%; background:#333; flex-shrink:0; }
    .panel-led.active { background:var(--accent); box-shadow:0 0 10px var(--accent); animation:blink 1.2s infinite; }
    .panel-led.done { background:var(--accent); box-shadow:0 0 8px var(--accent); }
    @keyframes blink { 0%,100% { opacity:1; } 50% { opacity:.3; } }

    .panel-desc { color:#8791A3; font-size:.85rem; }
    .panel-status { margin-top:.45rem; font-family:'JetBrains Mono',monospace; font-size:.74rem;
        color:#6B7688; letter-spacing:1px; }
    .panel-status.blink { animation: blink 1.2s infinite; color:var(--accent); }

    .panel-readout {
        font-family:'JetBrains Mono',monospace; font-size:.8rem; line-height:1.55; color:#C9D2E0;
        max-height: 320px; overflow-y:auto; white-space:pre-wrap;
        background:#080A10; border:1px solid rgba(255,255,255,.06); border-radius:4px; padding:.75rem .9rem;
    }
    .panel-readout::-webkit-scrollbar { width:6px; }
    .panel-readout::-webkit-scrollbar-thumb { background:#2A3040; border-radius:3px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Hero: decorative interactive 3D rack (mouse-tilt), isolated in an iframe
# ----------------------------------------------------------------------------
components.html(
    """
    <div class="rack-wrap">
      <div class="rack" id="rack">
        <div class="blade" style="--c:#4FD1FF"><span class="dot"></span>SEARCH</div>
        <div class="blade" style="--c:#B388FF"><span class="dot"></span>READER</div>
        <div class="blade" style="--c:#39FF88"><span class="dot"></span>WRITER</div>
        <div class="blade" style="--c:#FFB020"><span class="dot"></span>CRITIC</div>
      </div>
      <div class="scanline"></div>
    </div>
    <style>
      body { margin:0; background:transparent; }
      .rack-wrap { perspective:1200px; padding:26px 10px 6px; position:relative; }
      .rack { display:flex; gap:20px; justify-content:center; transform-style:preserve-3d;
        transition: transform .15s ease-out; }
      .blade {
        width:150px; height:110px; background:linear-gradient(160deg,#0D1220,#080B12);
        border:1px solid rgba(255,255,255,.08); border-top:3px solid var(--c); border-radius:4px;
        display:flex; flex-direction:column; align-items:center; justify-content:center; gap:10px;
        color:#9AA4B5; font-family:'Space Mono',monospace; font-size:11px; letter-spacing:2px;
        box-shadow:0 20px 40px rgba(0,0,0,.6); animation: sway 6s ease-in-out infinite;
      }
      .blade:nth-child(2) { animation-delay:-1.5s; }
      .blade:nth-child(3) { animation-delay:-3s; }
      .blade:nth-child(4) { animation-delay:-4.5s; }
      @keyframes sway {
        0%,100% { transform: rotateY(-10deg) rotateX(3deg); }
        50% { transform: rotateY(6deg) rotateX(-2deg); }
      }
      .dot { width:8px; height:8px; border-radius:50%; background:var(--c);
        box-shadow:0 0 10px var(--c); animation:blink 1.8s infinite; }
      @keyframes blink { 0%,100% { opacity:1; } 50% { opacity:.25; } }
      .scanline { position:absolute; left:6%; right:6%; height:2px; top:20px;
        background:linear-gradient(90deg,transparent,#4FD1FF,transparent); opacity:.5;
        animation:scan 4s linear infinite; }
      @keyframes scan { 0% { top:20px; } 100% { top:150px; } }
    </style>
    <script>
      const rack = document.getElementById('rack');
      document.addEventListener('mousemove', (e) => {
        const x = (e.clientX / window.innerWidth - 0.5) * 16;
        const y = (e.clientY / window.innerHeight - 0.5) * -10;
        rack.style.transform = `rotateY(${x}deg) rotateX(${y}deg)`;
      });
    </script>
    """,
    height=190,
)

st.markdown('<div class="hero-title">RESEARCH PIPELINE // AGENT RACK</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">4-stage multi-agent research system</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Console input
# ----------------------------------------------------------------------------
st.markdown('<div class="console-label">TOPIC</div>', unsafe_allow_html=True)
col1, col2 = st.columns([5, 1])
with col1:
    topic = st.text_input(
        "topic", placeholder="e.g. advances in solid-state batteries 2026",
        label_visibility="collapsed",
    )
with col2:
    run_clicked = st.button("RUN ▶")

STAGES = [
    {"key": "search", "num": "01", "name": "SEARCH AGENT", "accent": "#4FD1FF",
     "desc": "Scanning for recent, reliable sources."},
    {"key": "reader", "num": "02", "name": "READER AGENT", "accent": "#B388FF",
     "desc": "Scraping the top result for deeper content."},
    {"key": "writer", "num": "03", "name": "WRITER CHAIN", "accent": "#39FF88",
     "desc": "Synthesizing the research into a report."},
    {"key": "critic", "num": "04", "name": "CRITIC CHAIN", "accent": "#FFB020",
     "desc": "Reviewing the report for gaps and rigor."},
]


def esc(x) -> str:
    return _html.escape(str(x))


def as_text(x) -> str:
    """Normalize LangChain outputs (str, or objects with .content) to plain text."""
    return getattr(x, "content", x)


def render_panel(placeholder, stage: dict, state: str, content=None) -> None:
    accent = stage["accent"]
    if state == "pending":
        body = (
            f'<div class="panel-desc">{esc(stage["desc"])}</div>'
            f'<div class="panel-status">STANDBY</div>'
        )
    elif state == "active":
        body = (
            f'<div class="panel-desc">{esc(stage["desc"])}</div>'
            f'<div class="panel-status blink">● PROCESSING…</div>'
        )
    else:
        body = f'<div class="panel-readout">{esc(as_text(content))}</div>'

    placeholder.markdown(
        f"""
        <div class="stage-panel {state}" style="--accent:{accent}; --glow:{accent}66;">
          <div class="panel-head">
            <span class="panel-num">{stage['num']}</span>
            <span class="panel-name">{stage['name']}</span>
            <span class="panel-led {state}"></span>
          </div>
          {body}
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown('<div class="console-label">PIPELINE</div>', unsafe_allow_html=True)

placeholders = {}
for stage in STAGES:
    placeholders[stage["key"]] = st.empty()
    render_panel(placeholders[stage["key"]], stage, "pending")

# ----------------------------------------------------------------------------
# Run the pipeline (same logic as pipeline.py), updating panels live
# ----------------------------------------------------------------------------
if run_clicked:
    if not topic.strip():
        st.warning("Enter a topic before running the pipeline.")
    else:
        state: dict = {}

        # 01 — Search agent
        render_panel(placeholders["search"], STAGES[0], "active")
        search_agent = build_search_agents()
        search_result = search_agent.invoke(
            {"messages": [("user", f"Find recent, reliable and detailed information about:{topic}")]}
        )
        state["search_results"] = search_result["messages"][-1].content
        render_panel(placeholders["search"], STAGES[0], "done", state["search_results"])

        # 02 — Reader agent
        render_panel(placeholders["reader"], STAGES[1], "active")
        reader_agent = build_reader_agents()
        reader_result = reader_agent.invoke(
            {
                "messages": [
                    (
                        "user",
                        f"Based on the following search results about '{topic}', "
                        f"pick the most relevant URL and scrape it for deeper content.\n\n"
                        f"Search Results:\n{state['search_results'][:800]}",
                    )
                ]
            }
        )
        state["scraped_content"] = reader_result["messages"][-1].content
        render_panel(placeholders["reader"], STAGES[1], "done", state["scraped_content"])

        # 03 — Writer chain
        render_panel(placeholders["writer"], STAGES[2], "active")
        research_combined = (
            f"Search Results : \n{state['search_results']}\n\n"
            f"Detailed Scraped Content : \n{state['scraped_content']}"
        )
        state["report"] = writer_chain.invoke({"topic": topic, "research": research_combined})
        render_panel(placeholders["writer"], STAGES[2], "done", state["report"])

        # 04 — Critic chain
        render_panel(placeholders["critic"], STAGES[3], "active")
        state["feedback"] = critic_chain.invoke({"report": state["report"]})
        render_panel(placeholders["critic"], STAGES[3], "done", state["feedback"])

        st.success("Pipeline complete — all 4 agents reported in.")
