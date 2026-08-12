"""
streamlit_app.py
-----------------
Drop this file next to pipeline.py and agents.py, then run:

    streamlit run streamlit_app.py

It re-implements the same four stages as pipeline.run_research_pipeline()
(search -> read -> write -> critique) using the exact same agent builders
and chains from agents.py, and drives a live 3D telemetry panel (Three.js +
a custom GLSL glow shader, HTML/CSS console theme, orchestrated from
Streamlit) that lights up as each stage runs.

Extras added on top of the base pipeline:
  - per-stage timing + a duration bar chart
  - "Retry from failed stage" so a flaky API call doesn't cost you the
    whole run
  - a session log in the sidebar so you can flip back through past runs
    without re-invoking the agents
  - word count / read-time + a one-click copy button on the report
"""

import json
import time
import traceback
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from agents import build_search_agents, build_reader_agents, writer_chain, critic_chain

STAGES = ["search", "reader", "writer", "critic"]
STAGE_LABEL = {
    "search": "STAGE 01 · SEARCH",
    "reader": "STAGE 02 · READ",
    "writer": "STAGE 03 · WRITE",
    "critic": "STAGE 04 · CRITIQUE",
}
STAGE_SHORT = {"search": "Search", "reader": "Read", "writer": "Write", "critic": "Critique"}
RESULT_KEY = {"search": "search_results", "reader": "scraped_content", "writer": "report", "critic": "feedback"}

st.set_page_config(page_title="Research Pipeline Console", page_icon="🛰️", layout="wide")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def to_text(x) -> str:
    """agents.py chains may return a string or a message-like object; normalize to text."""
    if hasattr(x, "content"):
        return x.content
    return str(x)


def init_state():
    defaults = {
        "status": {s: "pending" for s in STAGES},
        "results": {},
        "durations": {},
        "run_topic": "",
        "failed_stage": None,
        "history": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    # applied before the topic widget is instantiated below, so it's a safe mutation
    if st.session_state.get("pending_topic") is not None:
        st.session_state["topic_box"] = st.session_state.pop("pending_topic")


def mark(stage: str, value: str):
    st.session_state.status[stage] = value


def reset_run_state():
    st.session_state.status = {s: "pending" for s in STAGES}
    st.session_state.results = {}
    st.session_state.durations = {}
    st.session_state.failed_stage = None


def overall_status():
    vals = st.session_state.status.values()
    if any(v == "error" for v in vals):
        return "ERROR", "#f87171"
    if any(v == "active" for v in vals):
        return "RUNNING", "#fbbf24"
    if all(v == "done" for v in vals):
        return "COMPLETE", "#4ade80"
    return "IDLE", "#64748b"


# --------------------------------------------------------------------------
# Stage runners — same prompts/logic as pipeline.py, split out so a failed
# stage can be retried without re-running the stages that already succeeded
# --------------------------------------------------------------------------
def run_search(topic):
    agent = build_search_agents()
    result = agent.invoke(
        {"messages": [("user", f"Find recent, reliable and detailed information about:{topic}")]}
    )
    return result["messages"][-1].content


def run_reader(topic, search_results):
    agent = build_reader_agents()
    result = agent.invoke(
        {
            "messages": [
                (
                    "user",
                    f"Based on the following search results about '{topic}', "
                    f"pick the most relevant URL and scrape it for deeper content.\n\n"
                    f"Search Results:\n{search_results[:800]}",
                )
            ]
        }
    )
    return result["messages"][-1].content


def run_writer(topic, search_results, scraped_content):
    combined = (
        f"Search Results : \n{search_results}\n\n"
        f"Detailed Scraped Content : \n{scraped_content}"
    )
    report = writer_chain.invoke({"topic": topic, "research": combined})
    return to_text(report)


def run_critic(report):
    feedback = critic_chain.invoke({"report": report})
    return to_text(feedback)


def run_stage(stage, topic):
    res = st.session_state.results
    if stage == "search":
        return run_search(topic)
    if stage == "reader":
        return run_reader(topic, res["search_results"])
    if stage == "writer":
        return run_writer(topic, res["search_results"], res["scraped_content"])
    if stage == "critic":
        return run_critic(res["report"])
    raise ValueError(f"Unknown stage: {stage}")


# --------------------------------------------------------------------------
# Global console theme
# --------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"] { font-family: 'JetBrains Mono', monospace; }

    .stApp {
        background: radial-gradient(ellipse at top, #0b1120 0%, #060910 60%, #030509 100%);
        color: #cbd5e1;
    }
    .stApp::before {
        content: "";
        position: fixed; inset: 0; pointer-events: none; z-index: 0;
        background: repeating-linear-gradient(
            180deg, rgba(255,255,255,0.015) 0px, rgba(255,255,255,0.015) 1px,
            transparent 1px, transparent 3px
        );
    }

    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; letter-spacing: 0.3px; }

    .console-eyebrow {
        font-family: 'JetBrains Mono', monospace; font-size: 12px; letter-spacing: 3px;
        color: #38bdf8; text-transform: uppercase; margin-bottom: -6px;
    }
    .status-badge {
        display:inline-block; font-family:'JetBrains Mono',monospace; font-size:12px;
        letter-spacing:2px; padding:4px 12px; border-radius:999px; margin-left:12px;
        vertical-align:middle; border:1px solid currentColor;
    }

    .chip-row { display:flex; gap:10px; flex-wrap:wrap; margin: 6px 0 18px 0; }
    .chip {
        background:#0f172a; border:1px solid #1e293b; border-radius:999px;
        padding:5px 14px; font-size:12px; color:#94a3b8; font-family:'JetBrains Mono',monospace;
        letter-spacing:0.5px;
    }
    .chip b { color:#e2e8f0; }

    .stTextInput > div > div > input {
        background: #0f172a; color: #e2e8f0; border: 1px solid #1e293b;
        font-family: 'JetBrains Mono', monospace;
    }

    .stButton > button {
        background: transparent; color: #fbbf24; border: 1px solid #fbbf24;
        font-family: 'JetBrains Mono', monospace; text-transform: uppercase;
        letter-spacing: 1px; border-radius: 4px; padding: 0.5rem 1.4rem; font-weight: 600;
    }
    .stButton > button:hover { background: #fbbf24; color: #0b1120; border-color: #fbbf24; }
    .stButton > button:disabled { color: #475569; border-color: #1e293b; }

    .streamlit-expanderHeader {
        font-family: 'JetBrains Mono', monospace !important; letter-spacing: 0.5px;
        background: #0f172a !important; border: 1px solid #1e293b !important; border-radius: 4px !important;
    }

    .status-line { font-family: 'JetBrains Mono', monospace; font-size: 13px; color: #94a3b8; letter-spacing: 0.5px; }

    section[data-testid="stSidebar"] { background: #060910; border-right: 1px solid #1e293b; }
    section[data-testid="stSidebar"] .stButton > button {
        width: 100%; padding: 0.3rem 0.8rem; font-size: 11px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# 3D telemetry panel (Three.js scene + GLSL glow shader + flowing data
# particles along completed links, framed with HUD corner brackets)
# --------------------------------------------------------------------------
PIPELINE_HTML_TEMPLATE = """
<style>
  html, body {
    margin: 0;
    padding: 0;
    width: 900px;
    height: 500px;
    overflow: hidden;
    background: transparent;
  }
  #viz-wrap {
    position: relative;
    width: 900px;
    height: 500px;
    border-radius: 14px;
    overflow: hidden;
    background: radial-gradient(ellipse at center, #0f172a 0%, #020617 75%);
    border: 1px solid #1e293b;
    box-sizing: border-box;
  }
  #canvas-holder {
    width: 100%;
    height: 100%;
  }
  .node-label {
    color:#475569; font-size:12px; letter-spacing:1px; font-weight:600px;
    width:100%; text-align:center; transition:all .4s ease;
  }
  .node-label.active { color:#fbbf24; text-shadow:0 0 12px rgba(251,191,36,0.8); }
  .node-label.done   { color:#4ade80; text-shadow:0 0 10px rgba(74,222,128,0.7); }
  .node-label.error  { color:#f87171; text-shadow:0 0 10px rgba(248,113,113,0.7); }

  .hud-corner { position:absolute; width:16px; height:16px; border-color:#38bdf8; opacity:0.55; }
  .hud-tl { top:10px; left:10px; border-top:2px solid; border-left:2px solid; }
  .hud-tr { top:10px; right:10px; border-top:2px solid; border-right:2px solid; }
  .hud-bl { bottom:10px; left:10px; border-bottom:2px solid; border-left:2px solid; }
  .hud-br { bottom:10px; right:10px; border-bottom:2px solid; border-right:2px solid; }
</style>

<div id="viz-wrap">
  <div id="canvas-holder"></div>
  <div class="hud-corner hud-tl"></div>
  <div class="hud-corner hud-tr"></div>
  <div class="hud-corner hud-bl"></div>
  <div class="hud-corner hud-br"></div>
  <div id="labels" style="position:absolute;bottom:16px;left:0;right:0;display:flex;justify-content:space-around;
       pointer-events:none;font-family:'JetBrains Mono',monospace;">
    <div class="node-label" data-idx="0">01 · SEARCH</div>
    <div class="node-label" data-idx="1">02 · READ</div>
    <div class="node-label" data-idx="2">03 · WRITE</div>
    <div class="node-label" data-idx="3">04 · CRITIQUE</div>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(function () {
  var STATUS = __STATUS_JSON__;
  var order = ["search", "reader", "writer", "critic"];

  var holder = document.getElementById('canvas-holder');
  var w = holder.clientWidth, h = holder.clientHeight;

  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 1000);
  camera.position.set(0, 2.1, 13);
  camera.lookAt(0, 0, 0);

  var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(w, h);
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  holder.appendChild(renderer.domElement);

  scene.add(new THREE.AmbientLight(0x8899ff, 0.55));
  var key = new THREE.PointLight(0x38bdf8, 1.3, 50);
  key.position.set(0, 6, 8);
  scene.add(key);

  var starGeo = new THREE.BufferGeometry();
  var starCount = 350;
  var positions = new Float32Array(starCount * 3);
  for (var i = 0; i < starCount; i++) {
    positions[i * 3]     = (Math.random() - 0.5) * 60;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 30;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 60 - 10;
  }
  starGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  var starMat = new THREE.PointsMaterial({ color: 0x334155, size: 0.06 });
  scene.add(new THREE.Points(starGeo, starMat));

  var group = new THREE.Group();
  scene.add(group);

  var colors = { pending: 0x334155, active: 0xfbbf24, done: 0x4ade80, error: 0xf87171 };

  function glowMaterial(hexColor) {
    return new THREE.ShaderMaterial({
      uniforms: { c: { value: new THREE.Color(hexColor) }, pulse: { value: 0 } },
      vertexShader: [
        'varying vec3 vNormal;',
        'void main() {',
        '  vNormal = normalize(normalMatrix * normal);',
        '  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);',
        '}'
      ].join('\\n'),
      fragmentShader: [
        'uniform vec3 c;',
        'uniform float pulse;',
        'varying vec3 vNormal;',
        'void main() {',
        '  float intensity = pow(0.65 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 2.0);',
        '  vec3 glow = c * intensity * (1.0 + pulse * 1.6);',
        '  gl_FragColor = vec4(glow, intensity);',
        '}'
      ].join('\\n'),
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.BackSide
    });
  }

  var xs = [-6, -2, 2, 6];
  var nodes = [];
  var flowParticles = [];

  for (var idx = 0; idx < 4; idx++) {
    var st = STATUS[order[idx]] || 'pending';
    var col = colors[st];
    var zpos = -Math.pow(xs[idx], 2) * 0.05;

    var coreGeo = new THREE.IcosahedronGeometry(0.9, 1);
    var coreMat = new THREE.MeshPhongMaterial({
      color: col, emissive: col, emissiveIntensity: st === 'active' ? 0.9 : 0.35,
      shininess: 80, flatShading: true
    });
    var core = new THREE.Mesh(coreGeo, coreMat);
    core.position.set(xs[idx], 0, zpos);
    group.add(core);

    var glowGeo = new THREE.IcosahedronGeometry(1.35, 2);
    var glowMat = glowMaterial(col);
    var glow = new THREE.Mesh(glowGeo, glowMat);
    glow.position.copy(core.position);
    group.add(glow);

    nodes.push({ core: core, mat: coreMat, glowMat: glowMat, status: st });

    if (idx > 0) {
      var prevX = xs[idx - 1], curX = xs[idx];
      var prevZ = -Math.pow(prevX, 2) * 0.05, curZ = -Math.pow(curX, 2) * 0.05;
      var midX = (prevX + curX) / 2, midY = -0.18, midZ = -Math.pow(midX, 2) * 0.05;
      var curve = new THREE.QuadraticBezierCurve3(
        new THREE.Vector3(prevX, 0, prevZ),
        new THREE.Vector3(midX, midY, midZ),
        new THREE.Vector3(curX, 0, curZ)
      );
      var tubeGeo = new THREE.TubeGeometry(curve, 20, 0.045, 8, false);
      var linkDone = STATUS[order[idx - 1]] === 'done';
      var tubeMat = new THREE.MeshBasicMaterial({
        color: linkDone ? colors.done : colors.pending, transparent: true, opacity: 0.55
      });
      group.add(new THREE.Mesh(tubeGeo, tubeMat));

      if (linkDone) {
        var particleGeo = new THREE.SphereGeometry(0.09, 8, 8);
        var particleMat = new THREE.MeshBasicMaterial({ color: 0x4ade80 });
        var particle = new THREE.Mesh(particleGeo, particleMat);
        group.add(particle);
        flowParticles.push({ mesh: particle, curve: curve, t: Math.random() });
      }
    }
  }

  var t = 0;
  function animate() {
    t += 0.02;
    group.rotation.y = Math.sin(t * 0.15) * 0.18;
    group.rotation.x = Math.sin(t * 0.1) * 0.05;

    for (var n = 0; n < nodes.length; n++) {
      var node = nodes[n];
      if (node.status === 'active') {
        var pulse = (Math.sin(t * 4) + 1) / 2;
        var scale = 1 + pulse * 0.12;
        node.core.scale.set(scale, scale, scale);
        node.mat.emissiveIntensity = 0.6 + pulse * 0.8;
        node.glowMat.uniforms.pulse.value = pulse;
      } else {
        node.core.rotation.y += 0.004;
      }
    }

    for (var p = 0; p < flowParticles.length; p++) {
      var fp = flowParticles[p];
      fp.t += 0.006;
      if (fp.t > 1) fp.t = 0;
      var pos = fp.curve.getPointAt(fp.t);
      fp.mesh.position.copy(pos);
    }

    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }
  animate();

  var labels = document.querySelectorAll('.node-label');
  labels.forEach(function (el) {
    var i = parseInt(el.getAttribute('data-idx'), 10);
    var s = STATUS[order[i]] || 'pending';
    el.classList.remove('active', 'done', 'error');
    if (s !== 'pending') el.classList.add(s);
  });

  function syncSize() {
    var w2 = holder.clientWidth, h2 = holder.clientHeight;
    if (w2 === 0 || h2 === 0) return;
    camera.aspect = w2 / h2;
    camera.updateProjectionMatrix();
    renderer.setSize(w2, h2);
  }

  window.addEventListener('resize', syncSize);

  // Streamlit Cloud sizes the component's iframe asynchronously (after this
  // script has already run), so the very first clientWidth read above can
  // be captured before the iframe reaches its final, real width — locking
  // the canvas at a too-small size that a plain window "resize" event never
  // corrects. ResizeObserver watches the holder itself and re-syncs whenever
  // its actual box size changes, catching that race (and any later ones,
  // e.g. sidebar collapse/expand).
  if (window.ResizeObserver) {
    var ro = new ResizeObserver(function () { syncSize(); });
    ro.observe(holder);
  } else {
    // Fallback for older browsers without ResizeObserver support.
    setTimeout(syncSize, 300);
  }
})();
</script>
"""


def render_pipeline_visual(status: dict):
    html = PIPELINE_HTML_TEMPLATE.replace("__STATUS_JSON__", json.dumps(status))
    components.html(html, height=620, scrolling=False)


COPY_BUTTON_TEMPLATE = """
<button id="copy-btn-__KEY__" class="copy-btn">__LABEL__</button>
<script>
(function(){
  var btn = document.getElementById('copy-btn-__KEY__');
  var txt = __TEXT_JSON__;
  btn.addEventListener('click', function(){
    navigator.clipboard.writeText(txt);
    var original = btn.innerText;
    btn.innerText = '✓ copied';
    setTimeout(function(){ btn.innerText = original; }, 1400);
  });
})();
</script>
<style>
.copy-btn {
  background:transparent; color:#38bdf8; border:1px solid #1e293b;
  font-family:'JetBrains Mono',monospace; text-transform:uppercase; letter-spacing:1px;
  border-radius:4px; padding:0.5rem 1.4rem; font-size:12px; cursor:pointer; width:100%;
}
.copy-btn:hover { border-color:#38bdf8; }
</style>
"""


def copy_button(text: str, key: str, label: str = "⧉ COPY REPORT"):
    html = (
        COPY_BUTTON_TEMPLATE.replace("__KEY__", key)
        .replace("__LABEL__", label)
        .replace("__TEXT_JSON__", json.dumps(text))
    )
    components.html(html, height=46)


# --------------------------------------------------------------------------
# Sidebar — session log of past runs (view-only, doesn't re-invoke agents)
# --------------------------------------------------------------------------
def render_sidebar():
    with st.sidebar:
        st.markdown("### 🛰️ SESSION LOG")
        if not st.session_state.history:
            st.caption("No runs yet this session.")
        for i, rec in enumerate(reversed(st.session_state.history)):
            badge = "🟢" if rec["status"] == "done" else "🔴"
            st.markdown(f"**{badge} {rec['topic'][:36]}**")
            st.caption(f"{rec['time']} · {rec['total']:.1f}s total")
            if st.button("View", key=f"view-{i}"):
                st.session_state.results = rec["results"]
                st.session_state.status = rec["stage_status"]
                st.session_state.durations = rec["durations"]
                st.session_state.run_topic = rec["topic"]
                st.session_state.pending_topic = rec["topic"]
                st.session_state.failed_stage = None
            st.divider()
        if st.session_state.history:
            if st.button("🗑 Clear session log"):
                st.session_state.history = []


def log_history():
    st.session_state.history.append(
        {
            "topic": st.session_state.run_topic,
            "time": datetime.now().strftime("%H:%M:%S"),
            "status": "error" if st.session_state.failed_stage else "done",
            "total": sum(st.session_state.durations.values()),
            "results": dict(st.session_state.results),
            "stage_status": dict(st.session_state.status),
            "durations": dict(st.session_state.durations),
        }
    )
    st.session_state.history = st.session_state.history[-8:]


def update_last_history():
    if st.session_state.history:
        rec = st.session_state.history[-1]
        rec["status"] = "error" if st.session_state.failed_stage else "done"
        rec["results"] = dict(st.session_state.results)
        rec["stage_status"] = dict(st.session_state.status)
        rec["durations"] = dict(st.session_state.durations)
        rec["total"] = sum(st.session_state.durations.values())


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------
init_state()
render_sidebar()

status_label, status_color = overall_status()
st.markdown('<div class="console-eyebrow">MULTI-AGENT RESEARCH · TELEMETRY CONSOLE</div>', unsafe_allow_html=True)
st.markdown(
    f'<h1 style="display:inline-block;margin-bottom:0;">Research Pipeline</h1>'
    f'<span class="status-badge" style="color:{status_color};">● {status_label}</span>',
    unsafe_allow_html=True,
)
st.caption("⚪ pending&nbsp;&nbsp;&nbsp;🟡 active&nbsp;&nbsp;&nbsp;🟢 done&nbsp;&nbsp;&nbsp;🔴 error", unsafe_allow_html=True)

viz_slot = st.empty()
with viz_slot.container():
    render_pipeline_visual(st.session_state.status)

total_time = sum(st.session_state.durations.values()) if st.session_state.durations else 0.0
done_count = sum(1 for v in st.session_state.status.values() if v == "done")
st.markdown(
    f"""
    <div class="chip-row">
      <div class="chip">SESSION RUNS <b>{len(st.session_state.history)}</b></div>
      <div class="chip">STAGES DONE <b>{done_count}/4</b></div>
      <div class="chip">ELAPSED <b>{total_time:.1f}s</b></div>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns([4, 1, 1])
with col1:
    topic_input = st.text_input("Research topic", key="topic_box", placeholder="e.g. quantum error correction breakthroughs 2026")
with col2:
    st.write("")
    st.write("")
    run_clicked = st.button("▶ Run")
with col3:
    st.write("")
    st.write("")
    retry_clicked = st.button("↻ Retry", disabled=st.session_state.failed_stage is None)

status_text = st.empty()


def execute_from(start_index: int, topic: str) -> bool:
    for stage in STAGES[start_index:]:
        mark(stage, "active")
        with viz_slot.container():
            render_pipeline_visual(st.session_state.status)
        status_text.markdown(f'<span class="status-line">RUNNING · {STAGE_LABEL[stage]}…</span>', unsafe_allow_html=True)

        t0 = time.time()
        try:
            output = run_stage(stage, topic)
        except Exception as e:
            st.session_state.durations[stage] = time.time() - t0
            mark(stage, "error")
            st.session_state.failed_stage = stage
            with viz_slot.container():
                render_pipeline_visual(st.session_state.status)
            status_text.markdown(
                f'<span class="status-line">ERROR · {STAGE_LABEL[stage]} failed — {e}</span>', unsafe_allow_html=True
            )
            st.error(f"Pipeline failed at stage: {stage}")
            st.code(traceback.format_exc())
            return False

        st.session_state.results[RESULT_KEY[stage]] = output
        st.session_state.durations[stage] = time.time() - t0
        mark(stage, "done")
        with viz_slot.container():
            render_pipeline_visual(st.session_state.status)

    status_text.markdown('<span class="status-line">COMPLETE · report ready below.</span>', unsafe_allow_html=True)
    return True


if run_clicked:
    if not topic_input or not topic_input.strip():
        st.warning("Enter a topic first.")
    else:
        reset_run_state()
        st.session_state.run_topic = topic_input.strip()
        with viz_slot.container():
            render_pipeline_visual(st.session_state.status)
        execute_from(0, st.session_state.run_topic)
        log_history()
elif retry_clicked and st.session_state.failed_stage:
    start_idx = STAGES.index(st.session_state.failed_stage)
    st.session_state.failed_stage = None
    execute_from(start_idx, st.session_state.run_topic)
    update_last_history()

# --------------------------------------------------------------------------
# Persisted results (survive reruns triggered by other widgets, e.g. downloads)
# --------------------------------------------------------------------------
results = st.session_state.results

if results.get("search_results"):
    with st.expander(f"{STAGE_LABEL['search']} — raw findings"):
        st.write(results["search_results"])

if results.get("scraped_content"):
    with st.expander(f"{STAGE_LABEL['reader']} — scraped detail"):
        st.write(results["scraped_content"])

if results.get("report"):
    st.markdown(f"### {STAGE_LABEL['writer']}")
    wc = len(results["report"].split())
    read_min = max(1, round(wc / 200))
    st.caption(f"{wc} words · ~{read_min} min read")
    st.markdown(results["report"])
    dl_col, copy_col = st.columns([1, 1])
    with dl_col:
        st.download_button("⬇ Download .md", results["report"], file_name="research_report.md", mime="text/markdown")
    with copy_col:
        copy_button(results["report"], key="report")

if results.get("feedback"):
    with st.expander(f"{STAGE_LABEL['critic']} — review notes", expanded=True):
        st.write(results["feedback"])

if st.session_state.durations:
    st.markdown("#### Stage timing")
    chart_data = {STAGE_SHORT[s]: round(st.session_state.durations[s], 2) for s in STAGES if s in st.session_state.durations}
    st.bar_chart(chart_data)
