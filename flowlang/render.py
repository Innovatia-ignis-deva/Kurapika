"""Kurapika Flow Syntax v2 SVG painter: themes, shapes, edges, groups, lanes, and accessibility."""
from __future__ import annotations

import html
import math
import random
import re
from typing import Dict, List, Optional, Tuple

from .layout import (EdgeGeom, K, Layout, Pt, SNode, ellipse_cmds, flatten, fmt, line_w, outline_polygon,
                     path_d, point_at, round_rect_cmds, Run)
from .parser import GROUP_PREFIX, THEME_TOKENS, contrast, parse_color

FONT_STACK = 'Arial, Helvetica, "Liberation Sans", "Nimbus Sans", sans-serif'
MONO_STACK = '"Courier New", Courier, "Liberation Mono", monospace'


# --------------------------------------------------------------------------- colours / themes
def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def mix(a: str, b: str, t: float) -> str:
    """Blend colour a toward colour b by t (0 = a, 1 = b)."""
    ca, cb = parse_color(a), parse_color(b)
    if ca is None or cb is None:
        return a
    return _hex([ca[i] * (1 - t) + cb[i] * t for i in range(3)])


def readable(fill: str, ink: str, surface: str) -> str:
    """Pick ink or white/black so text on fill meets 4.5:1 where possible."""
    best, best_c = ink, contrast(ink, fill) or 0
    for cand in (ink, surface, "#000000", "#ffffff"):
        c = contrast(cand, fill) or 0
        if c >= 4.5:
            return cand
        if c > best_c:
            best, best_c = cand, c
    return best


BASE_THEMES = {
    "default": dict(surface="#ffffff", ink="#2b2d42", primary="#9370db", accent="#3b82c4", success="#3da35d",
                    warning="#e0a82e", danger="#d1453b", muted="#7a7f87", tint=0.86),
    "neutral": dict(surface="#ffffff", ink="#111111", primary="#555555", accent="#777777", success="#666666",
                    warning="#888888", danger="#333333", muted="#999999", tint=0.9),
    "forest": dict(surface="#f3f9f1", ink="#1e3a1e", primary="#2e7d32", accent="#7cb342", success="#2e7d32",
                   warning="#f9a825", danger="#c62828", muted="#6b7f6b", tint=0.82),
    "dark": dict(surface="#1a1b1e", ink="#e8e8e8", primary="#8ab4f8", accent="#c58af9", success="#81c995",
                 warning="#fdd663", danger="#f28b82", muted="#9aa0a6", tint=0.72),
    "redux-dark": dict(surface="#0b1426", ink="#f2f5ff", primary="#4da3ff", accent="#ff7a59", success="#35d0a0",
                       warning="#ffd166", danger="#ff5c7a", muted="#8a96b5", tint=0.72),
}


def build_theme(name: str, palette: Optional[dict] = None) -> dict:
    base = dict(BASE_THEMES["neutral"])
    if name == "custom":
        base.update(palette or {})
        base["tint"] = 0.72 if (parse_color(base["surface"]) and sum(parse_color(base["surface"])) < 300) else 0.86
        for k, v in list(base.items()):
            if k in THEME_TOKENS and parse_color(v) is None:
                base[k] = BASE_THEMES["neutral"][k]
    else:
        base = dict(BASE_THEMES.get(name, BASE_THEMES["default"]))
    t = base
    sf, ink, tn = t["surface"], t["ink"], t["tint"]
    dark = sum(parse_color(sf) or (255, 255, 255)) < 300

    def role(color, strong=1.0):
        return dict(fill=mix(color, sf, tn), border=color)
    t["roles"] = {
        "proc": role(t["primary"]), "start": role(t["success"]), "decide": role(t["warning"]),
        "data": role(t["accent"]), "ext": role(t["muted"]),
        "stop": dict(fill=mix(t["muted"], sf, tn - 0.04), border=mix(ink, sf, 0.25)),
        "note": dict(fill=mix(t["warning"], sf, min(0.93, tn + 0.05)), border=mix(t["warning"], sf, 0.2)),
    }
    t["edge"] = mix(ink, sf, 0.3 if not dark else 0.25)
    t["label_bg"] = sf
    t["group_fill"] = mix(t["primary"], sf, 0.94 if not dark else 0.85)
    t["group_border"] = mix(t["primary"], sf, 0.45)
    t["lane_fill"] = [mix(t["muted"], sf, 0.94 if not dark else 0.88), sf]
    t["lane_head"] = mix(t["primary"], sf, 0.78 if not dark else 0.6)
    t["lane_border"] = mix(t["muted"], sf, 0.45)
    t["dark"] = dark
    return t


def resolve_color(c: Optional[str], th: dict) -> Optional[str]:
    if c is None:
        return None
    c = c.strip()
    if c in THEME_TOKENS:
        return th[c]
    return c


SHAPE_ROLE = {"block": "proc", "sub": "proc", "pill": "proc", "io": "proc", "manual": "proc", "delay": "proc",
              "prepare": "proc", "doc": "proc", "docs": "proc", "image": "proc", "start": "start", "stop": "stop",
              "decide": "decide", "db": "data", "cloud": "ext", "connector": "ext", "note": "note",
              "collapsed": "proc"}


# --------------------------------------------------------------------------- shape outlines
def shape_cmds(shape: str, w: float, h: float, radius: float):
    """-> (behind, main, extras, text_dy). Path command lists centred on (0,0)."""
    hw, hh = w / 2, h / 2
    behind: list = []
    extras: list = []
    dy = 0.0
    if shape in ("block", "collapsed"):
        main = round_rect_cmds(hw, hh, radius)
    elif shape == "start":
        main = round_rect_cmds(hw, hh, hh)
    elif shape == "stop":
        main = round_rect_cmds(hw, hh, hh)
        extras.append(round_rect_cmds(hw - 4, hh - 4, max(hh - 4, 0)))
    elif shape == "pill":
        main = round_rect_cmds(hw, hh, min(hh, 14))
    elif shape == "decide":
        main = [("M", 0, -hh), ("L", hw, 0), ("L", 0, hh), ("L", -hw, 0), ("Z",)]
    elif shape == "io":
        s = min(hh * 0.6, 18)
        main = [("M", -hw + s, -hh), ("L", hw, -hh), ("L", hw - s, hh), ("L", -hw, hh), ("Z",)]
    elif shape == "sub":
        main = round_rect_cmds(hw, hh, min(radius, 4))
        for sx in (-1, 1):
            extras.append([("M", sx * (hw - 10), -hh), ("L", sx * (hw - 10), hh)])
    elif shape == "db":
        ry = min(9.0, hh * 0.4)
        top = -hh + ry
        main = [("M", -hw, top), ("C", -hw, top - K * ry, -K * hw, top - ry, 0, top - ry),
                ("C", K * hw, top - ry, hw, top - K * ry, hw, top), ("L", hw, hh - ry),
                ("C", hw, hh - ry + K * ry, K * hw, hh, 0, hh),
                ("C", -K * hw, hh, -hw, hh - ry + K * ry, -hw, hh - ry), ("Z",)]
        extras.append([("M", -hw, top), ("C", -hw, top + K * ry, -K * hw, top + ry, 0, top + ry),
                       ("C", K * hw, top + ry, hw, top + K * ry, hw, top)])
        dy = ry * 0.6
    elif shape in ("doc", "docs"):
        if shape == "docs":
            ww, hh2 = hw - 4, hh - 4
            cx0, cy0 = -4.0, 4.0
            for k in (2, 1):
                behind.append([("M", cx0 - ww + 4 * k, cy0 - hh2 - 4 * k), ("L", cx0 + ww + 4 * k, cy0 - hh2 - 4 * k),
                               ("L", cx0 + ww + 4 * k, cy0 + hh2 - 4 * k - 6), ("L", cx0 - ww + 4 * k, cy0 + hh2 - 4 * k - 6), ("Z",)])
        else:
            ww, hh2, cx0, cy0 = hw, hh, 0.0, 0.0
        b = hh2 - 8
        main = [("M", cx0 - ww, cy0 - hh2), ("L", cx0 + ww, cy0 - hh2), ("L", cx0 + ww, cy0 + b),
                ("C", cx0 + ww * 0.66, cy0 + b + 10, cx0 + ww * 0.33, cy0 + b + 10, cx0, cy0 + b),
                ("C", cx0 - ww * 0.33, cy0 + b - 10, cx0 - ww * 0.66, cy0 + b - 10, cx0 - ww, cy0 + b), ("Z",)]
        dy = (cy0 - 4) if shape == "doc" else cy0 - 4
    elif shape == "manual":
        s = min(14, hw * 0.2)
        main = [("M", -hw, -hh), ("L", hw, -hh), ("L", hw - s, hh), ("L", -hw + s, hh), ("Z",)]
    elif shape == "delay":
        main = [("M", -hw, -hh), ("L", hw - hh, -hh), ("C", hw - hh + K * hh, -hh, hw, -K * hh, hw, 0),
                ("C", hw, K * hh, hw - hh + K * hh, hh, hw - hh, hh), ("L", -hw, hh), ("Z",)]
    elif shape in ("connector", "junction"):
        main = ellipse_cmds(hw, hh)
    elif shape == "prepare":
        s = min(18, hw * 0.25)
        main = [("M", -hw + s, -hh), ("L", hw - s, -hh), ("L", hw, 0), ("L", hw - s, hh), ("L", -hw + s, hh),
                ("L", -hw, 0), ("Z",)]
    elif shape == "cloud":
        n = 9
        pts = [(hw * 0.86 * math.cos(2 * math.pi * i / n), hh * 0.86 * math.sin(2 * math.pi * i / n)) for i in range(n)]
        main = [("M", *pts[0])]
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            main.append(("Q", mx * 1.28, my * 1.28, *b))
        main.append(("Z",))
    elif shape == "note":
        f = min(12, hw * 0.4, hh * 0.6)
        main = [("M", -hw, -hh), ("L", hw - f, -hh), ("L", hw, -hh + f), ("L", hw, hh), ("L", -hw, hh), ("Z",)]
        extras.append([("M", hw - f, -hh), ("L", hw - f, -hh + f), ("L", hw, -hh + f)])
    elif shape in ("fork", "join"):
        main = round_rect_cmds(hw, hh, min(2, hh))
    elif shape == "image":
        main = round_rect_cmds(hw, hh, 4)
    else:
        main = round_rect_cmds(hw, hh, radius)
    return behind, main, extras, dy


def jitter_path(cmds, rng: random.Random, amp: float, close_ok=True) -> str:
    """Wobbly polyline version of a path for the hand-drawn look."""
    out = []
    for sub in flatten(cmds, 6):
        pts = []
        for i in range(len(sub) - 1):
            a, b = sub[i], sub[i + 1]
            d = math.dist(a, b)
            n = max(1, int(d // 22))
            for k in range(n):
                t = k / n
                pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        pts.append(sub[-1])
        closed = math.dist(sub[0], sub[-1]) < 1e-6
        jp = []
        for i, (x, y) in enumerate(pts):
            if closed and i == len(pts) - 1:
                jp.append(jp[0])
            else:
                jp.append((x + rng.uniform(-amp, amp), y + rng.uniform(-amp, amp)))
        out.append("M" + " L".join(f"{fmt(x)} {fmt(y)}" for x, y in jp))
    return " ".join(out)


# --------------------------------------------------------------------------- painter
def esc(s) -> str:
    return html.escape(str(s), quote=True)


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", s).strip("_") or "x"


def safe_url(u: str) -> Optional[str]:
    u = u.strip()
    if re.match(r"^(https?:|mailto:|#|/|\./|\.\./)", u, re.I) or re.match(r"^[A-Za-z0-9_\-./]+$", u):
        return u
    return None


class Painter:
    def __init__(self, lay: Layout):
        self.lay = lay
        self.S = lay.scene
        self.doc = lay.scene.doc
        self.st = lay.settings
        self.th = build_theme(self.st["theme"], self.doc.palette)
        self.rng = random.Random(int(self.st.get("seed") or 1))
        self.defs: List[str] = []
        self.gid = 0
        self.font = (f'"{self.st["font"]}", ' if self.st.get("font") else "") + FONT_STACK
        self.fs = float(self.st["font_size"])
        self.lw = float(self.st["line_width"])
        self.hand = self.st["style"] == "hand-drawn"
        self.amp = 0.9 * float(self.st["roughness"])
        self.anim = False

    # -- colour helpers --
    def col(self, c):
        return resolve_color(c, self.th)

    def fill_ref(self, fill: str) -> str:
        parts = re.split(r"\s+to\s+", fill)
        if len(parts) == 2:
            self.gid += 1
            gid = f"flow-grad-{self.gid}"
            c1, c2 = self.col(parts[0]), self.col(parts[1])
            self.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
                             f'<stop offset="0" stop-color="{esc(c1)}"/><stop offset="1" stop-color="{esc(c2)}"/>'
                             f'</linearGradient>')
            return f"url(#{gid})"
        return self.col(fill)

    # -- node style --
    def node_style(self, sn: SNode) -> dict:
        th, p = self.th, sn.props
        role = th["roles"][SHAPE_ROLE.get(sn.shape, "proc")]
        fill, border = role["fill"], role["border"]
        if sn.shape == "collapsed":
            fill, border = th["group_fill"], th["group_border"]
        if self.st.get("border_color"):
            border = self.col(self.st["border_color"])
        text = th["ink"]
        dash = False
        opacity = 1.0
        badge = None
        state = p.get("state", "normal")
        explicit_fill = "fill" in p
        if state == "active":
            fill, border = th["primary"], th["primary"]
            text = readable(th["primary"], th["ink"], th["surface"])
        elif state == "done":
            fill, border = mix(th["success"], th["surface"], th["tint"]), th["success"]
            badge = "done"
        elif state == "failed":
            fill, border = mix(th["danger"], th["surface"], th["tint"]), th["danger"]
            dash, badge = True, "failed"
        elif state == "skipped":
            fill, border = mix(th["muted"], th["surface"], 0.9), th["muted"]
            dash, text, badge = True, mix(th["ink"], th["surface"], 0.4), "skipped"
        elif state == "disabled":
            opacity = 0.5
        if explicit_fill:
            fill = p["fill"]
        if "border" in p:
            border = p["border"]
        if explicit_fill:
            fill_v = self.fill_ref(fill)
        elif self.st.get("gradient") and sn.shape not in ("junction", "fork", "join", "text"):
            fill_v = self.fill_ref(f"{fill} to {mix(fill, self.th['surface'], 0.55)}")
        else:
            fill_v = fill
        border_v = self.col(border)
        if "text-color" in p:
            text = self.col(p["text-color"])
        elif explicit_fill and not " to " in fill:
            text = readable(self.col(fill), th["ink"], th["surface"])
        if sn.shape in ("junction", "fork", "join"):
            fill_v, border_v = th["ink"], th["ink"]
        return dict(fill=fill_v, border=border_v, text=text, dash=dash or bool(p.get("dash")),
                    dot=bool(p.get("dot")), bw=float(p.get("border-width", self.lw)),
                    opacity=float(p.get("opacity", opacity)), shadow=bool(p.get("shadow", self.st.get("shadow"))),
                    radius=float(p.get("radius", self.st["corner_radius"])), badge=badge,
                    bold=bool(p.get("bold")), italic=bool(p.get("italic")), underline=bool(p.get("underline")),
                    hidden=bool(p.get("hidden")), align=p.get("align", "center"),
                    font=p.get("font"), fs=float(p.get("font-size", self.fs)))

    def dash_attr(self, dash: bool, dot: bool) -> str:
        if dot:
            return ' stroke-dasharray="1.5 4"'
        if dash:
            return ' stroke-dasharray="6 4"'
        return ""

    # -- text --
    def text_el(self, lines: List[List[Run]], fs: float, color: str, x: float, cy: float, anchor="middle",
                bold=False, italic=False, underline=False, family=None, lh=1.25, extra="") -> str:
        n = len(lines)
        y0 = cy - (n - 1) * fs * lh / 2 + fs * 0.34
        out = []
        for i, runs in enumerate(lines):
            spans = []
            for r in runs:
                if r.text == "":
                    continue
                attrs = ""
                if r.bold and not bold:
                    attrs += ' font-weight="bold"'
                if r.italic and not italic:
                    attrs += ' font-style="italic"'
                if r.mono:
                    attrs += f' font-family="{esc(MONO_STACK)}"'
                spans.append(f"<tspan{attrs}>{esc(r.text)}</tspan>")
            if not spans:
                continue
            fam = family or self.font
            wt = ' font-weight="bold"' if bold else ""
            it = ' font-style="italic"' if italic else ""
            ul = ' text-decoration="underline"' if underline else ""
            out.append(f'<text x="{fmt(x)}" y="{fmt(y0 + i * fs * lh)}" text-anchor="{anchor}" font-size="{fmt(fs)}" '
                       f'font-family="{esc(fam)}" fill="{esc(color)}"{wt}{it}{ul}{extra} xml:space="preserve">'
                       f'{"".join(spans)}</text>')
        return "".join(out)

    # -- shapes --
    def paint_shape(self, shape: str, w: float, h: float, stl: dict, cls: str = "") -> str:
        behind, main, extras, dy = shape_cmds(shape, w, h, stl["radius"])
        out = []
        sw = stl["bw"]
        da = self.dash_attr(stl["dash"], stl["dot"])
        fill, border = stl["fill"], stl["border"]
        if stl["shadow"] and shape not in ("text", "junction"):
            out.append(f'<path d="{path_d(main, 2, 3)}" fill="#000000" fill-opacity="0.18" stroke="none"/>')
        for b in behind:
            out.append(f'<path d="{path_d(b)}" fill="{esc(fill)}" stroke="{esc(border)}" stroke-width="{fmt(sw)}"{da}/>')
        if self.hand and shape not in ("junction", "fork", "join"):
            out.append(f'<path d="{path_d(main)}" fill="{esc(fill)}" stroke="none"/>')
            for k in range(2):
                out.append(f'<path d="{jitter_path(main, self.rng, self.amp)}" fill="none" stroke="{esc(border)}" '
                           f'stroke-width="{fmt(sw * (1 if k == 0 else 0.7))}" stroke-linejoin="round" '
                           f'stroke-linecap="round"{da}/>')
            for ex in extras:
                out.append(f'<path d="{jitter_path(ex, self.rng, self.amp * 0.6)}" fill="none" stroke="{esc(border)}" '
                           f'stroke-width="{fmt(sw)}" stroke-linecap="round"{da}/>')
        else:
            out.append(f'<path d="{path_d(main)}" fill="{esc(fill)}" stroke="{esc(border)}" '
                       f'stroke-width="{fmt(sw)}" stroke-linejoin="round"{da}/>')
            for ex in extras:
                out.append(f'<path d="{path_d(ex)}" fill="none" stroke="{esc(border)}" stroke-width="{fmt(sw)}"{da}/>')
        return "".join(out), dy

    def badge_glyph(self, kind: str, x: float, y: float) -> str:
        th = self.th
        col = {"done": th["success"], "failed": th["danger"], "skipped": th["muted"]}[kind]
        g = f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="8" fill="{esc(col)}"/>'
        stroke = f'stroke="{esc(th["surface"])}" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"'
        if kind == "done":
            g += f'<path d="M{fmt(x - 3.5)} {fmt(y)} L{fmt(x - 1)} {fmt(y + 3)} L{fmt(x + 4)} {fmt(y - 3)}" {stroke}/>'
        elif kind == "failed":
            g += (f'<path d="M{fmt(x - 3)} {fmt(y - 3)} L{fmt(x + 3)} {fmt(y + 3)} M{fmt(x + 3)} {fmt(y - 3)} '
                  f'L{fmt(x - 3)} {fmt(y + 3)}" {stroke}/>')
        else:
            g += f'<path d="M{fmt(x - 4)} {fmt(y)} L{fmt(x + 4)} {fmt(y)}" {stroke}/>'
        return g

    def paint_node(self, sn: SNode, box, in_layer: Optional[str]) -> str:
        cx, cy, w, h = box
        stl = self.node_style(sn)
        if stl["hidden"]:
            return ""
        th = self.th
        shape = sn.shape
        nid = slug(sn.id[len(GROUP_PREFIX):]) if sn.kind == "proxy" else sn.id
        el_id = f"flow-group-{nid}" if sn.kind == "proxy" else (f"flow-note-{slug(sn.id)}" if sn.kind == "note" else f"flow-node-{sn.id}")
        attrs = f' id="{esc(el_id)}" class="flow-node flow-shape-{shape}"'
        if in_layer:
            attrs += f' data-layer="{esc(in_layer)}"'
        o = sn.orig
        if o is not None and o.click:
            attrs += f' data-flow-click="{esc(re.sub(r"[^A-Za-z0-9_]", "", o.click))}"'
        if stl["opacity"] < 1:
            attrs += f' opacity="{fmt(stl["opacity"])}"'
        parts = [f'<g{attrs} transform="translate({fmt(cx)} {fmt(cy)})">']
        if o is not None and o.tooltip:
            parts.append(f"<title>{esc(o.tooltip)}</title>")
        dy = 0.0
        if shape == "text":
            pass
        elif shape == "image":
            s, dy0 = self.paint_shape("image", w, h, stl)
            parts.append(s)
            ph = h - (len(sn.lines) * sn.fs * 1.25 + 6 if sn.lines else 0)
            top = -h / 2 + 6
            pw = w - 24
            parts.append(f'<rect x="{fmt(-pw / 2)}" y="{fmt(top)}" width="{fmt(pw)}" height="{fmt(ph - 12)}" rx="3" '
                         f'fill="{esc(mix(th["muted"], th["surface"], 0.8))}"/>')
            by = top + ph - 12
            parts.append(f'<path d="M{fmt(-pw / 2 + 6)} {fmt(by - 4)} L{fmt(-pw / 6)} {fmt(top + (ph - 12) * 0.35)} '
                         f'L{fmt(0)} {fmt(by - (ph - 12) * 0.3)} L{fmt(pw / 5)} {fmt(top + (ph - 12) * 0.45)} '
                         f'L{fmt(pw / 2 - 6)} {fmt(by - 4)} Z" fill="{esc(mix(th["muted"], th["surface"], 0.45))}"/>')
            dy = h / 2 - (len(sn.lines) * sn.fs * 1.25) / 2 - 3 if sn.lines else 0
        else:
            s, dy = self.paint_shape(shape, w, h, stl)
            parts.append(s)
            if shape == "collapsed":
                parts.append(f'<path d="M{fmt(w / 2 - 18)} 0 L{fmt(w / 2 - 8)} 0 M{fmt(w / 2 - 13)} -5 L{fmt(w / 2 - 13)} 5" '
                             f'stroke="{esc(stl["border"])}" stroke-width="1.6" stroke-linecap="round"/>')
        if sn.lines and shape not in ("junction", "fork", "join"):
            anchor = {"left": "start", "right": "end"}.get(stl["align"], "middle")
            x = {"left": -w / 2 + 14, "right": w / 2 - 14}.get(stl["align"], 0.0)
            if shape == "io":
                x *= 0.9
            parts.append(self.text_el(sn.lines, sn.fs, stl["text"], x, dy, anchor, stl["bold"], stl["italic"],
                                      stl["underline"], family=stl["font"] and f'"{stl["font"]}", {FONT_STACK}'))
        if stl["badge"]:
            parts.append(self.badge_glyph(stl["badge"], w / 2 - 2, -h / 2 + 2))
        num = self.lay.numbers.get(sn.id)
        if num is not None:
            parts.append(self.number_badge(num, -w / 2, -h / 2))
        parts.append("</g>")
        out = "".join(parts)
        if o is not None and o.link:
            u = safe_url(o.link)
            if u:
                out = f'<a href="{esc(u)}" xlink:href="{esc(u)}" target="_blank" rel="noopener noreferrer">{out}</a>'
        return out

    def number_badge(self, n: int, x: float, y: float) -> str:
        th = self.th
        return (f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="9" fill="{esc(th["ink"])}"/>'
                f'<text x="{fmt(x)}" y="{fmt(y + 3.4)}" text-anchor="middle" font-size="10" font-weight="bold" '
                f'font-family="{esc(self.font)}" fill="{esc(th["surface"])}">{n}</text>')

    # -- edges --
    def head_glyph(self, kind: str, tip: Pt, d: Pt, color: str, size: float, width: float) -> str:
        if kind == "none":
            return ""
        nx, ny = -d[1], d[0]
        tx, ty = tip

        def P(a: float, b: float) -> str:      # a along -d (back from tip), b across
            return f"{fmt(tx - d[0] * a + nx * b)} {fmt(ty - d[1] * a + ny * b)}"
        c = esc(color)
        if kind == "arrow":
            return f'<path d="M{P(0, 0)} L{P(size, size * 0.42)} L{P(size, -size * 0.42)} Z" fill="{c}" stroke="{c}" stroke-width="0.6" stroke-linejoin="round"/>'
        if kind == "open":
            return (f'<path d="M{P(size, size * 0.45)} L{P(0, 0)} L{P(size, -size * 0.45)}" fill="none" stroke="{c}" '
                    f'stroke-width="{fmt(width)}" stroke-linecap="round" stroke-linejoin="round"/>')
        if kind in ("dot", "circle"):
            r = size * 0.45
            cxp, cyp = tx - d[0] * r, ty - d[1] * r
            fill = c if kind == "dot" else esc(self.th["surface"])
            return f'<circle cx="{fmt(cxp)}" cy="{fmt(cyp)}" r="{fmt(r)}" fill="{fill}" stroke="{c}" stroke-width="{fmt(width)}"/>'
        if kind == "diamond":
            return f'<path d="M{P(0, 0)} L{P(size * 0.75, size * 0.4)} L{P(size * 1.5, 0)} L{P(size * 0.75, -size * 0.4)} Z" fill="{c}" stroke="{c}" stroke-width="0.6"/>'
        if kind == "cross":
            s = size * 0.4
            return (f'<path d="M{P(size * 0.5 + s, s)} L{P(size * 0.5 - s, -s)} M{P(size * 0.5 + s, -s)} '
                    f'L{P(size * 0.5 - s, s)}" fill="none" stroke="{c}" stroke-width="{fmt(width)}" stroke-linecap="round"/>')
        if kind == "bar":
            return f'<path d="M{P(0, size * 0.5)} L{P(0, -size * 0.5)}" fill="none" stroke="{c}" stroke-width="{fmt(width * 1.6)}" stroke-linecap="butt"/>'
        return ""

    def paint_edge(self, g: EdgeGeom):
        e = self.S.edges[g.k]
        if g.hidden or not g.cmds:
            return "", ""
        p = e.props
        color = self.col(p.get("color")) or self.th["edge"]
        width = float(p.get("width", self.lw * (2 if e.op in ("==>", "===") else 1)))
        dash = bool(p.get("dash")) or e.op in ("-.->", "-.-") and not p.get("dot")
        dot = bool(p.get("dot"))
        if e.op in ("-.->", "-.-") and not p.get("dash"):
            dash, dot = False, True
        if e.note_conn:
            dash, dot = True, False
        da = self.dash_attr(dash, dot)
        eid = f"flow-edge-{e.id}" if not e.note_conn else f"flow-noteconn-{slug(e.src)}-{slug(e.dst)}"
        cls = "flow-edge"
        if p.get("animate"):
            cls += " flow-anim"
            self.anim = True
        attrs = f' id="{esc(eid)}" class="{cls}"'
        out = [f"<g{attrs}>"]
        if self.hand:
            for k in range(2):
                out.append(f'<path d="{jitter_path(g.cmds, self.rng, self.amp * 0.55)}" fill="none" stroke="{esc(color)}" '
                           f'stroke-width="{fmt(width * (1 if k == 0 else 0.6))}" stroke-linecap="round"{da}/>')
        else:
            out.append(f'<path d="{path_d(g.cmds)}" fill="none" stroke="{esc(color)}" stroke-width="{fmt(width)}" '
                       f'stroke-linejoin="round" stroke-linecap="{"round" if dot else "butt"}"{da}/>')
        arrow = float(self.st["arrow_size"])
        hw = max(1.0, min(width, 2.0))
        hs, ts = {"->": ("none", "arrow"), "-.->": ("none", "arrow"), "==>": ("none", "arrow"), "both": ("arrow", "arrow"),
                  "back": ("arrow", "none")}.get(e.op, ("none", "none"))
        if g.head:
            out.append(self.head_glyph(p.get("head", ts), g.head[0], g.head[1], color, arrow, hw))
        if g.tail:
            out.append(self.head_glyph(p.get("tail", hs), g.tail[0], g.tail[1], color, arrow, hw))
        out.append("</g>")
        lab = ""
        if g.label and e.label:
            cx, cy, w, h = g.label
            ls = float(p.get("label-size", 12))
            lcol = self.col(p.get("label-color")) or self.th["ink"]
            lab = (f'<g class="flow-edge-label" id="flow-label-{esc(e.id)}">'
                   f'<rect x="{fmt(cx - w / 2)}" y="{fmt(cy - h / 2)}" width="{fmt(w)}" height="{fmt(h)}" rx="4" '
                   f'fill="{esc(self.th["label_bg"])}" fill-opacity="0.92"/>'
                   f'{self.text_el(e.lines, ls, lcol, cx, cy)}</g>')
        num = self.lay.enumbers.get(e.id)
        if num is not None:
            pt = (g.label[0] - g.label[2] / 2 - 10, g.label[1]) if g.label else point_at(g.pts, 0.5)[0]
            lab += self.number_badge(num, pt[0], pt[1])
        return "".join(out), lab

    # -- groups and lanes --
    def paint_groups(self) -> str:
        out = []
        th = self.th
        for name in self.lay.group_order:
            x, y, w, h = self.lay.groups[name]
            sg = self.S.groups[name]
            p = sg.props
            fill = self.fill_ref(p["fill"]) if "fill" in p else th["group_fill"]
            border = self.col(p.get("border")) or th["group_border"]
            da = self.dash_attr(bool(p.get("dash")), bool(p.get("dot")))
            bw = float(p.get("border-width", 1.2))
            op = f' opacity="{fmt(float(p["opacity"]))}"' if "opacity" in p else ""
            rad = float(p.get("radius", 8))
            tcol = self.col(p.get("text-color")) or th["ink"]
            body = (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(rad)}" '
                    f'fill="{esc(fill)}" stroke="{esc(border)}" stroke-width="{fmt(bw)}"{da}/>')
            if self.hand:
                body = (f'<path d="{path_d(round_rect_cmds(w / 2, h / 2, rad, x + w / 2, y + h / 2))}" fill="{esc(fill)}" stroke="none"/>'
                        f'<path d="{jitter_path(round_rect_cmds(w / 2, h / 2, rad, x + w / 2, y + h / 2), self.rng, self.amp)}" '
                        f'fill="none" stroke="{esc(border)}" stroke-width="{fmt(bw)}" stroke-linecap="round"{da}/>')
            title = self.text_el(sg.title_lines, 12, tcol, x + 12, y + 14, "start", bold=True)
            out.append(f'<g id="flow-group-{esc(slug(name))}" class="flow-group"{op}>{body}{title}</g>')
        return "".join(out)

    def paint_lanes(self) -> str:
        out = []
        th = self.th
        for i, ln in enumerate(self.lay.lanes):
            p = ln.get("props", {})
            fill = self.fill_ref(p["fill"]) if "fill" in p else th["lane_fill"][i % 2]
            border = self.col(p.get("border")) or th["lane_border"]
            head = th["lane_head"] if "fill" not in p else self.col(p["fill"].split(" to ")[0])
            tcol = self.col(p.get("text-color")) or th["ink"]
            x, y, w, h = ln["x"], ln["y"], ln["w"], ln["h"]
            hx, hy, hw, hh = ln["hx"], ln["hy"], ln["hw"], ln["hh"]
            el = (f'<g id="flow-lane-{esc(slug(ln["name"]))}" class="flow-lane">'
                  f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" fill="{esc(fill)}" '
                  f'stroke="{esc(border)}" stroke-width="1"/>'
                  f'<rect x="{fmt(hx)}" y="{fmt(hy)}" width="{fmt(hw)}" height="{fmt(hh)}" fill="{esc(head)}" '
                  f'stroke="{esc(border)}" stroke-width="1"/>')
            lines = [[Run(ln["name"], bold=True)]]
            if ln["rot"]:
                cx, cy = hx + hw / 2, hy + hh / 2
                el += f'<g transform="rotate(-90 {fmt(cx)} {fmt(cy)})">{self.text_el(lines, 13, tcol, cx, cy)}</g>'
            else:
                el += self.text_el(lines, 13, tcol, hx + hw / 2, hy + hh / 2)
            out.append(el + "</g>")
        return "".join(out)

    # -- blocks: title, legend ... --
    def paint_blocks(self) -> str:
        out = []
        th = self.th
        b = self.lay.blocks
        for key, col, bold, italic in (("title", th["ink"], True, False), ("subtitle", mix(th["ink"], th["surface"], 0.35), False, False),
                                       ("caption", mix(th["ink"], th["surface"], 0.3), False, True),
                                       ("footer", mix(th["ink"], th["surface"], 0.45), False, False)):
            if key in b:
                blk = b[key]
                cy = blk["y"] + blk["h"] / 2
                out.append(f'<g class="flow-{key}">' + self.text_el(blk["lines"], blk["fs"], col, blk["x"], cy,
                                                                    bold=bold, italic=italic) + "</g>")
        leg = b.get("legend")
        if leg:
            x, y = leg["x"], leg["y"]
            out.append(f'<g class="flow-legend"><rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(leg["w"])}" height="{fmt(leg["h"])}" '
                       f'rx="6" fill="{esc(th["surface"])}" stroke="{esc(th["lane_border"])}"/>')
            cy = y + 8
            for ent, lines, w, h in leg["rows"]:
                rh = max(h, 16)
                st = ent["style"]
                fill = self.fill_ref(st["fill"]) if "fill" in st else th["roles"]["proc"]["fill"]
                border = self.col(st.get("border")) or (th["roles"]["proc"]["border"] if "fill" not in st else mix(self.col(st["fill"].split(" to ")[0]), th["ink"], 0.35))
                da = self.dash_attr(bool(st.get("dash")), bool(st.get("dot")))
                out.append(f'<rect x="{fmt(x + 10)}" y="{fmt(cy + rh / 2 - 6)}" width="18" height="12" rx="3" fill="{esc(fill)}" '
                           f'stroke="{esc(border)}" stroke-width="1.2"{da}/>')
                out.append(self.text_el(lines, 12, th["ink"], x + 36, cy + rh / 2, "start"))
                cy += rh + 6
            out.append("</g>")
        return "".join(out)

    # -- accessibility --
    def description(self) -> Tuple[str, str]:
        S, doc = self.S, self.doc
        nodes = [n for n in doc.nodes if n.id in S.nodes and n.shape not in ("note",)]
        decisions = sum(1 for n in nodes if n.shape == "decide")
        start = next((n for n in nodes if n.shape == "start"), nodes[0] if nodes else None)
        stext = re.sub(r"\s+", " ", start.text).strip() if start else ""
        auto = f"Flowchart with {len(nodes)} steps and {decisions} decisions" + (f" starting at {stext}" if stext else "")
        alt = self.st.get("alt") or auto
        names = {n.id: re.sub(r"\s+", " ", re.sub(r"\*\*|`", "", n.text)).strip() or n.id for n in nodes}
        adj: Dict[str, List] = {}
        for e in doc.edges:
            if e.src in S.nodes and e.dst in S.nodes:
                adj.setdefault(e.src, []).append(e)
        seen, order = set(), []
        roots = ([start.id] if start else []) + [n.id for n in nodes]
        for r in roots:
            if r in seen:
                continue
            seen.add(r)
            q = [r]
            while q:
                u = q.pop(0)
                order.append(u)
                for e in adj.get(u, []):
                    if e.dst not in seen:
                        seen.add(e.dst)
                        q.append(e.dst)
        lines = []
        for u in order:
            if u not in names:
                continue
            outs = adj.get(u, [])
            if outs:
                lines.append(f"{names[u]} leads to " + "; ".join(
                    (f"{names.get(e.dst, e.dst)}" + (f" when {e.label}" if e.label else "")) for e in outs) + ".")
            else:
                lines.append(f"{names[u]}.")
        return alt, auto + ". " + " ".join(lines)

    # -- assemble --
    def svg(self) -> str:
        lay, S, st, th = self.lay, self.S, self.st, self.th
        cv = lay.canvas
        in_layer = dict(S.layer_of)
        layer_nodes = {n for n in in_layer}
        body = []
        body.append(self.paint_lanes())
        body.append(self.paint_groups())
        labels = []
        edge_els = []
        for g in lay.edges:
            ee, ll = self.paint_edge(g)
            if ee:
                edge_els.append(ee)
            if ll:
                labels.append(ll)
        body.append(f'<g class="flow-edges">{"".join(edge_els)}</g>')
        nodes_normal, nodes_layer = [], []
        for nid, sn in S.nodes.items():
            el = self.paint_node(sn, lay.nodes[nid], in_layer.get(nid))
            (nodes_layer if nid in layer_nodes else nodes_normal).append(el)
        body.append(f'<g class="flow-nodes">{"".join(nodes_normal)}{"".join(nodes_layer)}</g>')
        body.append(f'<g class="flow-labels">{"".join(labels)}</g>')
        diagram = "".join(body)
        W, H = cv["W"], cv["H"]
        alt, desc = self.description()
        bg = st.get("background")
        out = []
        out.append(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                   f'viewBox="0 0 {fmt(W)} {fmt(H)}" width="{fmt(cv["width_attr"])}" height="{fmt(cv["height_attr"])}" '
                   f'role="img" aria-labelledby="flow-title flow-desc" font-family="{esc(self.font)}">')
        out.append(f'<title id="flow-title">{esc(alt)}</title><desc id="flow-desc">{esc(desc)}</desc>')
        if self.anim:
            out.append("<style>.flow-anim path{stroke-dasharray:6 4;animation:flow-dash 1s linear infinite}"
                       "@keyframes flow-dash{to{stroke-dashoffset:-20}}</style>")
        if self.defs:
            out.append("<defs>" + "".join(self.defs) + "</defs>")
        if bg != "transparent":
            fill = self.col(bg) if bg else th["surface"]
            out.append(f'<rect id="flow-background" x="0" y="0" width="{fmt(W)}" height="{fmt(H)}" fill="{esc(fill)}"/>')
        sc = cv["scale"]
        tr = f'translate({fmt(cv["ox"])} {fmt(cv["oy"])})' + (f' scale({fmt(sc)})' if abs(sc - 1) > 1e-9 else "")
        out.append(f'<g id="flow-content" transform="{tr}">')
        out.append(f'<g id="flow-diagram" transform="translate({fmt(lay.dx)} {fmt(lay.dy)})">{diagram}</g>')
        out.append(self.paint_blocks())
        out.append("</g>")
        wm = st.get("watermark")
        if wm:
            pos = st.get("watermark_pos", "bottom-right")
            col = esc(th["ink"])
            if pos == "center":
                fs = max(20.0, min(W, H) / 8)
                out.append(f'<text x="{fmt(W / 2)}" y="{fmt(H / 2)}" text-anchor="middle" font-size="{fmt(fs)}" fill="{col}" '
                           f'fill-opacity="0.08" font-weight="bold" font-family="{esc(self.font)}" '
                           f'transform="rotate(-25 {fmt(W / 2)} {fmt(H / 2)})">{esc(wm)}</text>')
            else:
                anchor = "end" if "right" in pos else "start"
                x = W - 10 if "right" in pos else 10
                y = H - 10 if "bottom" in pos else 22
                out.append(f'<text x="{fmt(x)}" y="{fmt(y)}" text-anchor="{anchor}" font-size="12" fill="{col}" '
                           f'fill-opacity="0.35" font-family="{esc(self.font)}">{esc(wm)}</text>')
        out.append("</svg>")
        return "".join(out)


def paint(lay: Layout) -> str:
    return Painter(lay).svg()
