"""Kurapika Flow Syntax v2 measuring, scene building, layout, routing, and canvas fitting."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .parser import (GROUP_PREFIX, Document, Edge, Node, merged_props)

# --------------------------------------------------------------------------- text metrics
# Helvetica/Arial advance widths (1/1000 em) for ASCII 32..126
_H = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
      556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
      1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
      667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
      333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
      556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]


def char_w(ch: str) -> float:
    o = ord(ch)
    if 32 <= o <= 126:
        return _H[o - 32] / 1000
    if o in (9,):
        return 4 * 0.278
    if o >= 0x2E80 or 0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF:
        return 1.0 if o >= 0x2E80 else 1.15
    return 0.56


def text_width(s: str, fs: float, bold=False, mono=False) -> float:
    if mono:
        return len(s) * 0.6 * fs
    w = sum(char_w(c) for c in s) * fs
    return w * (1.07 if bold else 1.0) * 1.03     # 3 percent safety for font differences


ICONS = {"fa-ban": "\U0001F6AB", "fa-check": "✔", "fa-times": "✖", "fa-x": "✖",
         "fa-warning": "⚠", "fa-exclamation-triangle": "⚠", "fa-lock": "\U0001F512",
         "fa-unlock": "\U0001F513", "fa-user": "\U0001F464", "fa-users": "\U0001F465",
         "fa-database": "\U0001F5C4", "fa-cloud": "☁", "fa-cog": "⚙", "fa-gear": "⚙",
         "fa-envelope": "✉", "fa-mail": "✉", "fa-bell": "\U0001F514", "fa-star": "★",
         "fa-heart": "♥", "fa-home": "⌂", "fa-search": "\U0001F50D", "fa-clock": "⏱",
         "fa-flag": "⚑", "fa-play": "▶", "fa-stop": "■", "fa-pause": "⏸",
         "fa-info": "ℹ", "fa-question": "?", "fa-file": "\U0001F4C4", "fa-folder": "\U0001F4C1",
         "fa-trash": "\U0001F5D1", "fa-key": "\U0001F511", "fa-credit-card": "\U0001F4B3",
         "fa-shopping-cart": "\U0001F6D2", "fa-bolt": "⚡", "fa-rocket": "\U0001F680"}
EMOJI = {"rocket": "\U0001F680", "check": "✅", "x": "❌", "warning": "⚠️",
         "fire": "\U0001F525", "star": "⭐", "bulb": "\U0001F4A1", "lock": "\U0001F512",
         "mail": "✉️", "bug": "\U0001F41B", "gear": "⚙️", "heart": "❤️",
         "clock": "⏰", "party": "\U0001F389", "stop": "⛔", "thumbsup": "\U0001F44D"}

_INLINE = re.compile(
    r"\*\*(?=\S)(?P<b>.+?)(?<=\S)\*\*|\*(?=\S)(?P<i>[^*]+?)(?<=\S)\*|`(?P<m>[^`]+)`"
    r"|\[icon:\s*(?P<icon>[^\]]+?)\s*\]|\[emoji:\s*(?P<emoji>[^\]]+?)\s*\]|\[img:\s*(?P<img>[^\]]+?)\s*\]")


@dataclass
class Run:
    text: str
    bold: bool = False
    italic: bool = False
    mono: bool = False


def parse_inline(line: str) -> List[Run]:
    runs, pos = [], 0
    for m in _INLINE.finditer(line):
        if m.start() > pos:
            runs.append(Run(line[pos:m.start()]))
        if m.group("b") is not None:
            runs.append(Run(m.group("b"), bold=True))
        elif m.group("i") is not None:
            runs.append(Run(m.group("i"), italic=True))
        elif m.group("m") is not None:
            runs.append(Run(m.group("m"), mono=True))
        elif m.group("icon") is not None:
            runs.append(Run(ICONS.get(m.group("icon"), "●") + " "))
        elif m.group("emoji") is not None:
            runs.append(Run(EMOJI.get(m.group("emoji"), m.group("emoji")) + " "))
        else:
            runs.append(Run("\U0001F5BC "))
        pos = m.end()
    if pos < len(line):
        runs.append(Run(line[pos:]))
    return runs or [Run("")]


def run_w(r: Run, fs: float) -> float:
    return text_width(r.text, fs, r.bold, r.mono)


def line_w(runs: List[Run], fs: float) -> float:
    return sum(run_w(r, fs) for r in runs)


def wrap_text(text: str, max_w: float, fs: float, wrap=True) -> List[List[Run]]:
    """-> list of lines, each a list of Run."""
    out: List[List[Run]] = []
    for hard in text.split("\n"):
        runs = parse_inline(hard)
        if not wrap or max_w <= 0:
            out.append(runs)
            continue
        words: List[Tuple[str, Run]] = []
        for r in runs:
            for tok in re.findall(r"\s+|\S+", r.text):
                words.append((tok, r))
        cur: List[Run] = []
        cw = 0.0
        for tok, r in words:
            wtok = text_width(tok, fs, r.bold, r.mono)
            if tok.isspace():
                if cur:
                    cur.append(Run(" ", r.bold, r.italic, r.mono))
                    cw += wtok
                continue
            if cw + wtok > max_w and cur:
                while cur and cur[-1].text == " ":
                    cur.pop()
                out.append(cur)
                cur, cw = [], 0.0
            if wtok > max_w and max_w > 0:      # break very long words
                piece = ""
                for ch in tok:
                    if text_width(piece + ch, fs, r.bold, r.mono) > max_w and piece:
                        cur.append(Run(piece, r.bold, r.italic, r.mono))
                        out.append(cur)
                        cur, cw, piece = [], 0.0, ""
                    piece += ch
                tok, wtok = piece, text_width(piece, fs, r.bold, r.mono)
            cur.append(Run(tok, r.bold, r.italic, r.mono))
            cw += wtok
        while cur and cur[-1].text == " ":
            cur.pop()
        out.append(cur or [Run("")])
    return out


# --------------------------------------------------------------------------- options
@dataclass
class LayoutOptions:
    direction: str = "tb"
    font_size: float = 14
    min_w: float = 80
    max_w: float = 240
    wrap: bool = True
    rank_gap: float = 56
    node_gap: float = 40
    group_pad: float = 18
    padx: float = 14
    pady: float = 10
    edge_style: str = "curved"
    corner: float = 6
    label_size: float = 12
    arrow: float = 8
    line_h: float = 1.25
    lane_header: float = 30
    grid: Optional[float] = None
    engine: str = "dagre"


# --------------------------------------------------------------------------- scene
@dataclass
class SNode:
    id: str
    shape: str
    text: str
    props: dict
    path: Tuple[str, ...] = ()
    lane: Optional[str] = None
    kind: str = "node"               # node | proxy | note
    orig: Optional[Node] = None
    lines: List[List[Run]] = field(default_factory=list)
    w: float = 0
    h: float = 0
    fs: float = 14
    decl: int = 0
    attach: List[str] = field(default_factory=list)


@dataclass
class SEdge:
    id: str
    src: str
    dst: str
    orig: Optional[Edge]
    op: str = "->"
    label: Optional[str] = None
    lines: List[List[Run]] = field(default_factory=list)
    lw: float = 0
    lh: float = 0
    props: dict = field(default_factory=dict)
    len: float = 1
    weight: float = 1
    constraint: bool = True
    hidden: bool = False
    note_conn: bool = False
    src_port: Optional[str] = None
    dst_port: Optional[str] = None
    decl: int = 0


@dataclass
class SGroup:
    name: str
    parent: Optional[str]
    path: Tuple[str, ...]
    direction: Optional[str]
    props: dict
    decl: int = 0
    title_lines: List[List[Run]] = field(default_factory=list)


@dataclass
class Scene:
    doc: Document
    opts: LayoutOptions
    direction: str
    nodes: Dict[str, SNode] = field(default_factory=dict)
    edges: List[SEdge] = field(default_factory=list)
    groups: Dict[str, SGroup] = field(default_factory=dict)
    lanes: List[str] = field(default_factory=list)
    lane_props: Dict[str, dict] = field(default_factory=dict)
    same_rank: List[List[str]] = field(default_factory=list)
    order: List[List[str]] = field(default_factory=list)
    layer_of: Dict[str, str] = field(default_factory=dict)


def _group_path(doc: Document, name: Optional[str]) -> Tuple[str, ...]:
    chain = []
    while name:
        chain.append(name)
        g = doc.group(name)
        name = g.parent if g else None
    return tuple(reversed(chain))


def _members_deep(doc: Document, gname: str) -> List[str]:
    return [n.id for n in doc.nodes if gname in _group_path(doc, n.group)]


def select_view(doc: Document, view_name: Optional[str]):
    """-> (visible_node_ids, collapsed_group_names, overrides dict)"""
    vis = {n.id for n in doc.nodes}
    collapsed = {g.name for g in doc.groups if g.collapsed}
    over = {}
    view = next((v for v in doc.views if v.name == view_name), None) if view_name else None
    if view is None:
        return vis, collapsed, over
    over = dict(view.overrides)

    def match(kind, val):
        if kind == "tag":
            return {n.id for n in doc.nodes if val in n.tags}
        if kind == "layer":
            return set(doc.layers.get(val, []))
        if kind == "node":
            return {val}
        if kind == "group":
            return set(_members_deep(doc, val))
        return set()
    if any(r[0] == "show" for r in view.rules):
        vis = set()
        for act, kind, val, _ in view.rules:
            if act == "show":
                vis |= match(kind, val)
    for act, kind, val, _ in view.rules:
        if act == "hide":
            vis -= match(kind, val)
        elif act == "collapse":
            collapsed.add(val)
        elif act == "expand":
            collapsed.discard(val)
    return vis, collapsed, over


def measure_node(sn: SNode, opts: LayoutOptions, direction: str, deg: int = 0):
    p = sn.props
    fs = float(p.get("font-size", opts.font_size))
    sn.fs = fs
    shape = sn.shape
    wrap_w = opts.max_w - 2 * opts.padx
    bold = bool(p.get("bold"))
    text = sn.text
    if p.get("icon") and shape not in ("junction", "fork", "join"):
        text = f"[icon: {p['icon']}] {text}"
    if bold and "**" not in text:
        text = "\n".join(f"**{t}**" if t.strip() else t for t in text.split("\n"))
    lines = wrap_text(text, wrap_w, fs, opts.wrap) if text != "" else []
    sn.lines = lines
    tw = max((line_w(l, fs) for l in lines), default=0.0)
    th = len(lines) * fs * opts.line_h if lines else 0.0
    px, py = opts.padx, opts.pady
    if shape in ("junction",):
        w = h = 10.0
    elif shape in ("fork", "join"):
        length = max(70.0, 26.0 * max(deg, 2))
        w, h = (length, 8.0) if direction == "tb" else (8.0, length)
    elif shape == "connector":
        d = max(tw, th) + 18
        w = h = max(d, 30.0)
    elif shape == "text":
        w, h = tw + 6, th + 4
    elif shape == "image":
        w, h = 120.0, 90.0
        if lines:
            h += th + 6
            w = max(w, tw + 16)
    else:
        bw = max(tw + 2 * px, opts.min_w)
        bh = max(th + 2 * py, 34.0)
        w, h = min(bw, max(opts.max_w, tw + 2 * px)), bh
        if shape == "decide":
            w, h = 1.6 * bw, 1.6 * bh
            while tw / w + th / h > 0.9:
                w, h = w * 1.08, h * 1.08
        elif shape in ("io", "manual"):
            w += 28
        elif shape == "prepare":
            w += 24
        elif shape == "delay":
            w += bh / 2
        elif shape == "db":
            h += 16
        elif shape == "cloud":
            w, h = w * 1.25, h * 1.35
        elif shape == "docs":
            w, h = w + 8, h + 8
        elif shape in ("start", "stop"):
            w += 10
        elif shape == "doc":
            h += 8
    if "width" in p:
        w = float(p["width"])
    if "height" in p:
        h = float(p["height"])
    sn.w, sn.h = w, h


def build_scene(doc: Document, view: Optional[str] = None, opts: Optional[LayoutOptions] = None,
                direction: Optional[str] = None) -> Scene:
    opts = opts or LayoutOptions()
    vis, collapsed, over = select_view(doc, view)
    direction = direction or over.get("direction") or doc.direction
    scene = Scene(doc, opts, direction)
    opts.direction = direction
    node_of = {n.id: n for n in doc.nodes}

    # collapsed groups: outermost collapsed ancestor wins
    def collapsed_root(n: Node) -> Optional[str]:
        for gname in _group_path(doc, n.group):
            if gname in collapsed:
                return gname
        return None

    # visible groups (any visible member, directly or nested)
    shown_groups = set()
    for n in doc.nodes:
        if n.id in vis:
            for gname in _group_path(doc, n.group):
                shown_groups.add(gname)
                if gname in collapsed:
                    break
    decl = 0
    for g in doc.groups:
        if g.name in shown_groups:
            path = _group_path(doc, g.name)[:-1]
            if any(a in collapsed for a in path):
                continue
            if g.name in collapsed:
                sn = SNode(GROUP_PREFIX + g.name, "collapsed", g.name, {**merged_props(doc, g), "_group": True},
                           path=path, kind="proxy", decl=decl)
                scene.nodes[sn.id] = sn
            else:
                sg = SGroup(g.name, g.parent, path, g.direction, merged_props(doc, g), decl=decl)
                scene.groups[g.name] = sg
        decl += 1
    base_decl = decl
    deg = {}
    for e in doc.edges:
        for ep in (e.src, e.dst):
            deg[ep] = deg.get(ep, 0) + 1
    lane_names = [l.name for l in doc.lanes]
    for i, n in enumerate(doc.nodes):
        if n.id not in vis or collapsed_root(n):
            continue
        props = merged_props(doc, n, n.shape)
        sn = SNode(n.id, n.shape, n.text, props, path=_group_path(doc, n.group), lane=n.lane,
                   orig=n, decl=base_decl + i)
        measure_node(sn, opts, direction, deg.get(n.id, 0))
        scene.nodes[sn.id] = sn
    for sn in scene.nodes.values():
        if sn.kind == "proxy":
            fs = opts.font_size
            sn.lines = wrap_text(sn.text, opts.max_w - 2 * opts.padx, fs, True)
            tw = max(line_w(l, fs) for l in sn.lines)
            sn.w = max(tw + 2 * opts.padx + 16, opts.min_w)
            sn.h = len(sn.lines) * fs * opts.line_h + 2 * opts.pady + 8
            sn.fs = fs
            gl = doc.group(sn.id[len(GROUP_PREFIX):])
            sn.lane = gl.lane if gl else None
    for sg in scene.groups.values():
        sg.title_lines = wrap_text(sg.name, 400, 12, False)
    scene.lanes = [l for l in lane_names if any(s.lane == l for s in scene.nodes.values())]
    for l in doc.lanes:
        if l.name in scene.lanes:
            scene.lane_props[l.name] = merged_props(doc, l)

    def map_ep(ep: str) -> Optional[str]:
        if ep.startswith(GROUP_PREFIX):
            gname = ep[len(GROUP_PREFIX):]
            if gname in collapsed and (GROUP_PREFIX + gname) in scene.nodes:
                return GROUP_PREFIX + gname
            if gname in scene.groups:
                return ep
            for a in _group_path(doc, doc.group(gname).parent if doc.group(gname) else None):
                if a in collapsed and (GROUP_PREFIX + a) in scene.nodes:
                    return GROUP_PREFIX + a
            return None
        n = node_of.get(ep)
        if n is None or n.id not in vis:
            return None
        r = collapsed_root(n)
        if r:
            return GROUP_PREFIX + r
        return ep if ep in scene.nodes else None
    for k, e in enumerate(doc.edges):
        a, b = map_ep(e.src), map_ep(e.dst)
        if a is None or b is None:
            continue
        if a == b and not (e.src == e.dst):
            continue
        props = merged_props(doc, e)
        se = SEdge(e.id, a, b, e, e.op, e.label, props=props, len=max(1, e.len), weight=max(0.01, e.weight),
                   hidden=(e.op == "hide"), src_port=e.src_port, dst_port=e.dst_port, decl=k)
        if e.label:
            ls = float(props.get("label-size", opts.label_size))
            se.lines = wrap_text(e.label, 160, ls, True)
            se.lw = max(line_w(l, ls) for l in se.lines) + 10
            se.lh = len(se.lines) * ls * opts.line_h + 6
        scene.edges.append(se)
    # notes become pseudo nodes beside their first target
    for k, note in enumerate(doc.notes):
        tid = note.targets[-1] if note.kind == "over" else note.targets[0]
        tn = scene.nodes.get(tid)
        if tn is None:
            continue
        nid = f"note:{k}"
        sn = SNode(nid, "note", note.text, {"font-size": 12}, path=tn.path, lane=tn.lane, kind="note",
                   decl=10_000 + k, attach=list(note.targets))
        measure_node(sn, opts, direction)
        scene.nodes[nid] = sn
        scene.same_rank.append([tid, nid])
        scene.order.append([nid, tid] if note.kind == "left" else [tid, nid])
        for t in note.targets:
            if t in scene.nodes:
                scene.edges.append(SEdge(f"{nid}-{t}", nid, t, None, op="--", constraint=False,
                                         note_conn=True, props={"dash": True}, decl=10_000 + k))
    c = doc.constraints
    for grp in c.get("same_rank", []):
        g = [x for x in grp if x in scene.nodes]
        if len(g) > 1:
            scene.same_rank.append(g)
    for grp in c.get("order", []):
        g = [x for x in grp if x in scene.nodes]
        if len(g) > 1:
            scene.order.append(g)
    for lname, ids in doc.layers.items():
        for i in ids:
            scene.layer_of[i] = lname
    return scene


# --------------------------------------------------------------------------- geometry helpers
Pt = Tuple[float, float]
K = 0.5522847498


def fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def path_d(cmds, dx: float = 0.0, dy: float = 0.0) -> str:
    out = []
    for c in cmds:
        op = c[0]
        if op == "Z":
            out.append("Z")
            continue
        nums = c[1:]
        vals = [fmt(v + (dx if i % 2 == 0 else dy)) for i, v in enumerate(nums)]
        out.append(op + " ".join(vals))
    return " ".join(out)


def flatten(cmds, steps: int = 14) -> List[List[Pt]]:
    """Path commands -> list of polylines (one per subpath)."""
    subs: List[List[Pt]] = []
    cur: List[Pt] = []
    p: Pt = (0.0, 0.0)
    start: Pt = (0.0, 0.0)
    for c in cmds:
        op = c[0]
        if op == "M":
            if cur:
                subs.append(cur)
            p = start = (c[1], c[2])
            cur = [p]
        elif op == "L":
            p = (c[1], c[2])
            cur.append(p)
        elif op == "C":
            p0, p1, p2, p3 = p, (c[1], c[2]), (c[3], c[4]), (c[5], c[6])
            for i in range(1, steps + 1):
                t = i / steps
                u = 1 - t
                cur.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                            u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
            p = p3
        elif op == "Q":
            p0, p1, p2 = p, (c[1], c[2]), (c[3], c[4])
            for i in range(1, steps + 1):
                t = i / steps
                u = 1 - t
                cur.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
            p = p2
        elif op == "Z":
            if cur:
                cur.append(start)
                subs.append(cur)
                cur = []
            p = start
    if cur:
        subs.append(cur)
    return subs


def poly_len(pts: List[Pt]) -> float:
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def point_at(pts: List[Pt], frac: float) -> Tuple[Pt, Pt]:
    """Point and unit tangent at a length fraction of a polyline."""
    total = poly_len(pts)
    if total == 0:
        return pts[0], (0.0, 1.0)
    target, acc = frac * total, 0.0
    for i in range(len(pts) - 1):
        seg = math.dist(pts[i], pts[i + 1])
        if acc + seg >= target and seg > 0:
            t = (target - acc) / seg
            dx, dy = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
            return (pts[i][0] + dx * t, pts[i][1] + dy * t), (dx / seg, dy / seg)
        acc += seg
    dx, dy = pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]
    n = math.hypot(dx, dy) or 1
    return pts[-1], (dx / n, dy / n)


def round_rect_cmds(hw, hh, r, cx=0.0, cy=0.0):
    r = max(0.0, min(r, hw, hh))
    x0, x1, y0, y1 = cx - hw, cx + hw, cy - hh, cy + hh
    k = r * (1 - K)
    return [("M", x0 + r, y0), ("L", x1 - r, y0), ("C", x1 - k, y0, x1, y0 + k, x1, y0 + r),
            ("L", x1, y1 - r), ("C", x1, y1 - k, x1 - k, y1, x1 - r, y1), ("L", x0 + r, y1),
            ("C", x0 + k, y1, x0, y1 - k, x0, y1 - r), ("L", x0, y0 + r),
            ("C", x0, y0 + k, x0 + k, y0, x0 + r, y0), ("Z",)]


def ellipse_cmds(rx, ry, cx=0.0, cy=0.0):
    return [("M", cx - rx, cy), ("C", cx - rx, cy - K * ry, cx - K * rx, cy - ry, cx, cy - ry),
            ("C", cx + K * rx, cy - ry, cx + rx, cy - K * ry, cx + rx, cy),
            ("C", cx + rx, cy + K * ry, cx + K * rx, cy + ry, cx, cy + ry),
            ("C", cx - K * rx, cy + ry, cx - rx, cy + K * ry, cx - rx, cy), ("Z",)]


def outline_polygon(shape: str, w: float, h: float) -> List[Pt]:
    """Approximate outline (centered at 0,0) used for anchoring edges."""
    hw, hh = w / 2, h / 2
    if shape == "decide":
        return [(0, -hh), (hw, 0), (0, hh), (-hw, 0)]
    if shape in ("connector", "junction", "cloud"):
        return [(hw * math.cos(a * math.pi / 12), hh * math.sin(a * math.pi / 12)) for a in range(24)]
    if shape in ("start", "stop", "pill", "delay"):
        r = hh if shape != "pill" else min(hh, 14)
        pts = []
        for corner, (cx, cy, a0) in enumerate(((hw - r, -hh + r, -90), (hw - r, hh - r, 0),
                                               (-hw + r, hh - r, 90), (-hw + r, -hh + r, 180))):
            if shape == "delay" and corner >= 2:
                pts.append((-hw, cy + (r if corner == 2 else -r)))
                continue
            for k in range(7):
                a = math.radians(a0 + 15 * k)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return pts
    if shape == "io":
        s = min(hh * 0.6, 18)
        return [(-hw + s, -hh), (hw, -hh), (hw - s, hh), (-hw, hh)]
    if shape == "manual":
        s = min(14, hw * 0.2)
        return [(-hw, -hh), (hw, -hh), (hw - s, hh), (-hw + s, hh)]
    if shape == "prepare":
        s = min(18, hw * 0.25)
        return [(-hw + s, -hh), (hw - s, -hh), (hw, 0), (hw - s, hh), (-hw + s, hh), (-hw, 0)]
    return [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]


def ray_poly(origin: Pt, d: Pt, poly: List[Pt], center: Pt) -> Pt:
    """Farthest intersection of the ray origin + t*d (t>=0) with a polygon placed at center."""
    best = None
    n = len(poly)
    ox, oy = origin
    for i in range(n):
        x1, y1 = poly[i][0] + center[0], poly[i][1] + center[1]
        x2, y2 = poly[(i + 1) % n][0] + center[0], poly[(i + 1) % n][1] + center[1]
        ex, ey = x2 - x1, y2 - y1
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-12:
            continue
        t = ((x1 - ox) * ey - (y1 - oy) * ex) / den
        u = ((x1 - ox) * d[1] - (y1 - oy) * d[0]) / den
        if t >= -1e-9 and -1e-9 <= u <= 1 + 1e-9:
            if best is None or t > best:
                best = t
    if best is None:
        return center
    return (ox + d[0] * best, oy + d[1] * best)


def unit(v: Pt) -> Pt:
    n = math.hypot(v[0], v[1])
    return (v[0] / n, v[1] / n) if n else (0.0, 1.0)


# --- path builders (points + tangents) ---------------------------------------------------
def bezier_through(points: List[Pt], tin: List[Pt], tout: List[Pt]):
    cmds = [("M", *points[0])]
    for i in range(len(points) - 1):
        P, Q = points[i], points[i + 1]
        t0, t1 = tout[i], tin[i + 1]
        dist = math.dist(P, Q)
        d1 = abs((Q[0] - P[0]) * t0[0] + (Q[1] - P[1]) * t0[1]) * 0.5
        d2 = abs((Q[0] - P[0]) * t1[0] + (Q[1] - P[1]) * t1[1]) * 0.5
        d1 = max(d1, min(10.0, dist * 0.4))
        d2 = max(d2, min(10.0, dist * 0.4))
        cmds.append(("C", P[0] + t0[0] * d1, P[1] + t0[1] * d1, Q[0] - t1[0] * d2, Q[1] - t1[1] * d2, *Q))
    return cmds


def polyline_cmds(points: List[Pt], radius: float = 0.0):
    pts = [points[0]]
    for p in points[1:]:
        if math.dist(p, pts[-1]) > 1e-6:
            pts.append(p)
    # drop collinear points
    clean = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = clean[-1], pts[i], pts[i + 1]
        if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) > 1e-6:
            clean.append(b)
    clean.append(pts[-1])
    pts = clean
    if len(pts) < 2:
        return [("M", *pts[0]), ("L", *pts[0])]
    cmds = [("M", *pts[0])]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        r = min(radius, math.dist(a, b) / 2, math.dist(b, c) / 2)
        if r < 0.5:
            cmds.append(("L", *b))
            continue
        ua, uc = unit((a[0] - b[0], a[1] - b[1])), unit((c[0] - b[0], c[1] - b[1]))
        p1 = (b[0] + ua[0] * r, b[1] + ua[1] * r)
        p2 = (b[0] + uc[0] * r, b[1] + uc[1] * r)
        cmds += [("L", *p1), ("Q", b[0], b[1], *p2)]
    cmds.append(("L", *pts[-1]))
    return cmds


def ortho_points(points: List[Pt], tin: List[Pt], tout: List[Pt]) -> List[Pt]:
    def ax(t):
        return "h" if abs(t[0]) > abs(t[1]) else "v"
    pts = [points[0]]
    for i in range(len(points) - 1):
        P, Q = points[i], points[i + 1]
        a, b = ax(tout[i]), ax(tin[i + 1])
        if a == "v" and b == "v":
            my = (P[1] + Q[1]) / 2
            pts += [(P[0], my), (Q[0], my)]
        elif a == "h" and b == "h":
            mx = (P[0] + Q[0]) / 2
            pts += [(mx, P[1]), (mx, Q[1])]
        elif a == "h":
            pts.append((Q[0], P[1]))
        else:
            pts.append((P[0], Q[1]))
        pts.append(Q)
    return pts


def catmull_cmds(points: List[Pt]):
    if len(points) == 2:
        return [("M", *points[0]), ("L", *points[1])]
    cmds = [("M", *points[0])]
    n = len(points)
    for i in range(n - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < n else points[i + 1]
        cmds.append(("C", p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6,
                     p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, *p2))
    return cmds


def trim_path(cmds, start: float, end: float, t_start: Pt, t_end: Pt):
    """Shorten a path at both ends (to make room for arrowheads)."""
    cmds = [list(c) for c in cmds]
    if start > 0 and len(cmds) > 1:
        c0, c1 = cmds[0], cmds[1]
        dx, dy = t_start[0] * start, t_start[1] * start
        c0[1] += dx
        c0[2] += dy
        if c1[0] == "C":
            c1[1] += dx
            c1[2] += dy
    if end > 0 and len(cmds) > 1:
        last = cmds[-1]
        dx, dy = -t_end[0] * end, -t_end[1] * end
        if last[0] == "C":
            last[3] += dx
            last[4] += dy
            last[5] += dx
            last[6] += dy
        elif last[0] == "Q":
            last[3] += dx
            last[4] += dy
        elif last[0] == "L":
            last[1] += dx
            last[2] += dy
    return [tuple(c) for c in cmds]


# --------------------------------------------------------------------------- settings
def resolve_settings(doc: Document, view: Optional[str] = None, overrides: Optional[dict] = None) -> dict:
    """Merge defaults, header options, devas options, the view and caller overrides."""
    from .parser import DEVAS
    h = doc.header
    dv = h.get("devas", {})
    S = {k: dv.get(k, spec[2]) for k, spec in DEVAS.items()}
    style = h.get("style", "classic")
    S.update(
        theme=h.get("theme", "default"), style=style, engine=h.get("engine", "dagre"),
        font=h.get("font"), font_size=float(h.get("font-size", 14)),
        corner_radius=float(h.get("corner-radius", 10 if style == "neo" else 6)),
        line_width=float(h.get("line-width", 1.5)), arrow_size=float(h.get("arrow-size", 8)),
        shadow=bool(h.get("shadow", style == "neo")),
        gradient=bool(h.get("gradient", style == "neo")), border_color=h.get("border-color"),
        roughness=float(h.get("roughness", 1)), mode=h.get("mode", "normal"),
        direction=doc.direction, title=h.get("title"), subtitle=h.get("subtitle"),
        caption=h.get("caption"), footer=h.get("footer"))
    v = next((x for x in doc.views if x.name == view), None) if view else None
    if v is not None:
        for k, val in v.overrides.items():
            S[k] = val
    for k, val in (overrides or {}).items():
        if val is not None:
            S[k] = val
    if S.get("transparent"):
        S["background"] = "transparent"
    u = 96 / 72 if S.get("units") == "pt" else 1.0
    if u != 1.0:
        for k in ("padding", "max_width", "max_height", "min_node_width", "max_node_width",
                  "rank_gap", "node_gap"):
            if S.get(k) is not None:
                S[k] = float(S[k]) * u
        m = S.get("share_margin")
        if isinstance(m, (int, float)) or (isinstance(m, str) and not m.endswith("%")):
            S["share_margin"] = str(float(m) * u)
    sp = doc.constraints.get("spacing", {})
    if "rank" in sp:
        S["rank_gap"] = sp["rank"]
    if "node" in sp:
        S["node_gap"] = sp["node"]
    S["group_pad"] = sp.get("group", 18)
    return S


def layout_options(S: dict) -> LayoutOptions:
    compact = S.get("mode") == "compact"
    k = 0.7 if compact else 1.0
    return LayoutOptions(
        direction=S["direction"], font_size=S["font_size"], min_w=float(S["min_node_width"]),
        max_w=float(S["max_node_width"]), wrap=bool(S["wrap_text"]),
        rank_gap=float(S["rank_gap"]) * k, node_gap=float(S["node_gap"]) * k,
        group_pad=float(S["group_pad"]) * (0.8 if compact else 1.0), padx=10 if compact else 14,
        pady=6 if compact else 10, edge_style=S["edge_style"], corner=6.0,
        arrow=S["arrow_size"], grid=S.get("grid"), engine=S["engine"])


# --------------------------------------------------------------------------- layered layout
GAP_DUMMY = 14.0
GAP_MIXED = 20.0
GAP_NOTE = 24.0
LOOP = 26.0
LANE_PAD = 22.0
GROUP_TITLE_H = 24.0


@dataclass
class V:
    i: int
    item: Optional[str]
    a: float = 0.0           # size on the cross axis (tb: width)
    r: float = 0.0           # size on the rank axis  (tb: height)
    rank: int = 0
    lane: int = 0
    key: float = 0.0
    dummy: bool = False
    off: float = 0.0         # item centre offset from vertex centre (room for self loops)
    pos: float = 0.0
    ry: float = 0.0
    pull: Optional[tuple] = None    # (anchor vertex, side) for notes


@dataclass
class LevelResult:
    path: Tuple[str, ...]
    direction: str
    size: Tuple[float, float] = (0.0, 0.0)
    pos: Dict[str, Pt] = field(default_factory=dict)
    dims: Dict[str, Pt] = field(default_factory=dict)
    wps: Dict[int, List[Pt]] = field(default_factory=dict)
    label_at: Dict[int, Pt] = field(default_factory=dict)
    flat: set = field(default_factory=set)
    back: set = field(default_factory=set)
    loops: Dict[int, int] = field(default_factory=dict)
    lanes: List[dict] = field(default_factory=list)


class Ctx:
    def __init__(self, S: Scene):
        self.S = S
        self.levels: Dict[tuple, LevelResult] = {}
        self.children: Dict[tuple, List[str]] = {}
        self.ikey: Dict[str, float] = {}
        self.level_edges: Dict[tuple, List[tuple]] = {}
        self.gmeta: Dict[str, tuple] = {}
        self.gdir: Dict[str, str] = {}
        self.warnings: List[Tuple[str, str]] = []
        self.skipped: set = set()
        self.edge_loc: Dict[int, tuple] = {}
        doc = S.doc
        for sn in S.nodes.values():
            self.children.setdefault(sn.path, []).append(sn.id)
            if sn.kind == "note":
                self.ikey[sn.id] = 100000.0 + sn.decl
            elif sn.kind == "proxy":
                g = doc.group(sn.id[len(GROUP_PREFIX):])
                self.ikey[sn.id] = float(g.line) if g else 0.0
            else:
                self.ikey[sn.id] = float(sn.orig.line if sn.orig else 0) + sn.decl * 1e-6
        for name, sg in S.groups.items():
            gid = GROUP_PREFIX + name
            self.children.setdefault(sg.path, []).append(gid)
            g = doc.group(name)
            self.ikey[gid] = float(g.line) if g else 0.0
        self.assign_edges()

    def anc(self, ep: str) -> Optional[tuple]:
        S = self.S
        if ep in S.nodes:
            return S.nodes[ep].path
        if ep.startswith(GROUP_PREFIX) and ep[len(GROUP_PREFIX):] in S.groups:
            return S.groups[ep[len(GROUP_PREFIX):]].path
        return None

    def assign_edges(self):
        for k, e in enumerate(self.S.edges):
            pa, pb = self.anc(e.src), self.anc(e.dst)
            if pa is None or pb is None:
                self.skipped.add(k)
                continue
            n = 0
            while n < len(pa) and n < len(pb) and pa[n] == pb[n]:
                n += 1
            ra = GROUP_PREFIX + pa[n] if len(pa) > n else e.src
            rb = GROUP_PREFIX + pb[n] if len(pb) > n else e.dst
            if ra == rb and e.src != e.dst:
                self.skipped.add(k)
                self.warnings.append(("W090", f"edge {e.src} to {e.dst} joins an item with its own group and is not drawn"))
                continue
            self.level_edges.setdefault(pa[:n], []).append((k, ra, rb))
            self.edge_loc[k] = (pa[:n], ra, rb)


def _pav(desired: List[float], weights: List[float], seps: List[float]) -> List[float]:
    """Least squares placement with minimum separations (pool adjacent violators)."""
    n = len(desired)
    off = [0.0] * n
    for i in range(1, n):
        off[i] = off[i - 1] + seps[i - 1]
    blocks: List[list] = []
    for i in range(n):
        w = max(weights[i], 1e-6)
        blocks.append([w * (desired[i] - off[i]), w, i, i])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            b = blocks.pop()
            a = blocks[-1]
            a[0] += b[0]
            a[1] += b[1]
            a[3] = b[3]
    x = [0.0] * n
    for sw, w, s, e in blocks:
        m = sw / w
        for i in range(s, e + 1):
            x[i] = m + off[i]
    return x


def _count_crossings(pairs: List[Tuple[int, int]]) -> int:
    """Number of crossings among segments between two layers; pairs are (upper pos, lower pos)."""
    if len(pairs) < 2:
        return 0
    pairs = sorted(pairs)
    lows = sorted({b for _, b in pairs})
    rank = {v: i + 1 for i, v in enumerate(lows)}
    tree = [0] * (len(lows) + 2)
    total = 0
    seen = 0
    for _, b in pairs:
        r = rank[b]
        i, s = r, 0
        while i > 0:
            s += tree[i]
            i -= i & -i
        total += seen - s
        i = r
        while i < len(tree):
            tree[i] += 1
            i += i & -i
        seen += 1
    return total


def layout_level(S: Scene, path: tuple, direction: str, ctx: Ctx) -> LevelResult:
    opts = S.opts
    tb = direction == "tb"
    res = LevelResult(path, direction)
    items = sorted(ctx.children.get(path, []), key=lambda i: ctx.ikey[i])
    dims: Dict[str, Pt] = {}
    for it in items:
        if it not in S.nodes and it.startswith(GROUP_PREFIX):
            dims[it] = group_dims(S, it[len(GROUP_PREFIX):], direction, ctx)
        else:
            dims[it] = (S.nodes[it].w, S.nodes[it].h)
    res.dims = dict(dims)
    if not items:
        return res
    lanes_on = path == () and bool(S.lanes)
    lane_idx = {n: i for i, n in enumerate(S.lanes)}
    n_lane_slots = len(S.lanes) + 1

    def lane_of(it: str) -> int:
        if not lanes_on:
            return 0
        if it in S.nodes:
            ln = S.nodes[it].lane
        else:
            g = S.doc.group(it[len(GROUP_PREFIX):])
            ln = g.lane if g else None
        return lane_idx.get(ln, len(S.lanes))

    verts: List[V] = []
    vid: Dict[str, int] = {}
    for it in items:
        w, h = dims[it]
        a, r = (w, h) if tb else (h, w)
        v = V(len(verts), it, a=a, r=r, key=ctx.ikey[it], lane=lane_of(it))
        verts.append(v)
        vid[it] = v.i

    ledges = ctx.level_edges.get(path, [])
    # self loops reserve room beside the node
    for k, ra, rb in ledges:
        if ra == rb:
            e = S.edges[k]
            cnt = res.loops.get(vid[ra], 0)
            res.loops[vid[ra]] = cnt + 1
            lab = (e.lw if tb else e.lh) if e.label else 0.0
            extra = LOOP + 12 * cnt + lab
            v = verts[vid[ra]]
            if extra > -v.off * 2:
                v.a += extra - (-v.off * 2)
                v.off = -extra / 2

    # note anchors
    note_side: Dict[str, Tuple[str, str]] = {}
    for grp in S.order:
        if len(grp) == 2 and grp[0].startswith("note:") and grp[0] in vid:
            note_side[grp[0]] = (grp[1], "left")
        elif len(grp) == 2 and grp[1].startswith("note:") and grp[1] in vid:
            note_side[grp[1]] = (grp[0], "right")
    for nid, (anchor, side) in note_side.items():
        if anchor in vid:
            verts[vid[nid]].pull = (vid[anchor], side)

    # same-rank sets
    parent = list(range(len(verts)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for grp in S.same_rank:
        present = [g for g in grp if g in S.nodes]
        ids = [vid[g] for g in present if g in vid]
        if len(ids) < len(present):
            ctx.warnings.append(("W093", "same rank ignored for nodes that sit in different groups: " + ", ".join(present)))
        for x in ids[1:]:
            parent[find(x)] = find(ids[0])

    # constraint edges
    cedges: List[dict] = []
    for k, ra, rb in ledges:
        e = S.edges[k]
        if ra == rb or not e.constraint:
            if ra != rb:
                res.flat.add(k)
            continue
        u, v = vid[ra], vid[rb]
        if find(u) == find(v):
            res.flat.add(k)
            continue
        cedges.append(dict(k=k, u=u, v=v, minlen=2 * max(1, int(round(e.len))), weight=e.weight, rev=False))

    roots = sorted({find(v.i) for v in verts}, key=lambda r: min(verts[m.i].key for m in verts if find(m.i) == r))
    rkey = {r: min(verts[m.i].key for m in verts if find(m.i) == r) for r in roots}
    adj: Dict[int, list] = {r: [] for r in roots}
    has_in = {r: False for r in roots}
    for ci, ce in enumerate(cedges):
        adj[find(ce["u"])].append((find(ce["v"]), ci))
        has_in[find(ce["v"])] = True
    color: Dict[int, int] = {}
    for start in sorted(roots, key=lambda r: (has_in[r], rkey[r])):
        if color.get(start):
            continue
        color[start] = 1
        stack = [(start, iter(adj[start]))]
        while stack:
            u, it = stack[-1]
            moved = False
            for w, ci in it:
                c = color.get(w, 0)
                if c == 0:
                    color[w] = 1
                    stack.append((w, iter(adj[w])))
                    moved = True
                    break
                if c == 1:
                    cedges[ci]["rev"] = True
            if not moved:
                color[u] = 2
                stack.pop()

    outs: Dict[int, list] = {r: [] for r in roots}
    indeg = {r: 0 for r in roots}
    for ce in cedges:
        u, v = (ce["v"], ce["u"]) if ce["rev"] else (ce["u"], ce["v"])
        ce["ou"], ce["ov"] = u, v
        outs[find(u)].append((find(v), ce))
        indeg[find(v)] += 1
    has_in = {r: indeg[r] > 0 for r in roots}
    import heapq
    heap = [(rkey[r], r) for r in roots if indeg[r] == 0]
    heapq.heapify(heap)
    rank = {r: 0 for r in roots}
    topo = []
    while heap:
        _, u = heapq.heappop(heap)
        topo.append(u)
        for w, ce in outs[u]:
            rank[w] = max(rank[w], rank[u] + ce["minlen"])
            indeg[w] -= 1
            if indeg[w] == 0:
                heapq.heappush(heap, (rkey[w], w))
    for u in reversed(topo):
        if not has_in[u] and outs[u]:
            rank[u] = min(rank[w] - ce["minlen"] for w, ce in outs[u])
    base = min(rank.values())
    for v in verts:
        v.rank = rank[find(v.i)] - base

    # dummy chains
    segs: List[Tuple[int, int, float]] = []
    chains: Dict[int, list] = {}
    rev_of: Dict[int, bool] = {}
    label_v: Dict[int, int] = {}
    for ce in sorted(cedges, key=lambda c: c["k"]):
        e = S.edges[ce["k"]]
        u, v = ce["ou"], ce["ov"]
        n = verts[v].rank - verts[u].rank - 1
        chain = [u]
        for j in range(n):
            d = V(len(verts), None, dummy=True, rank=verts[u].rank + 1 + j, key=verts[u].key)
            if lanes_on:
                lu, lv = verts[u].lane, verts[v].lane
                d.lane = int(round(lu + (lv - lu) * (j + 1) / (n + 1)))
            else:
                d.lane = 0
            verts.append(d)
            chain.append(d.i)
        chain.append(v)
        if e.label and n:
            m = chain[1 + n // 2]
            verts[m].a = (e.lw if tb else e.lh) + 6
            verts[m].r = e.lh if tb else e.lw
            label_v[ce["k"]] = m
        for x, y in zip(chain, chain[1:]):
            both_real = not verts[x].dummy and not verts[y].dummy
            both_dummy = verts[x].dummy and verts[y].dummy
            segs.append((x, y, ce["weight"] * (1 if both_real else (8 if both_dummy else (2 if n == 1 else 1)))))
        chains[ce["k"]] = chain
        rev_of[ce["k"]] = ce["rev"]
        if ce["rev"]:
            res.back.add(ce["k"])

    maxrank = max(v.rank for v in verts)
    layers: List[List[int]] = [[] for _ in range(maxrank + 1)]
    for v in verts:
        layers[v.rank].append(v.i)

    up: Dict[int, list] = {v.i: [] for v in verts}
    down: Dict[int, list] = {v.i: [] for v in verts}
    for x, y, w in segs:
        down[x].append((y, w))
        up[y].append((x, w))

    # initial order: depth-first preorder
    pre: Dict[int, int] = {}
    srcs = sorted((v.i for v in verts if not up[v.i]), key=lambda i: (verts[i].key, i))
    cnt = 0
    for s0 in srcs:
        if s0 in pre:
            continue
        stack = [s0]
        while stack:
            x = stack.pop()
            if x in pre:
                continue
            pre[x] = cnt
            cnt += 1
            for y, _ in reversed(down[x]):
                if y not in pre:
                    stack.append(y)
    for v in verts:
        pre.setdefault(v.i, cnt + v.i)
    for L in layers:
        L.sort(key=lambda i: (verts[i].lane, pre[i]))

    # constraints applied to an order
    order_groups = []
    for grp in S.order:
        ids = [vid[g] for g in grp if g in vid]
        if len(ids) > 1 and len({verts[i].rank for i in ids}) == 1 and not any(
                g.startswith("note:") for g in grp):
            order_groups.append(ids)
    note_ids = sorted((v for v in verts if v.pull is not None), key=lambda v: v.key)

    def apply_constraints():
        for ids in order_groups:
            L = layers[verts[ids[0]].rank]
            slots = sorted(L.index(i) for i in ids)
            for s, i in zip(slots, ids):
                L[s] = i
        if note_ids:
            cl: Dict[int, int] = {}
            cr: Dict[int, int] = {}
            for nv in note_ids:
                L = layers[nv.rank]
                anchor, side = nv.pull
                if verts[anchor].rank != nv.rank:
                    continue
                L.remove(nv.i)
                ai = L.index(anchor)
                if side == "right":
                    L.insert(ai + 1 + cr.get(anchor, 0), nv.i)
                    cr[anchor] = cr.get(anchor, 0) + 1
                else:
                    L.insert(max(0, ai - cl.get(anchor, 0)), nv.i)
                    cl[anchor] = cl.get(anchor, 0) + 1

    apply_constraints()

    def index_map() -> Dict[int, int]:
        m = {}
        for L in layers:
            for p, i in enumerate(L):
                m[i] = p
        return m

    def total_crossings(ix) -> int:
        by_rank: Dict[int, list] = {}
        for x, y, _ in segs:
            by_rank.setdefault(verts[x].rank, []).append((ix[x], ix[y]))
        return sum(_count_crossings(p) for p in by_rank.values())

    def sort_layer(r: int, nbrs, ix):
        L = layers[r]
        bary = {}
        for i in L:
            ns = nbrs[i]
            bary[i] = (sum(ix[u] * w for u, w in ns) / sum(w for _, w in ns)) if ns else None
        if lanes_on:
            L.sort(key=lambda i: (verts[i].lane, bary[i] if bary[i] is not None else ix[i], ix[i]))
        else:
            fixed = {p: i for p, i in enumerate(L) if bary[i] is None}
            movable = sorted((i for i in L if bary[i] is not None), key=lambda i: (bary[i], ix[i]))
            it = iter(movable)
            L[:] = [fixed[p] if p in fixed else next(it) for p in range(len(L))]
        for p, i in enumerate(L):
            ix[i] = p

    ix = index_map()
    best = [list(L) for L in layers]
    best_cc = total_crossings(ix)
    stale = 0
    if best_cc > 0 and maxrank > 0:
        for it_no in range(24):
            if it_no % 2 == 0:
                for r in range(1, maxrank + 1):
                    sort_layer(r, up, ix)
            else:
                for r in range(maxrank - 1, -1, -1):
                    sort_layer(r, down, ix)
            apply_constraints()
            ix = index_map()
            cc = total_crossings(ix)
            if cc < best_cc:
                best, best_cc, stale = [list(L) for L in layers], cc, 0
                if cc == 0:
                    break
            else:
                stale += 1
                if stale >= 4:
                    break
        layers = best
    ix = index_map()

    # ---- cross axis coordinates
    def gap(x: V, y: V) -> float:
        if x.pull is not None or y.pull is not None:
            return GAP_NOTE
        if x.dummy and y.dummy:
            return GAP_DUMMY
        if x.dummy or y.dummy:
            return GAP_MIXED
        return opts.node_gap

    def seps_for(L: List[int]) -> List[float]:
        return [(verts[a].a + verts[b].a) / 2 + gap(verts[a], verts[b]) for a, b in zip(L, L[1:])]

    nbrs_all: Dict[int, list] = {v.i: up[v.i] + down[v.i] for v in verts}
    lane_bounds: List[Tuple[float, float]] = []
    if lanes_on:
        widths = [0.0] * n_lane_slots
        for L in layers:
            by: Dict[int, List[int]] = {}
            for i in L:
                by.setdefault(verts[i].lane, []).append(i)
            for ln, ids in by.items():
                wsum = verts[ids[0]].a / 2 + verts[ids[-1]].a / 2 + sum(seps_for(ids))
                widths[ln] = max(widths[ln], wsum)
        # lanes are adjacent bands; the unnamed slot (index len(lanes)) only exists if used
        used_slots = [ln for ln in range(n_lane_slots) if any(verts[i].lane == ln for i in range(len(verts)))]
        x0 = 0.0
        bounds = {}
        for ln in range(n_lane_slots):
            if ln in used_slots or ln < len(S.lanes):
                w = max(widths[ln], 40.0) + 2 * LANE_PAD
                bounds[ln] = (x0, x0 + w)
                x0 += w
        lane_bounds = [bounds[ln] for ln in range(n_lane_slots) if ln in bounds]
        lane_lo = {ln: b[0] for ln, b in bounds.items()}
        lane_hi = {ln: b[1] for ln, b in bounds.items()}

    for L in layers:
        if not L:
            continue
        if lanes_on:
            by2: Dict[int, List[int]] = {}
            for i in L:
                by2.setdefault(verts[i].lane, []).append(i)
            for ln, ids in by2.items():
                tot = sum(seps_for(ids)) + verts[ids[0]].a / 2 + verts[ids[-1]].a / 2
                start = (lane_lo[ln] + lane_hi[ln]) / 2 - tot / 2 + verts[ids[0]].a / 2
                p = start
                for n_, i in enumerate(ids):
                    verts[i].pos = p
                    if n_ + 1 < len(ids):
                        p += seps_for([i, ids[n_ + 1]])[0]
        else:
            tot = sum(seps_for(L)) + verts[L[0]].a / 2 + verts[L[-1]].a / 2
            p = -tot / 2 + verts[L[0]].a / 2
            for n_, i in enumerate(L):
                verts[i].pos = p
                if n_ + 1 < len(L):
                    p += seps_for([i, L[n_ + 1]])[0]

    def desire(v: V):
        ns = nbrs_all[v.i]
        num = den = 0.0
        for u, w in ns:
            num += verts[u].pos * w
            den += w
        if v.pull is not None and verts[v.pull[0]].rank == v.rank:
            a = verts[v.pull[0]]
            sgn = 1 if v.pull[1] == "right" else -1
            tgt = a.pos + sgn * ((a.a + v.a) / 2 + GAP_NOTE)
            num += tgt * 10
            den += 10
        if den == 0:
            return v.pos, 0.01
        return num / den, den

    def place_layer(L: List[int]):
        groups_ = [L]
        if lanes_on:
            groups_ = []
            for i in L:
                if groups_ and verts[groups_[-1][0]].lane == verts[i].lane:
                    groups_[-1].append(i)
                else:
                    groups_.append([i])
        for ids in groups_:
            ds, ws = zip(*[desire(verts[i]) for i in ids])
            xs = _pav(list(ds), list(ws), seps_for(ids))
            if lanes_on:
                ln = verts[ids[0]].lane
                lo, hi = lane_lo[ln] + LANE_PAD, lane_hi[ln] - LANE_PAD
                left = xs[0] - verts[ids[0]].a / 2
                right = xs[-1] + verts[ids[-1]].a / 2
                shift = 0.0
                if left < lo:
                    shift = lo - left
                elif right > hi:
                    shift = hi - right
                xs = [x + shift for x in xs]
            for i, x in zip(ids, xs):
                verts[i].pos = x

    for _ in range(10):
        for r in list(range(1, maxrank + 1)) + list(range(maxrank - 1, -1, -1)):
            if layers[r]:
                place_layer(layers[r])

    def straighten(r: int, nbrs, other):
        L = layers[r]
        for p, i in enumerate(L):
            v = verts[i]
            if v.pull is not None or len(nbrs[i]) != 1:
                continue
            u = nbrs[i][0][0]
            if len(other[u]) != 1:
                continue
            t = verts[u].pos
            lo, hi = -1e18, 1e18
            if p > 0:
                lo = verts[L[p - 1]].pos + seps_for([L[p - 1], i])[0]
            if p + 1 < len(L):
                hi = verts[L[p + 1]].pos - seps_for([i, L[p + 1]])[0]
            if lanes_on:
                lo = max(lo, lane_lo[v.lane] + LANE_PAD + v.a / 2)
                hi = min(hi, lane_hi[v.lane] - LANE_PAD - v.a / 2)
            if lo <= hi:
                v.pos = min(max(t, lo), hi)

    for _ in range(2):
        for r in range(maxrank - 1, -1, -1):
            straighten(r, down, up)
        for r in range(1, maxrank + 1):
            straighten(r, up, down)

    # ---- rank axis coordinates
    header = opts.lane_header + 14 if lanes_on else 0.0
    pad_r = 16.0 if lanes_on else 0.0
    row_h = [max((verts[i].r for i in L), default=0.0) for L in layers]
    y = header + pad_r
    for r, L in enumerate(layers):
        center = y + row_h[r] / 2
        for i in L:
            verts[i].ry = center
        y += row_h[r] + opts.rank_gap / 2
    r_end = y - opts.rank_gap / 2 + pad_r

    # ---- convert to screen coordinates
    def scr(a: float, r: float) -> Pt:
        return (a, r) if tb else (r, a)

    pos: Dict[str, Pt] = {}
    for it in items:
        v = verts[vid[it]]
        pos[it] = scr(v.pos + v.off, v.ry)
    for k, chain in chains.items():
        pts = [scr(verts[i].pos, verts[i].ry) for i in chain[1:-1]]
        if rev_of[k]:
            pts.reverse()
        res.wps[k] = pts
        if k in label_v:
            res.label_at[k] = scr(verts[label_v[k]].pos, verts[label_v[k]].ry)
    res.pos = pos

    xs0, ys0, xs1, ys1 = [], [], [], []
    for it in items:
        cx, cy = pos[it]
        w, h = dims[it]
        xs0.append(cx - w / 2)
        ys0.append(cy - h / 2)
        xs1.append(cx + w / 2)
        ys1.append(cy + h / 2)
        v = verts[vid[it]]
        if v.off:
            # loop room on the right (tb) or bottom (lsrs)
            if tb:
                xs1.append(cx + w / 2 + (-v.off * 2))
            else:
                ys1.append(cy + h / 2 + (-v.off * 2))
    for pts in res.wps.values():
        for px, py in pts:
            xs0.append(px)
            xs1.append(px)
            ys0.append(py)
            ys1.append(py)
    for k, (px, py) in res.label_at.items():
        e = S.edges[k]
        xs0.append(px - e.lw / 2)
        xs1.append(px + e.lw / 2)
        ys0.append(py - e.lh / 2)
        ys1.append(py + e.lh / 2)
    if lanes_on and lane_bounds:
        a0, a1 = lane_bounds[0][0], lane_bounds[-1][1]
        if tb:
            xs0.append(a0)
            xs1.append(a1)
            ys0.append(0.0)
            ys1.append(r_end)
        else:
            ys0.append(a0)
            ys1.append(a1)
            xs0.append(0.0)
            xs1.append(r_end)
    minx, miny = min(xs0), min(ys0)
    for it in items:
        res.pos[it] = (pos[it][0] - minx, pos[it][1] - miny)
    for k in res.wps:
        res.wps[k] = [(px - minx, py - miny) for px, py in res.wps[k]]
    for k in res.label_at:
        res.label_at[k] = (res.label_at[k][0] - minx, res.label_at[k][1] - miny)
    res.size = (max(xs1) - minx, max(ys1) - miny)
    res.loops = {items[v]: n for v, n in res.loops.items()}
    if lanes_on:
        names = list(S.lanes) + [""]
        k = 0
        slot_ids = [ln for ln in range(n_lane_slots) if ln in lane_lo]
        for ln, (lo, hi) in zip(slot_ids, lane_bounds):
            if ln >= len(S.lanes):
                continue
            if tb:
                res.lanes.append(dict(name=names[ln], x=lo - minx, y=0 - miny, w=hi - lo, h=r_end,
                                      hx=lo - minx, hy=0 - miny, hw=hi - lo, hh=opts.lane_header, rot=False))
            else:
                res.lanes.append(dict(name=names[ln], x=0 - minx, y=lo - miny, w=r_end, h=hi - lo,
                                      hx=0 - minx, hy=lo - miny, hw=opts.lane_header, hh=hi - lo, rot=True))
    return res


def group_dims(S: Scene, gname: str, parent_dir: str, ctx: Ctx) -> Pt:
    sg = S.groups[gname]
    gdir = sg.direction or parent_dir
    ctx.gdir[gname] = gdir
    inner = layout_level(S, sg.path + (gname,), gdir, ctx)
    ctx.levels[sg.path + (gname,)] = inner
    pad = S.opts.group_pad
    title_w = max((line_w(l, 12) for l in sg.title_lines), default=0.0) + 2 * pad
    iw, ih = inner.size
    if not inner.dims:
        iw, ih = 70.0, 24.0
    gw = max(iw + 2 * pad, title_w, 90.0)
    gh = ih + 2 * pad + GROUP_TITLE_H
    ctx.gmeta[gname] = (gw, gh, pad, (gw - iw) / 2, pad + GROUP_TITLE_H)
    return gw, gh


# --------------------------------------------------------------------------- placement, routing
@dataclass
class EdgeGeom:
    id: str
    k: int
    cmds: list = field(default_factory=list)
    pts: List[Pt] = field(default_factory=list)
    head: Optional[Tuple[Pt, Pt]] = None       # (tip, unit direction)
    tail: Optional[Tuple[Pt, Pt]] = None
    label: Optional[Tuple[float, float, float, float]] = None   # cx, cy, w, h
    hidden: bool = False
    loop: bool = False


@dataclass
class Layout:
    scene: Scene
    settings: dict
    nodes: Dict[str, Tuple[float, float, float, float]] = field(default_factory=dict)   # cx, cy, w, h
    groups: Dict[str, Tuple[float, float, float, float]] = field(default_factory=dict)  # x, y, w, h
    group_order: List[str] = field(default_factory=list)
    lanes: List[dict] = field(default_factory=list)
    edges: List[EdgeGeom] = field(default_factory=list)
    numbers: Dict[str, int] = field(default_factory=dict)
    enumbers: Dict[str, int] = field(default_factory=dict)
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)
    blocks: dict = field(default_factory=dict)
    content: Tuple[float, float] = (0, 0)
    dx: float = 0.0
    dy: float = 0.0
    canvas: dict = field(default_factory=dict)
    warnings: List[Tuple[str, str]] = field(default_factory=list)
    direction: str = "tb"


def _hits_side(box, port):
    cx, cy, w, h = box[:4]
    hw, hh = w / 2, h / 2
    return {"top": (cx, cy - hh), "bottom": (cx, cy + hh), "left": (cx - hw, cy), "right": (cx + hw, cy)}[port]


NORMALS = {"top": (0.0, -1.0), "bottom": (0.0, 1.0), "left": (-1.0, 0.0), "right": (1.0, 0.0),
           "top-left": (-0.7071, -0.7071), "top-right": (0.7071, -0.7071),
           "bottom-left": (-0.7071, 0.7071), "bottom-right": (0.7071, 0.7071)}


def port_point(box, shape: str, port: str) -> Pt:
    cx, cy, w, h = box[:4]
    if port in ("top", "bottom", "left", "right"):
        return _hits_side(box, port)
    sx = -1 if "left" in port else 1
    sy = -1 if "top" in port else 1
    if shape == "decide":
        return (cx + sx * w / 4, cy + sy * h / 4)
    return (cx + sx * w / 2, cy + sy * h / 2)


def border_point(box, shape: str, toward: Pt) -> Pt:
    cx, cy, w, h = box[:4]
    d = (toward[0] - cx, toward[1] - cy)
    if abs(d[0]) < 1e-9 and abs(d[1]) < 1e-9:
        return (cx, cy + h / 2)
    poly = outline_polygon(shape, w, h)
    return ray_poly((cx, cy), unit(d), poly, (cx, cy))


def _end_dirs(cmds):
    """start point, start direction, end point, end direction of a path."""
    def seg_dir(a: Pt, b: Pt) -> Pt:
        return unit((b[0] - a[0], b[1] - a[1]))
    first, second = cmds[0], cmds[1]
    p0 = (first[1], first[2])
    if second[0] == "C":
        q = (second[1], second[2])
        if math.dist(q, p0) < 1e-6:
            q = (second[3], second[4])
        if math.dist(q, p0) < 1e-6:
            q = (second[5], second[6])
    elif second[0] == "Q":
        q = (second[1], second[2])
    else:
        q = (second[1], second[2])
    last = cmds[-1]
    prev = cmds[-2]
    pe = (last[-2], last[-1])
    pp = (prev[-2], prev[-1]) if prev[0] != "Z" else p0
    if last[0] == "C":
        q2 = (last[3], last[4])
        if math.dist(q2, pe) < 1e-6:
            q2 = (last[1], last[2])
        if math.dist(q2, pe) < 1e-6:
            q2 = pp
    elif last[0] == "Q":
        q2 = (last[1], last[2])
    else:
        q2 = pp
    return p0, seg_dir(p0, q), pe, seg_dir(q2, pe)


def head_trim(kind: str, size: float) -> float:
    return {"arrow": size, "diamond": size * 1.5, "dot": size * 0.9, "circle": size * 0.9}.get(kind, 0.0)


def _tangents(pts: List[Pt], tb: bool):
    n = len(pts)
    t = []
    for i in range(n):
        lo = pts[i - 1] if i > 0 else pts[i]
        hi = pts[i + 1] if i < n - 1 else pts[i]
        d = (hi[1] - lo[1]) if tb else (hi[0] - lo[0])
        s = 1.0 if d >= 0 else -1.0
        t.append((0.0, s) if tb else (s, 0.0))
    return list(t), list(t)


def _default_heads(op: str):
    return {"->": ("none", "arrow"), "-.->": ("none", "arrow"), "==>": ("none", "arrow"),
            "--": ("none", "none"), "-.-": ("none", "none"), "===": ("none", "none"),
            "both": ("arrow", "arrow"), "back": ("arrow", "none"), "hide": ("none", "none")}.get(op, ("none", "arrow"))


def build_path(pts, route, tb, corner, forced_in=None, forced_out=None):
    """pts -> path commands."""
    if len(pts) == 2 and route in ("curved", "spline", "orthogonal", "step") and \
            ((abs(pts[0][0] - pts[1][0]) < 0.5) or (abs(pts[0][1] - pts[1][1]) < 0.5)) and not (forced_in or forced_out):
        return [("M", *pts[0]), ("L", *pts[1])]
    if route == "straight":
        return polyline_cmds(pts, 0)
    tin, tout = _tangents(pts, tb)
    if forced_out:
        tout[0] = forced_out
    if forced_in:
        tin[-1] = forced_in
    if route == "spline":
        return catmull_cmds(pts)
    if route in ("orthogonal", "step"):
        return polyline_cmds(ortho_points(pts, tin, tout), corner if route == "orthogonal" else 0)
    return bezier_through(pts, tin, tout)


def route_edge(S: Scene, k: int, A, B, shape_a: str, shape_b: str, wps: List[Pt], back: bool, flat: bool,
               direction: str, settings: dict, label_at: Optional[Pt] = None) -> EdgeGeom:
    e = S.edges[k]
    tb = direction == "tb"
    route = e.props.get("route") or settings.get("edge_style", "curved")
    corner = 6.0
    arrow = float(settings.get("arrow_size", 8))
    g = EdgeGeom(e.id, k, hidden=e.hidden)
    if e.hidden:
        return g
    ca, cb = (A[0], A[1]), (B[0], B[1])
    forced_out = forced_in = None
    pts: List[Pt]
    if e.src == e.dst:
        return loop_geom(S, k, A, direction, arrow, settings)
    if flat:
        wps = []
    # start / end
    if e.src_port:
        p0 = port_point(A, shape_a, e.src_port)
        nrm = NORMALS[e.src_port]
        s0 = (p0[0] + nrm[0] * 14, p0[1] + nrm[1] * 14)
        forced_out = nrm
        pre = [p0, s0]
    elif back and wps:
        side = _side(A, wps[0], tb)
        p0 = _hits_side(A, side)
        forced_out = NORMALS[side]
        nr = NORMALS[side]
        pre = [p0, (p0[0] + nr[0] * 18, p0[1] + nr[1] * 18)]
    else:
        toward = wps[0] if wps else cb
        pre = [border_point(A, shape_a, toward)]
    if e.dst_port:
        p1 = port_point(B, shape_b, e.dst_port)
        nrm = NORMALS[e.dst_port]
        s1 = (p1[0] + nrm[0] * 14, p1[1] + nrm[1] * 14)
        forced_in = (-nrm[0], -nrm[1])
        post = [s1, p1]
    elif back and wps:
        side = _side(B, wps[-1], tb)
        p1 = _hits_side(B, side)
        nrm = NORMALS[side]
        forced_in = (-nrm[0], -nrm[1])
        post = [(p1[0] + nrm[0] * 18, p1[1] + nrm[1] * 18), p1]
    else:
        toward = wps[-1] if wps else ca
        post = [border_point(B, shape_b, toward)]
    pts = pre + list(wps) + post
    if flat and not e.src_port and not e.dst_port:
        pts = [border_point(A, shape_a, cb), border_point(B, shape_b, ca)]
        route_ = "straight"
    else:
        route_ = route
    cmds = build_path(pts, route_, tb, corner, forced_in, forced_out)
    hs, ts = _default_heads(e.op)
    hk = e.props.get("head", ts)
    tk = e.props.get("tail", hs)
    p_start, d_start, p_end, d_end = _end_dirs(cmds)
    cmds = trim_path(cmds, head_trim(tk, arrow), head_trim(hk, arrow), d_start, d_end)
    g.cmds = cmds
    g.pts = [p for sub in flatten(cmds) for p in sub]
    if hk != "none":
        g.head = (p_end, d_end)
    if tk != "none":
        g.tail = (p_start, (-d_start[0], -d_start[1]))
    if e.label:
        pos = float(e.props.get("label-pos", 0.5))
        lp = label_at if abs(pos - 0.5) < 1e-9 else None
        if lp is None:
            lp = point_at(g.pts, pos)[0]
        g.label = (lp[0], lp[1], e.lw, e.lh)
    return g


def _side(box, toward: Pt, tb: bool) -> str:
    cx, cy = box[0], box[1]
    if tb:
        return "right" if toward[0] >= cx else "left"
    return "bottom" if toward[1] >= cy else "top"


def loop_geom(S: Scene, k: int, A, direction: str, arrow: float, settings: dict, nth: int = 0) -> EdgeGeom:
    e = S.edges[k]
    cx, cy, w, h = A[:4]
    tb = direction == "tb"
    L = LOOP + 12 * nth
    g = EdgeGeom(e.id, k, loop=True, hidden=e.hidden)
    if e.hidden:
        return g
    if tb:
        sy = min(h / 4, 10)
        s, t = (cx + w / 2, cy - sy), (cx + w / 2, cy + sy)
        cmds = [("M", *s), ("C", s[0] + L, s[1] - 8, t[0] + L, t[1] + 8, *t)]
        lab = (cx + w / 2 + L + (e.lw / 2 if e.label else 0) - 2, cy)
    else:
        sx = min(w / 4, 10)
        s, t = (cx - sx, cy + h / 2), (cx + sx, cy + h / 2)
        cmds = [("M", *s), ("C", s[0] - 8, s[1] + L, t[0] + 8, t[1] + L, *t)]
        lab = (cx, cy + h / 2 + L + (e.lh / 2 if e.label else 0) - 2)
    hs, ts = _default_heads(e.op)
    hk = e.props.get("head", ts)
    tk = e.props.get("tail", hs)
    p_start, d_start, p_end, d_end = _end_dirs(cmds)
    cmds = trim_path(cmds, head_trim(tk, arrow), head_trim(hk, arrow), d_start, d_end)
    g.cmds = cmds
    g.pts = [p for sub in flatten(cmds) for p in sub]
    if hk != "none":
        g.head = (p_end, d_end)
    if tk != "none":
        g.tail = (p_start, (-d_start[0], -d_start[1]))
    if e.label:
        g.label = (lab[0], lab[1], e.lw, e.lh)
    return g


def fit_groups(S: Scene, ctx: Ctx, nodes: dict, groups: dict):
    """Recompute group boxes bottom-up as the bounding box of their children."""
    pad = S.opts.group_pad
    order = sorted(S.groups, key=lambda n: -len(S.groups[n].path))
    for name in order:
        sg = S.groups[name]
        boxes = []
        for nid, sn in S.nodes.items():
            if sn.path and sn.path[-1] == name and nid in nodes:
                cx, cy, w, h = nodes[nid]
                boxes.append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
        for n2, g2 in S.groups.items():
            if g2.path and g2.path[-1] == name and n2 in groups:
                x, y, w, h = groups[n2]
                boxes.append((x, y, x + w, y + h))
        if not boxes:
            cx, cy = (groups[name][0] + groups[name][2] / 2, groups[name][1] + groups[name][3] / 2) \
                if name in groups else (0.0, 0.0)
            boxes = [(cx - 35, cy - 12, cx + 35, cy + 12)]
        x0 = min(b[0] for b in boxes) - pad
        y0 = min(b[1] for b in boxes) - pad - GROUP_TITLE_H
        x1 = max(b[2] for b in boxes) + pad
        y1 = max(b[3] for b in boxes) + pad
        tw = max((line_w(l, 12) for l in sg.title_lines), default=0.0) + 2 * pad
        if x1 - x0 < tw:
            x1 = x0 + tw
        groups[name] = (x0, y0, x1 - x0, y1 - y0)


def compute_layout(doc: Document, view: Optional[str] = None, overrides: Optional[dict] = None) -> Layout:
    settings = resolve_settings(doc, view, overrides)
    opts = layout_options(settings)
    scene = build_scene(doc, view, opts, direction=settings["direction"])
    direction = scene.direction
    settings["direction"] = direction
    ctx = Ctx(scene)
    lay = Layout(scene, settings, direction=direction)
    c = doc.constraints
    pins = {k: v for k, v in c.get("pins", {}).items() if k in scene.nodes}
    manual = settings["engine"] == "manual"
    if settings["engine"] == "elk":
        lay.warnings.append(("W010", "engine elk is not available in this renderer: falling back to dagre"))
    nodes: Dict[str, tuple] = {}
    groups: Dict[str, tuple] = {}
    origins: Dict[tuple, Pt] = {}
    root = LevelResult((), direction)
    if manual:
        for nid, sn in scene.nodes.items():
            x, y = pins.get(nid, (0.0, 0.0))
            nodes[nid] = (x, y, sn.w, sn.h)
        for name in scene.groups:
            groups[name] = (0.0, 0.0, 10.0, 10.0)
        fit_groups(scene, ctx, nodes, groups)
    else:
        root = layout_level(scene, (), direction, ctx)
        ctx.levels[()] = root

        def rec(path: tuple, res: LevelResult, ox: float, oy: float):
            origins[path] = (ox, oy)
            for it, (cx, cy) in res.pos.items():
                w, h = res.dims[it]
                ax, ay = ox + cx, oy + cy
                if it in scene.nodes:
                    nodes[it] = (ax, ay, w, h)
                else:
                    name = it[len(GROUP_PREFIX):]
                    gw, gh, pad, ioff_x, ioff_y = ctx.gmeta[name]
                    gx, gy = ax - gw / 2, ay - gh / 2
                    groups[name] = (gx, gy, gw, gh)
                    sg = scene.groups[name]
                    rec(sg.path + (name,), ctx.levels[sg.path + (name,)], gx + ioff_x, gy + ioff_y)
        rec((), root, 0.0, 0.0)
    moved: set = set()
    for nid, (px, py) in pins.items():
        if nid in nodes and not manual:
            cx, cy, w, h = nodes[nid]
            nodes[nid] = (px, py, w, h)
            moved.add(nid)
    if pins and not manual:
        lay.warnings.append(("W091", "pin moves nodes after automatic layout, so spacing around them is not rebalanced"))
    for ids, how in c.get("aligns", []):
        ids = [i for i in ids if i in nodes]
        if len(ids) < 2:
            continue
        bs = [nodes[i] for i in ids]
        for i, (cx, cy, w, h) in zip(ids, bs):
            if how == "center":
                cx = bs[0][0]
            elif how == "middle":
                cy = bs[0][1]
            elif how == "left":
                cx = min(b[0] - b[2] / 2 for b in bs) + w / 2
            elif how == "right":
                cx = max(b[0] + b[2] / 2 for b in bs) - w / 2
            elif how == "top":
                cy = min(b[1] - b[3] / 2 for b in bs) + h / 2
            elif how == "bottom":
                cy = max(b[1] + b[3] / 2 for b in bs) - h / 2
            nodes[i] = (cx, cy, w, h)
            moved.add(i)
    grid = settings.get("grid")
    if grid and not manual:
        g_ = float(grid)
        for nid, (cx, cy, w, h) in list(nodes.items()):
            sx, sy = round(cx / g_) * g_, round(cy / g_) * g_
            if (sx, sy) != (cx, cy):
                nodes[nid] = (sx, sy, w, h)
                moved.add(nid)
    if moved:
        fit_groups(scene, ctx, nodes, groups)
    lay.nodes, lay.groups = nodes, groups
    lay.group_order = sorted(groups, key=lambda n: len(scene.groups[n].path))
    if root.lanes and not manual:
        ox, oy = origins.get((), (0.0, 0.0))
        for ln in root.lanes:
            d = dict(ln)
            d["props"] = scene.lane_props.get(ln["name"], {})
            lay.lanes.append(d)
    lay.warnings += ctx.warnings

    # ---- edges
    label_cache: Dict[int, Pt] = {}
    loops_seen: Dict[str, int] = {}
    for k, e in enumerate(scene.edges):
        if k in ctx.skipped:
            lay.edges.append(EdgeGeom(e.id, k, hidden=True))
            continue
        path, ra, rb = ctx.edge_loc[k]
        res = ctx.levels.get(path)
        ox, oy = origins.get(path, (0.0, 0.0))
        wps = []
        flat = back = False
        if res is not None and not manual:
            wps = [(ox + x, oy + y) for x, y in res.wps.get(k, [])]
            flat = k in res.flat
            back = k in res.back
            if k in res.label_at:
                label_cache[k] = (ox + res.label_at[k][0], oy + res.label_at[k][1])
        endpoints = [e.src, e.dst]
        if moved and (e.src in moved or e.dst in moved):
            wps, flat, back = [], False, False
            label_cache.pop(k, None)
        if manual:
            wps, flat, back = [], False, False
        boxes, shapes = [], []
        for ep in endpoints:
            if ep in nodes:
                boxes.append(nodes[ep])
                shapes.append(scene.nodes[ep].shape if scene.nodes[ep].shape != "collapsed" else "block")
            else:
                gx, gy, gw, gh = groups[ep[len(GROUP_PREFIX):]]
                boxes.append((gx + gw / 2, gy + gh / 2, gw, gh))
                shapes.append("block")
        if e.src == e.dst:
            n = loops_seen.get(e.src, 0)
            loops_seen[e.src] = n + 1
            lay.edges.append(loop_geom(scene, k, boxes[0], direction, float(settings["arrow_size"]), settings, n))
            continue
        lay.edges.append(route_edge(scene, k, boxes[0], boxes[1], shapes[0], shapes[1], wps, back, flat,
                                    direction, settings, label_cache.get(k)))
    number_items(lay)
    compose(lay)
    return lay


def number_items(lay: Layout):
    S = lay.scene
    mode = lay.settings.get("autonumber", "off")
    if mode == "off":
        return
    doc = S.doc
    vis = [n for n in doc.nodes if n.id in S.nodes and n.shape != "note"]
    out: Dict[str, List[str]] = {}
    for e in doc.edges:
        if e.src in S.nodes and e.dst in S.nodes:
            out.setdefault(e.src, []).append(e.dst)
            if e.op in ("--", "-.-", "===", "both"):
                out.setdefault(e.dst, []).append(e.src)
    seen, order = set(), []
    starts = [n.id for n in vis if n.shape == "start"][:1]
    for root in starts + [n.id for n in vis]:
        if root in seen:
            continue
        seen.add(root)
        q = [root]
        while q:
            u = q.pop(0)
            order.append(u)
            for w in out.get(u, []):
                if w not in seen and w in S.nodes:
                    seen.add(w)
                    q.append(w)
    if mode in ("nodes", "both"):
        k = 0
        for nid in order:
            sn = S.nodes[nid]
            if sn.kind != "note" and not sn.props.get("nonumber") and sn.shape not in ("junction", "fork", "join", "text"):
                k += 1
                lay.numbers[nid] = k
    if mode in ("edges", "both"):
        k = 0
        for g in lay.edges:
            e = S.edges[g.k]
            if e.hidden or e.note_conn or g.hidden:
                continue
            k += 1
            lay.enumbers[e.id] = k


# --------------------------------------------------------------------------- composition and fit
def block_lines(text: str, fs: float, bold=False) -> Tuple[List[List[Run]], float, float]:
    t = text if not bold else "\n".join(f"**{x}**" if x.strip() else x for x in text.split("\n"))
    lines = wrap_text(t, 0, fs, False)
    w = max((line_w(l, fs) for l in lines), default=0.0)
    return lines, w, len(lines) * fs * 1.25


def compose(lay: Layout):
    S = lay.scene
    st = lay.settings
    # diagram bounding box
    bleed = 3.0 + float(st["line_width"]) + (8.0 if st.get("shadow") else 0.0)
    if st["style"] == "hand-drawn":
        bleed += 3.0 * float(st["roughness"])
    xs0, ys0, xs1, ys1 = [], [], [], []
    for cx, cy, w, h in lay.nodes.values():
        xs0.append(cx - w / 2 - bleed)
        ys0.append(cy - h / 2 - bleed)
        xs1.append(cx + w / 2 + bleed)
        ys1.append(cy + h / 2 + bleed)
    for nid in lay.numbers:
        cx, cy, w, h = lay.nodes[nid]
        xs0.append(cx - w / 2 - 10)
        ys0.append(cy - h / 2 - 10)
    for x, y, w, h in lay.groups.values():
        xs0.append(x - bleed)
        ys0.append(y - bleed)
        xs1.append(x + w + bleed)
        ys1.append(y + h + bleed)
    for ln in lay.lanes:
        xs0.append(ln["x"] - bleed)
        ys0.append(ln["y"] - bleed)
        xs1.append(ln["x"] + ln["w"] + bleed)
        ys1.append(ln["y"] + ln["h"] + bleed)
    ab = float(st["arrow_size"])
    for g in lay.edges:
        if g.hidden:
            continue
        for px, py in g.pts:
            xs0.append(px - ab)
            xs1.append(px + ab)
            ys0.append(py - ab)
            ys1.append(py + ab)
        if g.label:
            cx, cy, w, h = g.label
            xs0.append(cx - w / 2)
            xs1.append(cx + w / 2)
            ys0.append(cy - h / 2)
            ys1.append(cy + h / 2)
    if not xs0:
        xs0, ys0, xs1, ys1 = [0.0], [0.0], [60.0], [30.0]
    bx0, by0, bx1, by1 = min(xs0), min(ys0), max(xs1), max(ys1)
    lay.bbox = (bx0, by0, bx1, by1)
    bw, bh = bx1 - bx0, by1 - by0

    blocks: Dict[str, dict] = {}
    title = st.get("title")
    sizes = {}
    if title:
        blocks["title"] = dict(zip(("lines", "w", "h"), block_lines(title, 22, True)), fs=22)
    if st.get("subtitle"):
        blocks["subtitle"] = dict(zip(("lines", "w", "h"), block_lines(st["subtitle"], 14)), fs=14)
    if st.get("caption"):
        blocks["caption"] = dict(zip(("lines", "w", "h"), block_lines(st["caption"], 12)), fs=12)
    if st.get("footer"):
        blocks["footer"] = dict(zip(("lines", "w", "h"), block_lines(st["footer"], 11)), fs=11)
    legend = S.doc.legend
    leg = None
    if legend and legend["entries"]:
        rows = []
        for ent in legend["entries"]:
            lines, w, h = block_lines(ent["text"], 12)
            rows.append((ent, lines, w, h))
        lw = max(r[2] for r in rows) + 18 + 10 + 20
        lh = sum(max(r[3], 16) + 6 for r in rows) + 10
        leg = dict(rows=rows, w=lw, h=lh, pos=legend["position"])
    widths = [bw] + [b["w"] for b in blocks.values()] + ([leg["w"]] if leg else [])
    Wc = max(widths)
    y = 0.0
    if "title" in blocks:
        blocks["title"].update(x=Wc / 2, y=y)
        y += blocks["title"]["h"] + 4
    if "subtitle" in blocks:
        blocks["subtitle"].update(x=Wc / 2, y=y)
        y += blocks["subtitle"]["h"] + 4
    if "title" in blocks or "subtitle" in blocks:
        y += 10
    if leg and leg["pos"].startswith("top"):
        leg["x"] = 0.0 if leg["pos"].endswith("left") else Wc - leg["w"]
        leg["y"] = y
        y += leg["h"] + 12
    lay.dx = (Wc - bw) / 2 - bx0
    lay.dy = y - by0
    y += bh
    if leg and leg["pos"].startswith("bottom"):
        y += 12
        leg["x"] = 0.0 if leg["pos"].endswith("left") else Wc - leg["w"]
        leg["y"] = y
        y += leg["h"]
    if "caption" in blocks:
        y += 12
        blocks["caption"].update(x=Wc / 2, y=y)
        y += blocks["caption"]["h"]
    if "footer" in blocks:
        y += 12
        blocks["footer"].update(x=Wc / 2, y=y)
        y += blocks["footer"]["h"]
    if leg:
        blocks["legend"] = leg
    lay.blocks = blocks
    lay.content = (Wc, y)
    lay.canvas = fit_canvas(Wc, y, st, lay)


def fit_canvas(Wc: float, Hc: float, st: dict, lay: Optional[Layout] = None) -> dict:
    ratio = st.get("share_layout", "free")
    R = None
    if ratio and ratio != "free":
        a, b = ratio.split("/")
        R = float(a) / float(b)
    ew = st.get("export_width")
    out: dict = dict(R=R, scale=1.0)
    if R is None:
        pad = float(st.get("padding", 24))
        Wv, Hv = Wc + 2 * pad, Hc + 2 * pad
        out.update(W=Wv, H=Hv, ox=pad, oy=pad, M=pad)
    else:
        m = st.get("share_margin", "5%")
        m = str(m)
        M = (float(m[:-1]) / 100.0 * max(Wc, Hc)) if m.endswith("%") else float(m)
        M = max(M, 16.0)
        Wp, Hp = Wc + 2 * M, Hc + 2 * M
        if Wp / Hp > R:
            Wv = Wp
            Hv = Wv / R
        else:
            Hv = Hp
            Wv = Hv * R
        scale = 1.0
        if st.get("share_fit") == "shrink" and ew:
            Wv, Hv = float(ew), float(ew) / R
            scale = min(1.0, (Wv - 2 * M) / Wc if Wc else 1.0, (Hv - 2 * M) / Hc if Hc else 1.0)
        cw, ch = Wc * scale, Hc * scale
        anchor = st.get("share_anchor", "center")
        ox = {"left": M, "top-left": M, "bottom-left": M, "right": Wv - cw - M, "top-right": Wv - cw - M,
              "bottom-right": Wv - cw - M}.get(anchor, (Wv - cw) / 2)
        oy = {"top": M, "top-left": M, "top-right": M, "bottom": Hv - ch - M, "bottom-left": Hv - ch - M,
              "bottom-right": Hv - ch - M}.get(anchor, (Hv - ch) / 2)
        out.update(W=Wv, H=Hv, ox=ox, oy=oy, M=M, scale=scale)
    Wv, Hv = out["W"], out["H"]
    out["fill"] = (Wc * Hc * out["scale"] ** 2) / (Wv * Hv) if Wv * Hv else 1.0
    wa, ha = Wv, Hv
    if ew:
        wa = float(ew)
        ha = round(float(ew) * Hv / Wv)
    mw, mh = st.get("max_width"), st.get("max_height")
    if R is None and (mw or mh):
        s = 1.0
        if mw:
            s = min(s, float(mw) / wa)
        if mh:
            s = min(s, float(mh) / ha)
        wa, ha = wa * s, ha * s
    out["width_attr"], out["height_attr"] = wa, ha
    warns = []
    if R is not None and lay is not None:
        if out["fill"] < 0.45:
            if Wc / Hc > 1.5:
                best = "16/9"
            elif Hc / Wc > 1.6:
                best = "2/3"
            elif Hc / Wc > 1.25:
                best = "4/5"
            else:
                best = "1/1"
            warns.append(("W020", f"share_layout {ratio} leaves much empty space. Consider a different direction "
                                  f"or ratio (this shape suits {best})"))
        d = lay.direction
        if (d == "tb" and ratio == "16/9") or (d == "lsrs" and ratio in ("4/5", "2/3")):
            warns.append(("W021", f"share_layout {ratio} is unsuited to direction {d}"))
        lay.warnings += warns
    return out
