"""Kurapika Flow Syntax v2 exporters: SVG, PNG, PDF, JPG, WEBP, JSON, DOT, and Mermaid."""
from __future__ import annotations

import io
import json
import re
from typing import List

from .layout import Layout
from .parser import GROUP_PREFIX
from .render import paint

FORMATS = ("svg", "png", "pdf", "jpg", "webp", "json", "dot", "mermaid")


class ExportError(RuntimeError):
    pass


def convert(lay: Layout, fmt: str):
    fmt = (fmt or "svg").lower()
    if fmt == "svg":
        return paint(lay)
    if fmt == "json":
        return to_json(lay)
    if fmt == "dot":
        return to_dot(lay)
    if fmt == "mermaid":
        return to_mermaid(lay)
    if fmt in ("png", "pdf", "jpg", "webp"):
        return rasterize(paint(lay), fmt, lay)
    raise ExportError(f"unknown format '{fmt}'")


def rasterize(svg: str, fmt: str, lay: Layout) -> bytes:
    try:
        import cairosvg
    except Exception as e:  # noqa: BLE001
        raise ExportError("png/pdf/jpg/webp export needs the cairosvg package (pip install cairosvg). "
                          "In the web app use the browser download button instead.") from e
    st = lay.settings
    bg = None if st.get("background") == "transparent" else "white"
    dpi = int(st.get("export_dpi") or 96)
    if fmt == "pdf":
        return cairosvg.svg2pdf(bytestring=svg.encode("utf-8"))
    kw = dict(bytestring=svg.encode("utf-8"), dpi=dpi)
    if st.get("export_width"):
        kw["output_width"] = int(st["export_width"])
    png = cairosvg.svg2png(**kw)
    if fmt == "png":
        return png
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    base = Image.new("RGB", im.size, (255, 255, 255))
    base.paste(im, mask=im.split()[3])
    buf = io.BytesIO()
    base.save(buf, "JPEG" if fmt == "jpg" else "WEBP", quality=92)
    return buf.getvalue()


def to_json(lay: Layout) -> str:
    d = lay.scene.doc.to_dict()
    d["layout"] = dict(
        canvas={k: v for k, v in lay.canvas.items()}, content=list(lay.content), direction=lay.direction,
        nodes={k: dict(cx=v[0], cy=v[1], w=v[2], h=v[3]) for k, v in lay.nodes.items()},
        groups={k: dict(x=v[0], y=v[1], w=v[2], h=v[3]) for k, v in lay.groups.items()},
        edges={g.id: [list(p) for p in g.pts] for g in lay.edges if g.pts},
        warnings=[dict(code=c, message=m) for c, m in lay.warnings])
    return json.dumps(d, indent=2, default=str)


# --------------------------------------------------------------------------- Mermaid
M_RESERVED = {"end", "graph", "subgraph", "flowchart", "style", "class", "classdef", "click", "default", "linkstyle"}


def _q(t: str) -> str:
    t = t.replace('"', "#quot;").replace("\n", "<br/>")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return t


def to_mermaid(lay: Layout) -> str:
    S = lay.scene
    doc = S.doc
    st = lay.settings
    lost: List[str] = []
    ids = {}
    for n in doc.nodes:
        ids[n.id] = n.id + "_1" if n.id.lower() in M_RESERVED else n.id
    gid = {g.name: "grp_" + re.sub(r"[^A-Za-z0-9_]", "_", g.name) for g in doc.groups}
    out = []
    if st["theme"] not in ("default",):
        mt = {"neutral": "neutral", "forest": "forest", "dark": "dark", "redux-dark": "dark"}.get(st["theme"])
        if mt:
            out += ["---", "config:", f"  theme: {mt}", "---"]
    if st["engine"] == "elk":
        out += ["%%{init: {\"flowchart\": {\"defaultRenderer\": \"elk\"}}}%%"]
    out.append("flowchart " + ("TB" if lay.direction == "tb" else "LR"))

    def node_line(n):
        i, t = ids[n.id], _q(n.text)
        sh = n.shape
        if sh == "start":
            return f'{i}(["{t}"])'
        if sh == "stop":
            return f'{i}(["{t}"]):::stopcls'
        if sh == "pill":
            return f'{i}("{t}")'
        if sh == "decide":
            return f'{i}{{"{t}"}}'
        if sh == "io":
            return f'{i}[/"{t}"/]'
        if sh == "manual":
            return f'{i}[/"{t}"\\]'
        if sh == "sub":
            return f'{i}[["{t}"]]'
        if sh == "db":
            return f'{i}[("{t}")]'
        if sh == "connector":
            return f'{i}(("{t}"))'
        if sh == "prepare":
            return f'{i}{{{{"{t}"}}}}'
        if sh in ("cloud", "doc", "docs", "delay"):
            return f'{i}@{{ shape: {sh}, label: "{t}" }}'
        if sh == "junction":
            return f'{i}@{{ shape: sm-circ, label: "" }}'
        if sh in ("fork", "join"):
            return f'{i}@{{ shape: fork, label: "" }}'
        if sh not in ("block",):
            lost.append(f"shape {sh} of {n.id} became a rectangle")
        return f'{i}["{t}"]'

    def emit_group(name, ind):
        g = doc.group(name)
        out.append(f'{ind}subgraph {gid[name]}["{_q(name)}"]')
        for n in doc.nodes:
            if n.group == name:
                out.append(ind + "    " + node_line(n))
        for g2 in doc.groups:
            if g2.parent == name:
                emit_group(g2.name, ind + "    ")
        out.append(ind + "end")
    for n in doc.nodes:
        if n.group is None:
            out.append("    " + node_line(n))
    for g in doc.groups:
        if g.parent is None:
            emit_group(g.name, "    ")

    def ep(x):
        return gid.get(x[len(GROUP_PREFIX):], x) if x.startswith(GROUP_PREFIX) else ids.get(x, x)
    for e in doc.edges:
        a, b = ep(e.src), ep(e.dst)
        op = {"->": "-->", "-.->": "-.->", "==>": "==>", "--": "---", "-.-": "-.-", "===": "===", "both": "<-->",
              "back": "-->", "hide": "~~~"}[e.op]
        if e.op == "back":
            a, b = b, a
        lab = f"|{_q(e.label)}|" if e.label and e.op != "hide" else ""
        out.append(f"    {a} {op}{lab} {b}")
    if any(n.shape == "stop" for n in doc.nodes):
        out.append("    classDef stopcls stroke-width:4px")
    if doc.lanes:
        lost.append("lanes are not supported by Mermaid flowcharts")
    if doc.notes:
        lost.append("attached notes are not supported")
    if doc.classes or any(n.style for n in doc.nodes):
        lost.append("custom styles were not converted")
    for l in lost:
        out.append(f"    %% lost: {l}")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- Graphviz DOT
def to_dot(lay: Layout) -> str:
    S = lay.scene
    doc = S.doc
    shape = {"block": "box", "start": "ellipse", "stop": "doublecircle", "pill": "box", "decide": "diamond",
             "io": "parallelogram", "sub": "box", "db": "cylinder", "doc": "note", "docs": "tab", "manual": "trapezium",
             "delay": "box", "connector": "circle", "prepare": "hexagon", "cloud": "ellipse", "note": "note",
             "junction": "point", "fork": "box", "join": "box", "text": "plaintext", "image": "box"}
    q = lambda s: '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    out = ["digraph G {", f"  rankdir={'TB' if lay.direction == 'tb' else 'LR'};", "  compound=true;",
           "  node [fontname=Helvetica];"]

    def style_attrs(n):
        p = S.nodes[n.id].props if n.id in S.nodes else {}
        a = []
        if p.get("fill"):
            a.append(f"style=filled, fillcolor={q(p['fill'].split(' to ')[0])}")
        if p.get("border"):
            a.append(f"color={q(p['border'])}")
        if p.get("border-width"):
            a.append(f"penwidth={p['border-width']}")
        if p.get("text-color"):
            a.append(f"fontcolor={q(p['text-color'])}")
        return a

    def nline(n, ind):
        a = [f"label={q(n.text)}", f"shape={shape.get(n.shape, 'box')}"]
        if n.shape in ("pill", "start"):
            a.append("style=rounded")
        a += [x for x in style_attrs(n) if not (n.shape in ("pill", "start") and x.startswith("style="))]
        return f"{ind}{n.id} [{', '.join(a)}];"
    firsts = {}

    def emit(name, ind):
        out.append(f"{ind}subgraph cluster_{re.sub(r'[^A-Za-z0-9_]', '_', name)} {{")
        out.append(f"{ind}  label={q(name)};")
        for n in doc.nodes:
            if n.group == name:
                out.append(nline(n, ind + "  "))
                firsts.setdefault(name, n.id)
        for g in doc.groups:
            if g.parent == name:
                emit(g.name, ind + "  ")
                firsts.setdefault(name, firsts.get(g.name))
        out.append(f"{ind}}}")
    for n in doc.nodes:
        if n.group is None:
            out.append(nline(n, "  "))
    for g in doc.groups:
        if g.parent is None:
            emit(g.name, "  ")
    for e in doc.edges:
        a = []
        src, dst = e.src, e.dst
        if src.startswith(GROUP_PREFIX):
            g = src[len(GROUP_PREFIX):]
            a.append("ltail=cluster_" + re.sub(r"[^A-Za-z0-9_]", "_", g))
            src = firsts.get(g) or src
        if dst.startswith(GROUP_PREFIX):
            g = dst[len(GROUP_PREFIX):]
            a.append("lhead=cluster_" + re.sub(r"[^A-Za-z0-9_]", "_", g))
            dst = firsts.get(g) or dst
        if e.label:
            a.append(f"label={q(e.label)}")
        if e.op in ("-.->", "-.-"):
            a.append("style=dashed")
        if e.op in ("==>", "==="):
            a.append("penwidth=3")
        if e.op in ("--", "-.-", "==="):
            a.append("dir=none")
        elif e.op == "both":
            a.append("dir=both")
        elif e.op == "back":
            a.append("dir=back")
        elif e.op == "hide":
            a.append("style=invis")
        if e.style.get("color"):
            a.append(f"color={q(e.style['color'])}")
        out.append(f"  {src} -> {dst}" + (f" [{', '.join(a)}]" if a else "") + ";")
    out.append("}")
    return "\n".join(out) + "\n"
