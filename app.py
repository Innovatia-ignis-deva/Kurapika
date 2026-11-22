"""Kurapika's interactive Flow Syntax editor. Run with: streamlit run app.py"""
from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import flowlang
from flowlang import NAME

HERE = Path(__file__).parent
EXAMPLES = sorted((HERE / "examples").glob("*.flow"))
DEFAULT = (HERE / "examples" / "quickstart.flow")

st.set_page_config(page_title=f"{NAME} | Flow Diagram Studio", page_icon="🔀", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(135deg, #f8faff 0%, #f1f5fb 100%); }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    [data-testid="stSidebar"] { background: #111827; }
    [data-testid="stSidebar"] * { color: #eef2ff; }
    [data-testid="stSidebar"] input, [data-testid="stSidebar"] select {
        color: #111827 !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] * {
        color: #111827 !important;
    }
    div[data-testid="stTextArea"] textarea {
        font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
        font-size: 0.92rem;
        line-height: 1.55;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def preview_html(svg: str, height: int) -> str:
    """SVG with zoom, pan, fit and browser-side PNG/JPG/WEBP download (no native libraries needed)."""
    return f"""
<style>
 body{{margin:0;font-family:Arial,Helvetica,sans-serif}}
 #bar{{display:flex;gap:6px;flex-wrap:wrap;padding:6px;background:#f4f5f7;border-bottom:1px solid #ddd}}
 #bar button,#bar select{{padding:4px 10px;border:1px solid #bbb;border-radius:5px;background:#fff;cursor:pointer;font-size:13px}}
 #view{{height:{height - 46}px;overflow:hidden;position:relative;background:#fff;cursor:grab;
   background-image:linear-gradient(45deg,#f1f1f1 25%,transparent 25%,transparent 75%,#f1f1f1 75%),
   linear-gradient(45deg,#f1f1f1 25%,transparent 25%,transparent 75%,#f1f1f1 75%);
   background-size:16px 16px;background-position:0 0,8px 8px}}
 #stage{{transform-origin:0 0;position:absolute;left:0;top:0}}
</style>
<div id="bar">
 <button onclick="zoom(1.2)">＋</button><button onclick="zoom(1/1.2)">－</button>
 <button onclick="fit()">Fit</button><button onclick="actual()">100%</button>
 <span style="flex:1"></span>
 <select id="fmt"><option value="png">PNG</option><option value="jpeg">JPG</option><option value="webp">WEBP</option></select>
 <select id="scl"><option>1</option><option selected>2</option><option>3</option><option>4</option></select>
 <button onclick="dl()">Download image</button>
</div>
<div id="view"><div id="stage">{svg}</div></div>
<script>
const view=document.getElementById('view'),stage=document.getElementById('stage');
const svg=stage.querySelector('svg');
const W=parseFloat(svg.getAttribute('width'))||800,H=parseFloat(svg.getAttribute('height'))||600;
let s=1,tx=0,ty=0;
function apply(){{stage.style.transform='translate('+tx+'px,'+ty+'px) scale('+s+')';}}
function fit(){{const r=view.getBoundingClientRect();s=Math.min(r.width/W,r.height/H,1.5)*0.97;
 tx=(r.width-W*s)/2;ty=(r.height-H*s)/2;apply();}}
function actual(){{s=1;tx=10;ty=10;apply();}}
function zoom(f,cx,cy){{const r=view.getBoundingClientRect();cx=cx===undefined?r.width/2:cx;cy=cy===undefined?r.height/2:cy;
 tx=cx-(cx-tx)*f;ty=cy-(cy-ty)*f;s*=f;apply();}}
view.addEventListener('wheel',e=>{{e.preventDefault();const r=view.getBoundingClientRect();
 zoom(e.deltaY<0?1.1:1/1.1,e.clientX-r.left,e.clientY-r.top);}},{{passive:false}});
let drag=null;
view.addEventListener('mousedown',e=>{{drag=[e.clientX-tx,e.clientY-ty];view.style.cursor='grabbing';}});
window.addEventListener('mouseup',()=>{{drag=null;view.style.cursor='grab';}});
window.addEventListener('mousemove',e=>{{if(drag){{tx=e.clientX-drag[0];ty=e.clientY-drag[1];apply();}}}});
function dl(){{
 const k=parseFloat(document.getElementById('scl').value),type='image/'+document.getElementById('fmt').value;
 const xml=new XMLSerializer().serializeToString(svg);
 const img=new Image();
 img.onload=()=>{{const c=document.createElement('canvas');c.width=Math.round(W*k);c.height=Math.round(H*k);
  const g=c.getContext('2d');if(type!=='image/png'){{g.fillStyle='#fff';g.fillRect(0,0,c.width,c.height);}}
  g.drawImage(img,0,0,c.width,c.height);
  c.toBlob(b=>{{const a=document.createElement('a');a.href=URL.createObjectURL(b);
   a.download='diagram.'+(type==='image/jpeg'?'jpg':type.split('/')[1]);a.click();}},type,0.95);}};
 img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(xml);
}}
fit();
</script>"""


def load_example(name: str):
    st.session_state["src"] = (HERE / "examples" / name).read_text(encoding="utf-8")


if "src" not in st.session_state:
    st.session_state["src"] = DEFAULT.read_text(encoding="utf-8") if DEFAULT.exists() else "flowchart tb\nstart A: Begin\nstop B: End\nA -> B\n"

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title(f"🔀 {NAME}")
    st.caption(f"Flow Syntax v2 · engine {flowlang.__version__}")
    st.markdown("**Turn readable process steps into clear, exportable diagrams.**")
    if EXAMPLES:
        ex = st.selectbox("Load example", ["(keep current)"] + [p.name for p in EXAMPLES])
        if ex != "(keep current)" and st.session_state.get("_last_ex") != ex:
            load_example(ex)
            st.session_state["_last_ex"] = ex
            st.rerun()
        if ex == "(keep current)":
            st.session_state["_last_ex"] = None
    up = st.file_uploader("Open .flow file", type=["flow", "txt"])
    if up is not None:
        sig = f"{up.name}:{up.size}"
        if st.session_state.get("_last_up") != sig:
            st.session_state["src"] = up.getvalue().decode("utf-8", errors="replace")
            st.session_state["_last_up"] = sig
            st.rerun()
    imports = st.file_uploader("Files for `import` (optional)", type=["flow", "txt"], accept_multiple_files=True)
    st.divider()
    st.subheader("Overrides")
    theme = st.selectbox("Theme", ["(from file)", "default", "neutral", "forest", "dark", "redux-dark"])
    style = st.selectbox("Style", ["(from file)", "classic", "neo", "hand-drawn"])
    direction = st.selectbox("Direction", ["(from file)", "tb", "lsrs"])
    share = st.selectbox("Share layout", ["(from file)", "free", "16/9", "4/5", "2/3", "1/1"])
    width = st.number_input("Export width px (0 = auto)", min_value=0, max_value=8000, value=0, step=100)
    strict = st.checkbox("Strict (warnings are errors)")
    st.divider()
    st.caption("Created by Devashrit Panda")
    st.caption("GitHub: innovatis_ignis_deva · Apache License 2.0")

st.title(f"{NAME} Flow Diagram Studio")
st.markdown(
    "Write or paste **Flow Syntax** to build process diagrams. Kurapika checks your source, "
    "automatically arranges the flow, and previews changes as you edit."
)
feature_cols = st.columns(3)
feature_cols[0].markdown("**Compose**  \nNodes, decisions, links, groups, swimlanes, and reusable templates.")
feature_cols[1].markdown("**Style & inspect**  \nChoose direction, theme, style, layout, and named views.")
feature_cols[2].markdown(
    "**Render & export**  \nExplore with zoom/pan; export SVG, JSON, Graphviz DOT, Mermaid, and PNG/JPG/WEBP."
)
st.subheader("1. Paste or edit your diagram")
src = st.text_area(
    "Flow Syntax source",
    key="src",
    height=430,
    help="Paste a .flow diagram here, or start with an example selected in the sidebar.",
    placeholder="flowchart tb\nstart A: Start\nblock B: Work\nstop C: Finish\nA -> B -> C",
)
files = {u.name: u.getvalue().decode("utf-8", errors="replace") for u in (imports or [])}
doc = flowlang.parse(src, files=files or None, strict=True if strict else None)

pick = lambda v: None if v == "(from file)" else v
views = [v.name for v in doc.views]
with st.sidebar:
    view = st.selectbox("View", views) if views else None

overrides = dict(theme=pick(theme), style=pick(style), direction=pick(direction), share_layout=pick(share),
                 export_width=int(width) or None)

col_edit, col_view = st.columns([5, 6], gap="medium")
with col_edit:
    st.subheader("2. Check your source")
    n_err, n_warn = len(doc.errors), len(doc.warnings)
    (st.error if n_err else st.success)(f"{n_err} error(s), {n_warn} warning(s)")
    for d in doc.diagnostics:
        icon = "🟥" if d.severity == "error" else "🟨"
        where = f"line {d.line}" if d.line else "file"
        st.markdown(f"{icon} **{d.code}** · {where} — {d.message}" + (f"  \n&nbsp;&nbsp;&nbsp;&nbsp;↳ _{d.hint}_" if d.hint else ""))

svg = None
lay = None
if not doc.errors:
    try:
        svg, lay = flowlang.render(doc, view=view, return_layout=True, **overrides)
    except Exception as e:  # noqa: BLE001  - never crash the page on a layout bug
        st.exception(e)

with col_view:
    st.subheader("3. Live diagram preview")
    if svg:
        for code, msg in lay.warnings:
            st.warning(f"{code}: {msg}")
        c = lay.canvas
        h = int(max(380, min(820, 560 * c["H"] / max(c["W"], 1) + 120)))
        components.html(preview_html(svg, h), height=h, scrolling=False)
    elif not doc.errors:
        st.info("Nothing to show.")
    else:
        st.info("Fix the errors on the left to see the diagram.")

if svg:
    st.subheader("Export your diagram")
    stem = (doc.header.get("title") or "diagram").lower().replace(" ", "_")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.download_button("SVG", svg, f"{stem}.svg", "image/svg+xml")
    c2.download_button("Flow source", src, f"{stem}.flow", "text/plain")
    c3.download_button("JSON", flowlang.render(doc, format="json", view=view, **overrides), f"{stem}.json", "application/json")
    c4.download_button("Graphviz DOT", flowlang.render(doc, format="dot", view=view, **overrides), f"{stem}.dot", "text/plain")
    c5.download_button("Mermaid", flowlang.render(doc, format="mermaid", view=view, **overrides), f"{stem}.mmd", "text/plain")
    try:
        import cairosvg  # noqa: F401
        d1, d2 = st.columns(2)
        d1.download_button("PNG (server)", flowlang.render(doc, format="png", view=view, **overrides), f"{stem}.png", "image/png")
        d2.download_button("PDF", flowlang.render(doc, format="pdf", view=view, **overrides), f"{stem}.pdf", "application/pdf")
    except Exception:  # noqa: BLE001
        st.caption("PNG/JPG/WEBP: use the **Download image** button above the preview. "
                   "Install `cairosvg` to also get server-side PNG and PDF.")
    with st.expander("Resolved AST (JSON)"):
        st.json(json.loads(flowlang.render(doc, format="json", view=view, **overrides)))
