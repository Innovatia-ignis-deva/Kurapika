"""Kurapika Flow Syntax v2 lexer, parser, resolver, and linter.

parse(source) -> Document.  Diagnostics (errors and warnings) live in doc.diagnostics.
Extension codes not in the spec: E080 syntax error, E081 unknown reference.
"""
from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

SHAPES = ("block", "start", "stop", "pill", "decide", "io", "sub", "db", "doc", "docs",
          "manual", "delay", "connector", "prepare", "cloud", "note", "junction", "fork",
          "join", "text", "image")
RESERVED = set("""flowchart tb lsrs block start stop pill decide io sub db doc docs manual delay
connector prepare cloud note junction fork join text image group lane class apply set is in when
label then link both back hide from go to ask chain fanout fanin cycle pipeline parallel via retry
up max let repeat as template use import view show tag layer legend autonumber edge title subtitle
caption footer theme style engine devas version mode palette true false on off free auto collapse
expand same rank order pin spacing align dotted thick dots bold""".split())
# 'docs', 'dotted', 'thick', 'dots', 'bold' are keywords too (shapes / operator aliases)
FUTURE = {"timeline", "swim", "mermaid", "export", "plugin", "macro", "assert"}
# The spec lists these as reserved but its own examples (25.4, 25.5) use them as IDs, so they are
# accepted as IDs; a line that starts with one and contains an edge operator is read as an edge.
SOFT_IDS = {"label", "tag", "test"}
OP_ALIAS = {"->": "->", "then": "->", "-.->": "-.->", "dotted": "-.->", "==>": "==>",
            "thick": "==>", "--": "--", "link": "--", "-.-": "-.-", "dots": "-.-",
            "===": "===", "bold": "===", "both": "both", "back": "back", "hide": "hide"}
PORTS = {"top", "bottom", "left", "right", "top-left", "top-right", "bottom-left", "bottom-right"}
GROUP_PREFIX = "group:"
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
THEME_TOKENS = {"primary", "accent", "success", "warning", "danger", "muted", "surface", "ink"}
CSS_COLORS = set("""aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue
blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan
darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen
darkorange darkorchid darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey
darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite
forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew hotpink
indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral
lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen
lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen magenta
maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue
mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin
navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen
paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red
rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue
slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white
whitesmoke yellow yellowgreen transparent none currentcolor""".split())
HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
LAYOUTS = ("16/9", "4/5", "2/3", "1/1", "free")
ANCHORS = ("center", "top", "bottom", "left", "right", "top-left", "top-right",
           "bottom-left", "bottom-right")
STATES = ("normal", "active", "done", "failed", "skipped", "disabled")
HEADS = ("arrow", "open", "dot", "cross", "diamond", "circle", "bar", "none")
ROUTES = ("straight", "curved", "orthogonal", "step", "spline")
FLAGS = ("bold", "italic", "underline", "shadow", "dash", "dot", "hidden", "nonumber")

# devas option -> (kind, allowed/default info, default)
DEVAS = {
    "share_layout": ("enum", LAYOUTS, "free"),
    "share_anchor": ("enum", ANCHORS, "center"),
    "share_margin": ("size", None, "5%"),
    "share_reflow": ("enum", ("off", "wrap"), "off"),
    "share_fit": ("enum", ("grow", "shrink"), "grow"),
    "padding": ("num", None, 24),
    "background": ("color", None, None),
    "transparent": ("bool", None, False),
    "export_format": ("enum", ("svg", "png", "pdf", "jpg", "webp", "json", "dot", "mermaid"), "svg"),
    "export_width": ("int", None, None),
    "export_dpi": ("int", None, 96),
    "seed": ("int", None, 1),
    "grid": ("gridv", None, None),
    "lock": ("bool", None, False),
    "alt": ("text", None, None),
    "watermark": ("text", None, None),
    "watermark_pos": ("enum", ("center", "bottom-right", "bottom-left", "top-right", "top-left"),
                      "bottom-right"),
    "units": ("enum", ("px", "pt"), "px"),
    "max_width": ("num", None, None),
    "max_height": ("num", None, None),
    "min_node_width": ("num", None, 80),
    "max_node_width": ("num", None, 240),
    "wrap_text": ("bool", None, True),
    "rank_gap": ("num", None, 56),
    "node_gap": ("num", None, 40),
    "edge_style": ("enum", ("orthogonal", "straight", "curved", "step"), "curved"),
    "autonumber": ("enum", ("off", "nodes", "edges", "both"), "off"),
    "strict": ("bool", None, False),
}

# simple header options: keyword -> (kind, allowed)
HEADER_OPTS = {
    "version": ("int", None), "mode": ("enum", ("compact", "normal")),
    "theme": ("enum", ("default", "neutral", "forest", "dark", "redux-dark", "custom")),
    "style": ("enum", ("classic", "neo", "hand-drawn")),
    "engine": ("enum", ("dagre", "elk", "manual")),
    "merge-edges": ("bool", None),
    "placement": ("enum", ("simple", "network-simplex", "linear-segments", "brandes-koepf")),
    "align": ("enum", ("none", "left-up", "left-down", "right-up", "right-down", "balanced")),
    "preset": ("enum", ("depth-first", "legacy", "model-order", "default")),
    "edge-routing": ("enum", ("orthogonal", "polyline", "splines")),
    "crossing-min": ("enum", ("layer-sweep", "none")),
    "node-spacing": ("num", None), "layer-spacing": ("num", None),
    "border-color": ("color", None), "gradient": ("bool", None), "font": ("text", None),
    "font-size": ("num", None), "corner-radius": ("num", None), "line-width": ("num", None),
    "arrow-size": ("num", None), "shadow": ("bool", None),
    "direction-default": ("enum", ("tb", "lsrs")), "roughness": ("num", None),
}
ELK_ONLY = ("merge-edges", "placement", "align", "preset", "crossing-min")

NODE_PROPS = {
    "fill": "fill", "border": "color", "border-width": "num", "text-color": "color",
    "font": "text", "font-size": "num", "width": "num", "height": "num", "radius": "num",
    "opacity": "unit", "icon": "text", "state": STATES, "align": ("left", "center", "right"),
}
EDGE_PROPS = {
    "color": "color", "width": "num", "head": HEADS, "tail": HEADS, "route": ROUTES,
    "label-pos": "unit", "label-color": "color", "label-size": "num", "animate": "bool",
}


# --------------------------------------------------------------------------- diagnostics
@dataclass
class Diagnostic:
    code: str
    line: int
    message: str
    hint: str = ""
    col: int = 1
    file: Optional[str] = None
    severity: str = ""

    def __post_init__(self):
        if not self.severity:
            self.severity = "error" if self.code.startswith("E") else "warning"

    def to_dict(self):
        return dict(code=self.code, severity=self.severity, line=self.line, col=self.col,
                    message=self.message, hint=self.hint, file=self.file)

    def __str__(self):
        loc = f"{self.file}:" if self.file else ""
        s = f"{self.code} {loc}line {self.line}: {self.message}"
        return s + (f"  (fix: {self.hint})" if self.hint else "")


class FlowError(Exception):
    def __init__(self, code, message, hint=""):
        super().__init__(message)
        self.code, self.message, self.hint = code, message, hint


class FlowParseError(Exception):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__("\n".join(str(d) for d in diagnostics))


# --------------------------------------------------------------------------- model
@dataclass
class Node:
    id: str
    shape: str
    text: str = ""
    group: Optional[str] = None
    lane: Optional[str] = None
    classes: List[str] = field(default_factory=list)
    style: dict = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    line: int = 0
    auto: bool = False        # created implicitly (edge or function)
    from_edge: bool = False   # auto-created by an edge (W001 strict)
    link: Optional[str] = None
    tooltip: Optional[str] = None
    click: Optional[str] = None

    def to_dict(self):
        d = dict(id=self.id, shape=self.shape, text=self.text, group=self.group, lane=self.lane,
                 classes=self.classes, style=self.style, tags=self.tags, line=self.line)
        for k in ("link", "tooltip", "click"):
            if getattr(self, k):
                d[k] = getattr(self, k)
        return d


@dataclass
class Edge:
    id: str
    src: str
    dst: str
    op: str = "->"
    label: Optional[str] = None
    src_port: Optional[str] = None
    dst_port: Optional[str] = None
    style: dict = field(default_factory=dict)
    classes: List[str] = field(default_factory=list)
    len: float = 1
    weight: float = 1
    line: int = 0
    user_id: bool = False

    def to_dict(self):
        return {"id": self.id, "from": self.src, "from_port": self.src_port, "to": self.dst,
                "to_port": self.dst_port, "op": self.op, "label": self.label, "style": self.style,
                "len": self.len, "weight": self.weight, "line": self.line}


@dataclass
class Group:
    name: str
    parent: Optional[str] = None
    direction: Optional[str] = None
    collapsed: bool = False
    members: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    style: dict = field(default_factory=dict)
    lane: Optional[str] = None
    line: int = 0

    def to_dict(self):
        return dict(name=self.name, parent=self.parent, direction=self.direction,
                    collapsed=self.collapsed, members=self.members, classes=self.classes,
                    style=self.style, lane=self.lane)


@dataclass
class Lane:
    name: str
    members: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    style: dict = field(default_factory=dict)
    line: int = 0

    def to_dict(self):
        return dict(name=self.name, members=self.members, classes=self.classes, style=self.style)


@dataclass
class Note:
    kind: str            # on | over | left | right
    targets: List[str]
    text: str
    line: int = 0

    def to_dict(self):
        return dict(kind=self.kind, targets=self.targets, text=self.text, line=self.line)


@dataclass
class View:
    name: str
    rules: List[tuple] = field(default_factory=list)   # (action, kind, value, line)
    overrides: dict = field(default_factory=dict)
    line: int = 0

    def to_dict(self):
        return dict(name=self.name, rules=[list(r[:3]) for r in self.rules],
                    overrides=self.overrides)


@dataclass
class Document:
    version: int = 2
    header: dict = field(default_factory=dict)
    direction: str = "tb"
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    groups: List[Group] = field(default_factory=list)
    lanes: List[Lane] = field(default_factory=list)
    classes: Dict[str, dict] = field(default_factory=dict)
    variables: Dict[str, str] = field(default_factory=dict)
    views: List[View] = field(default_factory=list)
    notes: List[Note] = field(default_factory=list)
    legend: Optional[dict] = None
    palette: Dict[str, str] = field(default_factory=dict)
    layers: Dict[str, List[str]] = field(default_factory=dict)
    set_all: Dict[str, dict] = field(default_factory=dict)
    constraints: dict = field(default_factory=dict)
    diagnostics: List[Diagnostic] = field(default_factory=list)

    # lookups -------------------------------------------------------------
    def node(self, nid):
        for n in self.nodes:
            if n.id == nid:
                return n
        return None

    def group(self, name):
        for g in self.groups:
            if g.name == name:
                return g
        return None

    def lane(self, name):
        for l in self.lanes:
            if l.name == name:
                return l
        return None

    def edge(self, eid):
        for e in self.edges:
            if e.id == eid:
                return e
        return None

    @property
    def errors(self):
        return [d for d in self.diagnostics if d.severity == "error"]

    @property
    def warnings(self):
        return [d for d in self.diagnostics if d.severity == "warning"]

    def devas(self, key, default="__unset__"):
        d = self.header.get("devas", {})
        if key in d:
            return d[key]
        return DEVAS[key][2] if default == "__unset__" else default

    def to_dict(self):
        return dict(version=self.version, header=self.header, direction=self.direction,
                    nodes=[n.to_dict() for n in self.nodes], edges=[e.to_dict() for e in self.edges],
                    groups=[g.to_dict() for g in self.groups], lanes=[l.to_dict() for l in self.lanes],
                    classes=self.classes, variables=self.variables,
                    views=[v.to_dict() for v in self.views], notes=[n.to_dict() for n in self.notes],
                    legend=self.legend, diagnostics=[d.to_dict() for d in self.diagnostics])


# --------------------------------------------------------------------------- text helpers
@dataclass
class Line:
    no: int
    indent: int
    text: str
    file: Optional[str] = None
    children: List["Line"] = field(default_factory=list)

    def copy(self, text=None):
        return Line(self.no, self.indent, self.text if text is None else text, self.file,
                    [c.copy() for c in self.children])


def strip_comment(s: str) -> str:
    """Remove a trailing comment: '#' preceded by 2+ spaces, outside quotes, not a hex colour."""
    inq = False
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            i += 2
            continue
        if c == '"':
            inq = not inq
        elif c == "#" and not inq and i >= 3 and s[i - 1] == " " and s[i - 2] == " ":
            if not re.match(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", s[i:]):
                return s[:i].rstrip()
        i += 1
    return s


def unescape(s: str) -> str:
    def rep(m):
        c = m.group(1)
        return {"n": "\n", "t": "    ", '"': '"', "\\": "\\", "$": "$"}.get(c, "\\" + c)
    return re.sub(r"\\(.)", rep, s, flags=re.S).replace("\x00", "$")


def tokenize(s: str):
    """Tokens: (kind, value, start, end); kind in str|comma|word."""
    toks = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
        elif c == ",":
            toks.append(("comma", ",", i, i + 1))
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n and s[j] != '"':
                if s[j] == "\\" and j + 1 < n:
                    buf.append(s[j:j + 2])
                    j += 2
                else:
                    buf.append(s[j])
                    j += 1
            if j >= n:
                raise FlowError("E080", "unterminated string", 'close the quote with "')
            toks.append(("str", unescape("".join(buf)), i, j + 1))
            i = j + 1
        else:
            j = i
            while j < n and not s[j].isspace() and s[j] not in ',"':
                j += 1
            toks.append(("word", s[i:j], i, j))
            i = j
    return toks


def split_outside_quotes(s: str, sep: str) -> List[str]:
    out, buf, inq, i = [], [], False, 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            buf.append(s[i:i + 2])
            i += 2
            continue
        if c == '"':
            inq = not inq
        if c == sep and not inq:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    out.append("".join(buf))
    return out


def first_colon(s: str) -> int:
    inq = False
    for i, c in enumerate(s):
        if c == '"':
            inq = not inq
        elif c == ":" and not inq:
            return i
    return -1


def qstr(tok) -> str:
    if tok is None or tok[0] != "str":
        raise FlowError("E080", "expected a quoted name", 'write the name in double quotes, e.g. "Name"')
    return tok[1]


def closest(word: str, options) -> str:
    m = difflib.get_close_matches(word, list(options), n=1, cutoff=0.6)
    return m[0] if m else ""


def to_num(v: str):
    try:
        f = float(v)
    except ValueError:
        return None
    return int(f) if f == int(f) and "." not in v else f


def is_color(v: str) -> bool:
    v = v.strip()
    return bool(HEX_RE.match(v) or v.lower() in CSS_COLORS or v in THEME_TOKENS)


def check_value(kind, value: str, what: str, code="E062"):
    """Validate and normalise a property value. kind: str kind or tuple of allowed words."""
    v = value.strip()
    if isinstance(kind, tuple):
        if v not in kind:
            raise FlowError(code, f"{what} must be one of: {', '.join(kind)}",
                            f"try {closest(v, kind) or kind[0]}")
        return v
    if kind == "color":
        if not is_color(v):
            raise FlowError(code, f"{what}: '{v}' is not a colour",
                            "use #rrggbb, a CSS name or a theme token (primary, danger ...)")
        return v
    if kind == "fill":
        parts = re.split(r"\s+to\s+", v)
        if len(parts) > 2 or not all(is_color(p) for p in parts):
            raise FlowError(code, f"{what}: '{v}' is not a colour or 'COLOR to COLOR'",
                            "example: fill #fff to #ccc")
        return " to ".join(p.strip() for p in parts)
    if kind in ("num", "int", "unit"):
        n = to_num(v)
        if n is None or (kind == "int" and not isinstance(n, int)):
            raise FlowError(code, f"{what}: '{v}' is not a number", "write a plain number")
        if kind == "unit" and not 0 <= n <= 1:
            raise FlowError(code, f"{what} must be between 0 and 1", "")
        if kind != "unit" and n < 0:
            raise FlowError(code, f"{what} must not be negative", "")
        return n
    if kind == "bool":
        lv = v.lower()
        if lv in ("true", "on"):
            return True
        if lv in ("false", "off"):
            return False
        raise FlowError(code, f"{what} must be true or false", "")
    if kind == "size":
        m = re.match(r"^(\d+(\.\d+)?)(%?)$", v)
        if not m:
            raise FlowError(code, f"{what}: '{v}' is not a size", "use a number or a percent like 5%")
        return v
    if kind == "gridv":
        if v.lower() in ("off", "false"):
            return None
        return check_value("num", v, what, code)
    return v  # text


def parse_style_items(body: str, line_no: int, props: dict, diags: list, extra_flags=()):
    """'fill #fff, bold, width 3' -> dict. Errors appended to diags."""
    out = {}
    for item in split_outside_quotes(body, ","):
        item = item.strip()
        if not item:
            continue
        name, _, val = item.partition(" ")
        val = val.strip()
        if name in FLAGS or name in extra_flags:
            if val == "" or name == "shadow" and val in ("true", "false", "on", "off"):
                out[name] = True if val in ("", "true", "on") else False
                continue
        if name in props:
            if val == "":
                diags.append(Diagnostic("E062", line_no, f"property '{name}' needs a value", f"{name} VALUE"))
                continue
            if val.startswith('"') and val.endswith('"') and len(val) >= 2:
                val = unescape(val[1:-1])
            try:
                out[name] = check_value(props[name], val, name)
            except FlowError as e:
                diags.append(Diagnostic(e.code, line_no, e.message, e.hint))
        else:
            known = list(props) + list(FLAGS)
            diags.append(Diagnostic("E061", line_no, f"unknown property '{name}'",
                                    f"did you mean '{closest(name, known)}'?" if closest(name, known)
                                    else "see the property tables in section 13"))
    return out


def valid_id(s: str, what="ID"):
    if len(s) > 64:
        raise FlowError("E022", f"{what} '{s[:20]}...' is longer than 64 characters", "shorten it")
    if not ID_RE.match(s):
        hint = "use letters, digits and underscore; start with a letter"
        if "-" in s:
            hint = "hyphens are not allowed in v2: use underscore, e.g. " + s.replace("-", "_")
        raise FlowError("E022", f"invalid {what} '{s}'", hint)
    if (s in RESERVED or s in FUTURE) and s not in SOFT_IDS:
        raise FlowError("E021", f"{what} '{s}' is a reserved word", f"pick another name, e.g. {s}_1")
    return s


# --------------------------------------------------------------------------- line reading
def read_lines(source: str, diags: list, file=None) -> List[Line]:
    """Source text -> flat logical lines (comments removed, continuations joined)."""
    out: List[Line] = []
    src = source.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    src = src.replace("\\$", "\x00")
    for no, raw in enumerate(src.split("\n"), 1):
        if not raw.strip():
            continue
        stripped = raw.strip()
        if stripped.startswith("#") or re.match(r"^note:", stripped):
            continue
        lead = raw[:len(raw) - len(raw.lstrip(" \t"))]
        if "\t" in lead:
            diags.append(Diagnostic("E002", no, "tab used for indentation", "use 4 spaces", file=file))
            lead = lead.replace("\t", "    ")
        text = strip_comment(stripped)
        if not text:
            continue
        if text.startswith("+ ") or text == "+":
            if out:
                out[-1].text += " " + text[1:].strip()
            continue
        ind = len(lead)
        if ind % 4:
            diags.append(Diagnostic("E003", no, f"indent of {ind} spaces is not a multiple of 4",
                                    "indent with 4 spaces per level", file=file))
            ind = (ind // 4) * 4
        out.append(Line(no, ind // 4, text, file))
    return out


def build_tree(flat: List[Line], diags: list) -> List[Line]:
    root = Line(0, -1, "")
    stack = [root]
    for ln in flat:
        while stack[-1].indent >= ln.indent and len(stack) > 1:
            stack.pop()
        parent = stack[-1]
        if ln.indent > parent.indent + 1:
            diags.append(Diagnostic("E003", ln.no, "indent jumps more than one level",
                                    "indent by exactly 4 spaces", file=ln.file))
        parent.children.append(ln)
        stack.append(ln)
    return root.children


# --------------------------------------------------------------------------- builder
VAR_RE = re.compile(r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)|\$([A-Za-z_][A-Za-z0-9_]*)")
FUNC_WORDS = {"chain", "fanout", "fanin", "cycle", "ask", "from", "parallel", "pipeline", "retry",
              "merge", "split", "skip"}
LAYOUT_WORDS = {"same", "order", "spacing", "pin", "align", "wrap", "keep"}
HEADER_WORDS = set(HEADER_OPTS) | {"title", "subtitle", "caption", "footer", "devas"}


def fword(text: str) -> str:
    m = re.match(r"^([^\s:]+)", text)
    w = m.group(1) if m else ""
    return w


class Builder:
    def __init__(self, loader: Optional[Callable[[str], str]] = None, filename: Optional[str] = None):
        self.doc = Document()
        self.diags = self.doc.diagnostics
        self.loader = loader
        self.vars: Dict[str, str] = {}
        self.templates: Dict[str, tuple] = {}
        self.nid: Dict[str, Node] = {}
        self.gstack: List[Group] = []
        self.lane: Optional[Lane] = None
        self.later: List[tuple] = []
        self.import_stack: List[str] = [filename] if filename else []
        self.loaded: set = set()
        self.tpl_stack: List[str] = []
        self.explicit_flow = False
        self.cur_file: Optional[str] = None
        self.class_uses: List[tuple] = []
        self.class_lines: Dict[str, int] = {}
        self.flow_dir: Optional[str] = None

    # -- diagnostics -----------------------------------------------------
    def err(self, code, ln, msg, hint=""):
        self.diags.append(Diagnostic(code, ln.no if isinstance(ln, Line) else ln, msg, hint,
                                     file=ln.file if isinstance(ln, Line) else None))

    def warn(self, code, ln, msg, hint=""):
        self.err(code, ln, msg, hint)

    # -- interpolation ---------------------------------------------------
    def interp(self, text: str, ln: Line) -> str:
        if "$" not in text:
            return text

        def rep(m):
            name = m.group(1) or m.group(2)
            if name in self.vars:
                return self.vars[name]
            self.err("E050", ln, f"undefined variable ${name}", f"define it first with: let {name} = VALUE")
            return m.group(0)
        return VAR_RE.sub(rep, text)

    # -- top level -------------------------------------------------------
    def run(self, source: str):
        flat = read_lines(source, self.diags, self.import_stack[0] if self.import_stack else None)
        tree = build_tree(flat, self.diags)
        idx = [i for i, l in enumerate(tree) if fword(l.text) == "flowchart" and l.indent == 0]
        if not idx:
            self.err("E001", 1, "no 'flowchart' line found", "add 'flowchart tb' or 'flowchart lsrs' before the body")
            head, body = tree, []
        else:
            if len(idx) > 1:
                self.err("E080", tree[idx[1]], "'flowchart' may appear only once", "remove the extra line")
            head, body = tree[:idx[0]], tree[idx[0] + 1:]
            self.flowline(tree[idx[0]])
        for ln in head:
            try:
                self.header_line(ln)
            except FlowError as e:
                self.err(e.code, ln, e.message, e.hint)
        self.process(body)
        self.finalize()
        return self.doc

    def flowline(self, ln: Line):
        parts = ln.text.split()
        d = parts[1] if len(parts) > 1 else None
        if d is not None and d not in ("tb", "lsrs"):
            self.err("E080", ln, f"unknown direction '{d}'", "use 'flowchart tb' or 'flowchart lsrs'")
            d = None
        if len(parts) > 2:
            self.err("E080", ln, "unexpected text after the direction", "")
        self.flow_dir = d
        self.explicit_flow = True

    # -- header ----------------------------------------------------------
    def header_line(self, ln: Line):
        text = ln.text
        h = self.doc.header
        m = re.match(r"^(title|subtitle|caption|footer)\s*:?\s*(.*)$", text)
        if m and (text.startswith(m.group(1) + ":") or text.startswith(m.group(1) + " ")):
            h[m.group(1)] = unescape(self.interp(m.group(2), ln))
            return
        if text.startswith("devas:") or text.startswith("devas "):
            self.devas_line(ln)
            return
        if self.definition(ln):
            return
        w = fword(text)
        if w in HEADER_OPTS:
            kind, allowed = HEADER_OPTS[w]
            val = self.interp(text[len(w):].strip(), ln)
            if val == "":
                raise FlowError("E012", f"header option '{w}' needs a value", f"{w} VALUE")
            if kind == "text" and len(val) > 1 and val[0] == val[-1] == '"':
                val = val[1:-1]
            if w == "version":
                v = check_value("int", val, w, "E012")
                self.doc.version = v
                h["version"] = v
                return
            try:
                h[w] = check_value(allowed if kind == "enum" else kind, val, w, "E012")
            except FlowError as e:
                raise FlowError("E012", e.message, e.hint)
            return
        if w in SHAPES or w in FUNC_WORDS or w in LAYOUT_WORDS or w in ("group", "lane", "set", "edge", "view") \
                or re.search(r"\s(->|-\.->|==>)\s", text):
            raise FlowError("E004", f"'{w}' is a body statement but appears before the 'flowchart' line",
                            "move it after the 'flowchart' line")
        hint = closest(w, HEADER_WORDS)
        raise FlowError("E004", f"unknown header keyword '{w}'",
                        f"did you mean '{hint}'?" if hint else "see section 4 for header options")

    def devas_line(self, ln: Line):
        m = re.match(r"^devas:?\s+([A-Za-z_]+)\s*:\s*(.*)$", ln.text)
        if not m:
            raise FlowError("E012", "bad devas line", "write: devas: OPTION: VALUE")
        name, val = m.group(1), self.interp(m.group(2).strip(), ln)
        if name not in DEVAS:
            hint = closest(name, DEVAS)
            raise FlowError("E010", f"unknown devas option '{name}'",
                            f"did you mean '{hint}'?" if hint else "see section 5.1")
        kind, allowed, _ = DEVAS[name]
        if name == "share_layout":
            if val not in LAYOUTS:
                raise FlowError("E011", "share_layout must be 16/9, 4/5, 2/3, 1/1 or free",
                                "write the ratio with a slash, e.g. 16/9" if ":" in val else "")
            self.doc.header.setdefault("devas", {})[name] = val
            return
        if kind == "text" and len(val) > 1 and val[0] == val[-1] == '"':
            val = val[1:-1]
        try:
            v = check_value(allowed if kind == "enum" else kind, val, "devas " + name, "E012")
        except FlowError as e:
            raise FlowError("E012", e.message, e.hint)
        if name == "background" and val.lower() == "transparent":
            self.doc.header.setdefault("devas", {})["transparent"] = True
        if name == "transparent" and v:
            self.doc.header.setdefault("devas", {})["background"] = "transparent"
        self.doc.header.setdefault("devas", {})[name] = unescape(v) if isinstance(v, str) else v

    # -- definitions -----------------------------------------------------
    def definition(self, ln: Line) -> bool:
        w = fword(ln.text)
        if w == "let":
            m = re.match(r"^let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", ln.text)
            if not m:
                raise FlowError("E080", "bad let statement", "write: let NAME = VALUE")
            self.vars[m.group(1)] = self.interp(m.group(2), ln)
            self.doc.variables[m.group(1)] = self.vars[m.group(1)]
            return True
        if w == "class" and ln.text.rstrip().endswith(":"):
            self.class_def(ln)
            return True
        if w == "template":
            self.template_def(ln)
            return True
        if w == "import":
            self.import_stmt(ln)
            return True
        if w == "palette":
            self.palette_def(ln)
            return True
        return False

    def class_def(self, ln: Line):
        m = re.match(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*:$", ln.text)
        if not m:
            raise FlowError("E080", "bad class header", "write: class NAME:")
        props = {}
        for ch in ln.children:
            props.update(parse_style_items(self.interp(ch.text, ch), ch.no,
                                           {**NODE_PROPS, **EDGE_PROPS}, self.diags))
        self.doc.classes[m.group(1)] = props
        self.class_lines[m.group(1)] = ln.no

    def palette_def(self, ln: Line):
        pal = {}
        for ch in ln.children:
            parts = ch.text.replace(":", " ").split()
            if len(parts) != 2 or parts[0] not in THEME_TOKENS or not is_color(parts[1]):
                self.err("E062", ch, f"bad palette entry '{ch.text}'",
                         "write: TOKEN COLOR, e.g. primary #1f6feb")
                continue
            pal[parts[0]] = parts[1]
        self.doc.palette.update(pal)

    def template_def(self, ln: Line):
        m = re.match(r"^template\s+([A-Za-z_]\w*)\s*\((.*)\)\s*:$", ln.text)
        if not m:
            raise FlowError("E080", "bad template header", "write: template NAME(PARAM, PARAM):")
        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
        self.templates[m.group(1)] = (params, ln.children)

    def import_stmt(self, ln: Line):
        m = re.match(r'^import\s+"(.*)"$', ln.text)
        if not m:
            raise FlowError("E080", "bad import", 'write: import "file.flow"')
        path = m.group(1)
        if path in self.import_stack:
            raise FlowError("E053", f"circular import of '{path}'", "remove the import cycle")
        if path in self.loaded:
            return
        if self.loader is None:
            raise FlowError("E080", f"cannot import '{path}': no file loader available",
                            "pass loader= to parse() or run from a file")
        try:
            text = self.loader(path)
        except Exception as e:  # noqa: BLE001
            raise FlowError("E080", f"cannot read import '{path}': {e}", "check the path")
        self.loaded.add(path)
        sub: List[Diagnostic] = []
        flat = read_lines(text, sub, path)
        for d in sub:
            self.diags.append(d)
        tree = build_tree(flat, sub)
        idx = [i for i, l in enumerate(tree) if fword(l.text) == "flowchart"]
        keep = []
        if idx:
            for l in tree[:idx[0]]:
                if fword(l.text) in ("let", "class", "template", "import", "palette"):
                    keep.append(l)
            keep += tree[idx[0] + 1:]
        else:
            keep = tree
        self.import_stack.append(path)
        try:
            self.process(keep)
        finally:
            self.import_stack.pop()

    # -- statement loop --------------------------------------------------
    def process(self, lines: List[Line]):
        for ln in lines:
            try:
                self.stmt(ln)
            except FlowError as e:
                self.err(e.code, ln, e.message, e.hint)

    def stmt(self, ln: Line):
        w = fword(ln.text)
        if w in ("let", "template", "import", "palette") or (w == "class" and ln.text.rstrip().endswith(":")):
            if self.definition(ln):
                return
        if w == "repeat":
            return self.repeat_stmt(ln)
        text = self.interp(ln.text, ln)
        if text != ln.text:
            ln = Line(ln.no, ln.indent, text, ln.file, ln.children)
        h = getattr(self, "s_" + w, None) if re.match(r"^[a-z]+$", w) else None
        if w in SHAPES and not (w == "note" and self.is_note_annotation(ln.text)):
            return self.node_stmt(ln)
        if w in SOFT_IDS and self.edge_line_ok(tokenize(ln.text)):
            return self.id_stmt(ln)
        if w == "note":
            return self.s_note(ln)
        if h and w not in SHAPES:
            return h(ln)
        if w in HEADER_WORDS or w == "flowchart":
            raise FlowError("E004", f"header option '{w}' must appear before the 'flowchart' line", "")
        self.id_stmt(ln)

    # -- repeat / use / if ----------------------------------------------
    def repeat_stmt(self, ln: Line):
        text = self.interp(ln.text, ln)
        if not text.rstrip().endswith(":"):
            raise FlowError("E080", "repeat header must end with a colon", "repeat 3 as i:")
        m = re.match(r"^repeat\s+each\s+([A-Za-z_]\w*)\s+in\s+(.+?)\s*:$", text)
        if m:
            var = m.group(1)
            values = [v.strip() for v in m.group(2).split(",") if v.strip()]
        else:
            m = re.match(r"^repeat\s+(\d+)(?:\s+from\s+(-?\d+))?\s+as\s+([A-Za-z_]\w*)\s*:$", text)
            if not m:
                raise FlowError("E080", "bad repeat header",
                                "write: repeat 3 as i:   or   repeat each name in A, B, C:")
            count, start, var = int(m.group(1)), int(m.group(2) or 1), m.group(3)
            values = [str(start + k) for k in range(count)]
        if len(values) > 1000:
            raise FlowError("E051", "repeat limit of 1000 iterations exceeded", "use a smaller count")
        saved = self.vars.get(var)
        for v in values:
            self.vars[var] = v
            self.process(ln.children)
        if saved is None:
            self.vars.pop(var, None)
        else:
            self.vars[var] = saved

    def s_use(self, ln: Line):
        m = re.match(r"^use\s+([A-Za-z_]\w*)\s*\((.*)\)\s*$", ln.text)
        if not m:
            raise FlowError("E080", "bad use statement", "write: use NAME(ARG, ARG)")
        name = m.group(1)
        if name not in self.templates:
            raise FlowError("E081", f"unknown template '{name}'",
                            f"did you mean '{closest(name, self.templates)}'?" if closest(name, self.templates)
                            else "define it with: template NAME(PARAMS):")
        if name in self.tpl_stack:
            raise FlowError("E052", f"template '{name}' calls itself", "remove the recursion")
        params, body = self.templates[name]
        args = [a.strip().strip('"') for a in split_outside_quotes(m.group(2), ",")] if m.group(2).strip() else []
        if len(args) != len(params):
            raise FlowError("E080", f"template '{name}' takes {len(params)} argument(s), got {len(args)}",
                            f"template {name}({', '.join(params)})")
        mapping = dict(zip(params, args))
        pat = None
        if mapping:
            keys = sorted(mapping, key=len, reverse=True)
            pat = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(k) for k in keys) + r")(?![A-Za-z0-9])")

        def subst(l: Line) -> Line:
            t = pat.sub(lambda mm: mapping[mm.group(1)], l.text) if pat else l.text
            return Line(ln.no, l.indent, t, l.file, [subst(c) for c in l.children])
        self.tpl_stack.append(name)
        try:
            self.process([subst(b) for b in body])
        finally:
            self.tpl_stack.pop()

    def s_if(self, ln: Line):
        m = re.match(r"^if\s+([A-Za-z_]\w*)\s+is(\s+not)?\s+(.+?)\s*:$", ln.text)
        if not m:
            raise FlowError("E080", "bad if statement", "write: if NAME is VALUE:")
        cur = self.vars.get(m.group(1))
        if cur is None:
            raise FlowError("E050", f"undefined variable ${m.group(1)}", f"let {m.group(1)} = VALUE")
        eq = cur == m.group(3).strip()
        if eq != bool(m.group(2)):
            self.process(ln.children)

    # -- nodes -----------------------------------------------------------
    def cur_group(self) -> Optional[Group]:
        return self.gstack[-1] if self.gstack else None

    def register(self, node: Node):
        old = self.nid.get(node.id)
        g = self.cur_group()
        node.group = g.name if g else None
        node.lane = self.lane.name if self.lane else None
        if old is not None:
            if old.group and self.doc.group(old.group) and old.id in self.doc.group(old.group).members:
                self.doc.group(old.group).members.remove(old.id)
            if old.lane and self.doc.lane(old.lane) and old.id in self.doc.lane(old.lane).members:
                self.doc.lane(old.lane).members.remove(old.id)
            self.doc.nodes[self.doc.nodes.index(old)] = node
        else:
            self.doc.nodes.append(node)
        self.nid[node.id] = node
        if g:
            g.members.append(node.id)
        if self.lane:
            self.lane.members.append(node.id)

    def check_node_id(self, s: str):
        valid_id(s)
        if re.match(r"^e\d+$", s):
            raise FlowError("E022", f"ID '{s}' is reserved for automatic edge IDs",
                            f"choose another ID, e.g. {s}_x or step_{s[1:]}")

    def node_stmt(self, ln: Line):
        m = re.match(r"^(\w+)\s+([^\s:]+)\s*(?::\s?(.*))?$", ln.text)
        if not m:
            raise FlowError("E080", "bad node declaration", "write: SHAPE ID: Text")
        shape, nid, text = m.group(1), m.group(2), m.group(3)
        self.check_node_id(nid)
        old = self.nid.get(nid)
        if old is not None and not old.auto:
            raise FlowError("E020", f"duplicate node ID '{nid}' (first declared on line {old.line})",
                            "declare each node once and style it with 'set'")
        text = unescape(text.strip()) if text is not None else ""
        if shape == "text" and text == "":
            text = ""
        if text == "" and shape not in ("junction", "fork", "join"):
            self.warn("W002", ln, f"empty label on node '{nid}'", "add text after the colon")
        node = Node(nid, shape, text, line=ln.no)
        self.register(node)

    def ensure_node(self, nid: str, ln, shape="block", from_edge=True) -> Node:
        n = self.nid.get(nid)
        if n is None:
            self.check_node_id(nid)
            n = Node(nid, shape, nid if shape == "block" else "", line=ln.no if isinstance(ln, Line) else ln,
                     auto=True, from_edge=from_edge)
            self.register(n)
        return n

    # -- groups / lanes --------------------------------------------------
    def s_group(self, ln: Line):
        s = ln.text.rstrip()
        toks = tokenize(s[:-1]) if s.endswith(":") else None
        if toks is None or len(toks) < 2 or toks[1][0] != "str":
            return self.id_stmt(ln)          # edge line starting with 'group "X"'
        name = toks[1][1]
        g = Group(name, parent=self.cur_group().name if self.cur_group() else None, line=ln.no)
        i = 2
        while i < len(toks):
            t = toks[i][1]
            if t == "collapse":
                g.collapsed = True
                i += 1
            elif t == "direction" and i + 1 < len(toks) and toks[i + 1][1] in ("tb", "lsrs"):
                g.direction = toks[i + 1][1]
                i += 2
            elif t == "class" and i + 1 < len(toks):
                g.classes.append(toks[i + 1][1])
                i += 2
            else:
                raise FlowError("E080", f"unexpected '{t}' in group header",
                                'options: direction tb|lsrs, class NAME, collapse')
        if self.doc.group(name):
            raise FlowError("E020", f"duplicate group name '{name}'", "group names must be unique")
        g.lane = self.lane.name if self.lane else None
        self.doc.groups.append(g)
        self.gstack.append(g)
        try:
            self.process(ln.children)
        finally:
            self.gstack.pop()

    def s_lane(self, ln: Line):
        s = ln.text.rstrip()
        toks = tokenize(s[:-1]) if s.endswith(":") else []
        if len(toks) != 2 or toks[1][0] != "str":
            raise FlowError("E080", "bad lane header", 'write: lane "Name":')
        if self.gstack:
            raise FlowError("E080", "a lane cannot sit inside a group", "put the group inside the lane instead")
        if self.lane:
            raise FlowError("E080", "lanes cannot be nested", "")
        name = toks[1][1]
        lane = self.doc.lane(name)
        if lane is None:
            lane = Lane(name, line=ln.no)
            self.doc.lanes.append(lane)
        self.lane = lane
        try:
            self.process(ln.children)
        finally:
            self.lane = None

    # -- edges -----------------------------------------------------------
    def parse_endpoint(self, toks, i):
        """-> (endpoint_string, port, next_index) or None"""
        if i >= len(toks):
            return None
        k, v = toks[i][0], toks[i][1]
        if k == "word" and v == "group" and i + 1 < len(toks) and toks[i + 1][0] == "str":
            return GROUP_PREFIX + toks[i + 1][1], None, i + 2
        if k != "word":
            return None
        base, dot, port = v.partition(".")
        if not re.match(r"^[A-Za-z][A-Za-z0-9_\-]*$", base):
            return None
        return base, (port if dot else None), i + 1

    def edge_line_ok(self, toks) -> bool:
        return any(t[0] == "word" and t[1] in OP_ALIAS for t in toks)

    def is_terminator(self, toks, i):
        if i >= len(toks):
            return True
        t = toks[i]
        return t[0] == "comma" or (t[0] == "word" and (t[1] in OP_ALIAS or t[1] in ("when", "label", "len", "weight")))

    def parse_edge_line(self, text: str, ln: Line):
        edge_id = None
        m = re.match(r"^edge\s+([^\s:]+)\s*:\s*(.*)$", text)
        if m:
            edge_id, text = m.group(1), m.group(2)
            if not ID_RE.match(edge_id) or edge_id in RESERVED:
                raise FlowError("E022", f"invalid edge ID '{edge_id}'", "letters, digits, underscore")
        toks = tokenize(text)
        ep = self.parse_endpoint(toks, 0)
        if ep is None:
            raise FlowError("E080", "an edge must start with a node ID or group \"Name\"", "")
        cur, cur_port, i = ep
        edges = []
        while i < len(toks):
            t = toks[i]
            if not (t[0] == "word" and t[1] in OP_ALIAS):
                raise FlowError("E030", f"unknown operator '{t[1]}'",
                                "operators: -> -.-> ==> -- -.- === then dotted thick link dots bold both back hide")
            op = OP_ALIAS[t[1]]
            i += 1
            while True:
                ep = self.parse_endpoint(toks, i)
                if ep is None:
                    raise FlowError("E080", f"expected a node ID after '{t[1]}'", "")
                dst, dport, i = ep
                e = dict(src=cur, sp=cur_port, dst=dst, dp=dport, op=op, label=None, len=1, weight=1)
                i = self.parse_tail(toks, i, text, e)
                edges.append(e)
                if i < len(toks) and toks[i][0] == "comma":
                    i += 1
                    continue
                break
            cur, cur_port = dst, dport
        return edge_id, edges

    def parse_tail(self, toks, i, text, e):
        while i < len(toks):
            t = toks[i]
            if t[0] == "word" and t[1] == "when":
                j = i + 1
                if j >= len(toks):
                    raise FlowError("E080", "'when' needs label text", "A -> B when Yes")
                start = toks[j][2]
                end = start
                while j < len(toks):
                    tj = toks[j]
                    if tj[0] == "comma":
                        ep = self.parse_endpoint(toks, j + 1)
                        if ep and self.is_terminator(toks, ep[2]):
                            break
                    if tj[0] == "word" and tj[1] in ("len", "weight") and j + 1 < len(toks) \
                            and toks[j + 1][0] == "word" and to_num(toks[j + 1][1]) is not None:
                        break
                    end = tj[3]
                    j += 1
                raw = text[start:end].strip()
                if len(raw) >= 2 and raw[0] == raw[-1] == '"':
                    raw = raw[1:-1]
                e["label"] = unescape(raw)
                i = j
            elif t[0] == "word" and t[1] == "label":
                if i + 1 >= len(toks) or toks[i + 1][0] != "str":
                    raise FlowError("E080", "'label' text must be quoted", 'A -> B label "Yes"')
                e["label"] = toks[i + 1][1]
                i += 2
            elif t[0] == "word" and t[1] in ("len", "weight"):
                if i + 1 >= len(toks) or to_num(toks[i + 1][1]) is None:
                    raise FlowError("E080", f"'{t[1]}' needs a number", f"{t[1]} 2")
                e[t[1]] = to_num(toks[i + 1][1])
                i += 2
            else:
                break
        if i < len(toks) and toks[i][0] == "word" and toks[i][1] not in OP_ALIAS:
            raise FlowError("E080", f"unexpected text '{toks[i][1]}' after an edge target",
                            "use 'when TEXT' to label an edge")
        return i

    def add_edge(self, src, dst, op="->", label=None, ln=0, style=None, sp=None, dp=None,
                 eid=None, ln_obj=None, len_=1, weight=1):
        lno = ln if isinstance(ln, int) else ln.no
        for ep in (src, dst):
            if not ep.startswith(GROUP_PREFIX):
                self.ensure_node(ep, ln)
        for p in (sp, dp):
            if p is not None and p not in PORTS:
                raise FlowError("E033", f"unknown port '{p}'",
                                "ports: top, bottom, left, right (diamonds also top-left ...)")
        e = Edge(eid or "", src, dst, op, label, sp, dp, style or {}, line=lno, len=len_, weight=weight)
        e.user_id = eid is not None
        self.doc.edges.append(e)
        return e

    def edge_stmt(self, ln: Line):
        edge_id, items = self.parse_edge_line(ln.text, ln)
        if edge_id is not None and len(items) != 1:
            raise FlowError("E031", "an edge ID can only be used on a single edge",
                            "split the chain: one 'edge ID: A -> B' per line")
        for it in items:
            self.add_edge(it["src"], it["dst"], it["op"], it["label"], ln, sp=it["sp"], dp=it["dp"],
                          eid=edge_id, len_=it["len"], weight=it["weight"])

    def id_stmt(self, ln: Line):
        text = ln.text
        w = fword(text)
        toks = tokenize(text)
        words = [t[1] for t in toks]
        m = re.match(r"^loop\s+back\s+to\s+(\S+)\s+from\s+(\S+)(.*)$", text)
        if m:
            return self.edge_stmt(Line(ln.no, ln.indent, f"{m.group(2)} -> {m.group(1)}{m.group(3)}", ln.file))
        if w in ("edge", "group") or self.edge_line_ok(toks):
            return self.edge_stmt(ln)
        if re.search(r"\S(->|-\.->|==>|--|-\.-|===)|(->|-\.->|==>|--|-\.-|===)\S", text):
            raise FlowError("E030", "unknown operator or missing spaces around an operator",
                            "write operators with spaces on both sides: A -> B")
        m = re.match(r"^([A-Za-z]\w*)\s+is\s+(.+)$", text)
        if m:
            names = [x.strip() for x in m.group(2).split(",") if x.strip()]
            return self.queue(ln, lambda: self.apply_classes(names, [m.group(1)], ln))
        m = re.match(r'^([A-Za-z]\w*)\s+in\s+lane\s+"(.*)"$', text)
        if m:
            return self.queue(ln, lambda: self.assign_lane(m.group(1), m.group(2), ln))
        m = re.match(r"^([A-Za-z]\w*)\s+(fails|passes)\s+to\s+([A-Za-z]\w*)$", text)
        if m:
            bad = m.group(2) == "fails"
            self.add_edge(m.group(1), m.group(3), "-.->" if bad else "->", "failed" if bad else "ok", ln,
                          style={"color": "danger" if bad else "success", **({"dash": True} if bad else {})})
            return
        if len(words) >= 2 and words[0] == w and ID_RE.match(w):
            raise FlowError("E030", f"unknown operator or statement '{words[1]}'",
                            "operators: -> -.-> ==> -- -.- === then dotted thick link dots bold both back hide")
        raise FlowError("E080", f"cannot understand '{text[:40]}'", "check the statement keyword and spelling")

    def queue(self, ln, fn):
        self.later.append((ln, fn))

    # -- functions -------------------------------------------------------
    def id_list(self, text: str, what="node list") -> List[str]:
        out = []
        for p in text.split(","):
            p = p.strip()
            if not p:
                continue
            if not re.match(r"^[A-Za-z][A-Za-z0-9_\-]*$", p):
                raise FlowError("E022", f"invalid ID '{p}' in {what}", "letters, digits and underscore only")
            out.append(p)
        if not out:
            raise FlowError("E080", f"empty {what}", "")
        return out

    def s_chain(self, ln):
        ids = self.id_list(ln.text[5:], "chain")
        for a, b in zip(ids, ids[1:]):
            self.add_edge(a, b, "->", None, ln)
        if len(ids) == 1:
            self.ensure_node(ids[0], ln)

    def s_fanout(self, ln):
        m = re.match(r"^fanout\s+(\S+)\s+to\s+(.+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad fanout", "write: fanout A to B, C, D")
        for t in self.id_list(m.group(2)):
            self.add_edge(m.group(1), t, "->", None, ln)

    def s_fanin(self, ln):
        m = re.match(r"^fanin\s+(.+?)\s+to\s+(\S+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad fanin", "write: fanin B, C, D to E")
        for s in self.id_list(m.group(1)):
            self.add_edge(s, m.group(2), "->", None, ln)

    def s_cycle(self, ln):
        ids = self.id_list(ln.text[5:], "cycle")
        for a, b in zip(ids, ids[1:] + ids[:1]):
            self.add_edge(a, b, "->", None, ln)

    def s_ask(self, ln):
        m = re.match(r"^ask\s+([^\s:]+)\s*:\s?(.*)$", ln.text)
        if not m:
            raise FlowError("E080", "bad ask header", "write: ask ID: Question")
        did = m.group(1)
        self.node_stmt(Line(ln.no, ln.indent, f"decide {did}: {m.group(2)}", ln.file))
        for ch in ln.children:
            text = self.interp(ch.text, ch)
            try:
                toks = tokenize(text)
                if len(toks) < 2 or toks[-1][0] != "word":
                    raise FlowError("E080", "an answer line is: ANSWER TARGET", 'example: yes D   or   "not sure" F')
                target = toks[-1][1]
                raw = text[toks[0][2]:toks[-2][3]].strip()
                ans = toks[0][1] if len(toks) == 2 and toks[0][0] == "str" else raw
                if len(ans) >= 2 and ans[0] == ans[-1] == '"':
                    ans = ans[1:-1]
                self.add_edge(did, target, "->", unescape(ans), ch)
            except FlowError as e:
                self.err(e.code, ch, e.message, e.hint)

    def s_from(self, ln):
        m = re.match(r"^from\s+(\S+)\s*:$", ln.text)
        if not m:
            raise FlowError("E080", "bad from header", "write: from B:")
        self.ensure_node(m.group(1), ln)
        for ch in ln.children:
            text = self.interp(ch.text, ch)
            mm = re.match(r"^go\s+to\s+(.+)$", text)
            if not mm:
                self.err("E080", ch, "inside 'from' use: go to TARGET [when TEXT]", "")
                continue
            try:
                self.edge_stmt(Line(ch.no, ch.indent, f"{m.group(1)} -> {mm.group(1)}", ch.file))
            except FlowError as e:
                self.err(e.code, ch, e.message, e.hint)

    def s_parallel(self, ln):
        m = re.match(r"^parallel\s+(\S+)\s+to\s+(\S+)\s+via\s+(.+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad parallel", "write: parallel F to J via A, B, C")
        f, j = m.group(1), m.group(2)
        self.ensure_node(f, ln, "fork", from_edge=False)
        self.ensure_node(j, ln, "join", from_edge=False)
        for a in self.id_list(m.group(3)):
            self.add_edge(f, a, "->", None, ln)
            self.add_edge(a, j, "->", None, ln)

    def s_pipeline(self, ln):
        m = re.match(r"^pipeline\s+([A-Za-z]\w*)(\s+as\s+group)?\s*:$", ln.text)
        if not m:
            raise FlowError("E080", "bad pipeline header", "write: pipeline Name:   or   pipeline Name as group:")
        name, as_group = m.group(1), bool(m.group(2))
        prefix = name.lower()
        grp = None
        if as_group:
            grp = Group(name, parent=self.cur_group().name if self.cur_group() else None, line=ln.no)
            grp.lane = self.lane.name if self.lane else None
            if self.doc.group(name):
                raise FlowError("E020", f"duplicate group name '{name}'", "")
            self.doc.groups.append(grp)
            self.gstack.append(grp)
        ids = []
        try:
            for k, ch in enumerate(ln.children, 1):
                nid = f"{prefix}_{k}"
                self.node_stmt(Line(ch.no, ch.indent, f"block {nid}: {self.interp(ch.text, ch)}", ch.file))
                ids.append(nid)
        finally:
            if grp:
                self.gstack.pop()
        for a, b in zip(ids, ids[1:]):
            self.add_edge(a, b, "->", None, ln)

    def s_retry(self, ln):
        m = re.match(r"^retry\s+(\S+)\s+to\s+(\S+)\s+max\s+(\d+)(?:\s+when\s+(.+))?$", ln.text)
        if not m:
            raise FlowError("E080", "bad retry", "write: retry E to B max 3  [when TEXT]")
        label = unescape(m.group(4)) if m.group(4) else f"retry up to {m.group(3)}"
        self.add_edge(m.group(1), m.group(2), "-.->", label, ln)

    def s_merge(self, ln):
        m = re.match(r"^merge\s+(.+?)\s+into\s+(\S+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad merge", "write: merge A, B into M")
        self.ensure_node(m.group(2), ln, "junction", from_edge=False)
        for a in self.id_list(m.group(1)):
            self.add_edge(a, m.group(2), "->", None, ln)

    def s_split(self, ln):
        m = re.match(r"^split\s+(\S+)\s+into\s+(.+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad split", "write: split M into A, B")
        self.ensure_node(m.group(1), ln, "junction", from_edge=False)
        for a in self.id_list(m.group(2)):
            self.add_edge(m.group(1), a, "->", None, ln)

    def s_skip(self, ln):
        m = re.match(r"^skip\s+(\S+)\s+over\s+(\S+)\s+to\s+(\S+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad skip", "write: skip A over B to C")
        self.add_edge(m.group(1), m.group(3), "-.->", "skip", ln)
        mid = m.group(2)
        self.queue(ln, lambda: self.set_style("node", mid, {"state": "skipped"}, ln))

    # -- styling ---------------------------------------------------------
    def parse_targets(self, text: str):
        toks = tokenize(text)
        out, i = [], 0
        while i < len(toks):
            t = toks[i]
            if t[0] == "comma":
                i += 1
            elif t[0] == "word" and t[1] in ("group", "lane") and i + 1 < len(toks) and toks[i + 1][0] == "str":
                out.append((t[1], toks[i + 1][1]))
                i += 2
            elif t[0] == "word" and t[1] == "edge" and i + 1 < len(toks):
                out.append(("edge", toks[i + 1][1]))
                i += 2
            elif t[0] == "word":
                out.append(("node", t[1]))
                i += 1
            else:
                raise FlowError("E080", f"bad target '{t[1]}'", "")
        if not out:
            raise FlowError("E080", "missing target", "")
        return out

    def s_set(self, ln):
        rest = ln.text[3:].strip()
        c = first_colon(rest)
        if c < 0:
            raise FlowError("E080", "bad set statement", "write: set TARGET: PROP VALUE, FLAG")
        target, body = rest[:c].strip(), rest[c + 1:].strip()
        m = re.match(r"^all\s+(\w+)$", target)
        if m:
            if m.group(1) not in SHAPES:
                raise FlowError("E061", f"'set all' needs a shape keyword, got '{m.group(1)}'", "e.g. set all block: ...")
            st = parse_style_items(body, ln.no, NODE_PROPS, self.diags)
            self.queue(ln, lambda: self.doc.set_all.setdefault(m.group(1), {}).update(st))
            return
        (kind, name), = self.parse_targets(target)[:1]
        props = EDGE_PROPS if kind == "edge" else NODE_PROPS
        st = parse_style_items(body, ln.no, props, self.diags)
        self.queue(ln, lambda: self.set_style(kind, name, st, ln))

    def find_target(self, kind, name, ln):
        d = self.doc
        obj = {"node": d.node, "edge": d.edge, "group": d.group, "lane": d.lane}[kind](name)
        if obj is None:
            raise FlowError("E081" if kind != "group" and kind != "lane" else "E032",
                            f"unknown {kind} '{name}'", "declare it first")
        return obj

    def set_style(self, kind, name, st, ln):
        self.find_target(kind, name, ln).style.update(st)

    def apply_classes(self, names, ids, ln):
        for nm in names:
            self.class_uses.append((nm, ln))
        for i in ids:
            obj = self.find_target("node", i, ln)
            for nm in names:
                obj.classes.append(nm)

    def s_apply(self, ln):
        m = re.match(r"^apply\s+(.+?)\s+to\s+(.+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad apply", "write: apply NAME to A, B, C")
        names = [x.strip() for x in m.group(1).split(",") if x.strip()]
        targets = self.parse_targets(m.group(2))

        def run():
            for nm in names:
                self.class_uses.append((nm, ln))
            for kind, name in targets:
                obj = self.find_target(kind, name, ln)
                obj.classes.extend(names)
        self.queue(ln, run)

    def assign_lane(self, nid, lane_name, ln):
        n = self.find_target("node", nid, ln)
        lane = self.doc.lane(lane_name)
        if lane is None:
            raise FlowError("E032", f"unknown lane '{lane_name}'", "declare it with: lane \"Name\":")
        if n.lane and self.doc.lane(n.lane) and nid in self.doc.lane(n.lane).members:
            self.doc.lane(n.lane).members.remove(nid)
        n.lane = lane_name
        lane.members.append(nid)

    def is_note_annotation(self, text: str) -> bool:
        return bool(re.match(r"^note\s+(on|over|left\s+of|right\s+of)\s+[A-Za-z]", text))

    def s_note(self, ln):
        m = re.match(r"^note\s+(on|over|left\s+of|right\s+of)\s+(.+?)\s*:\s?(.*)$", ln.text)
        if not m:
            raise FlowError("E080", "bad note", "write: note on A: text")
        kind = m.group(1).split()[0]
        ids = self.id_list(m.group(2))
        note = Note(kind, ids, unescape(m.group(3)), ln.no)
        self.doc.notes.append(note)
        # keep notes inside the group of their first target for layout purposes (resolved later)

    def s_legend(self, ln):
        m = re.match(r"^legend(?:\s+at\s+(\S+))?\s*:$", ln.text)
        if not m:
            raise FlowError("E080", "bad legend header", "write: legend:   or   legend at top-right:")
        pos = m.group(1) or "bottom-left"
        if pos not in ("top-left", "top-right", "bottom-left", "bottom-right"):
            raise FlowError("E012", f"bad legend position '{pos}'", "top-left, top-right, bottom-left, bottom-right")
        entries = []
        for ch in ln.children:
            text = self.interp(ch.text, ch)
            m2 = re.match(r"^(.*?)\s=\s*(.*)$", text) or re.match(r"^(.*?)=(.*)$", text)
            if not m2:
                self.err("E080", ch, "legend entry is: STYLE = TEXT", "fill #ffe0e0 = Failure path")
                continue
            st = parse_style_items(m2.group(1), ch.no, NODE_PROPS, self.diags)
            entries.append({"style": st, "text": unescape(m2.group(2).strip())})
        self.doc.legend = {"position": pos, "entries": entries}

    def s_tag(self, ln):
        m = re.match(r"^tag\s+(.+?)\s*:\s*(.+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad tag", "write: tag A, B: main, detail")
        ids = self.id_list(m.group(1))
        tags = [t.strip() for t in m.group(2).split(",") if t.strip()]

        def run():
            for i in ids:
                n = self.find_target("node", i, ln)
                for t in tags:
                    if t not in n.tags:
                        n.tags.append(t)
        self.queue(ln, run)

    def s_layer(self, ln):
        m = re.match(r'^layer\s+"(.*?)"\s*:\s*(.+)$', ln.text)
        if not m:
            raise FlowError("E080", "bad layer", 'write: layer "Name": A, B, C')
        self.doc.layers.setdefault(m.group(1), []).extend(self.id_list(m.group(2)))

    def _meta(self, ln, attr):
        m = re.match(r"^\w+\s+(\S+?)\s*:\s*(.*)$", ln.text)
        if not m:
            raise FlowError("E080", f"bad {attr} statement", f"write: {attr} A: value")
        val = m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] == '"':
            val = val[1:-1]
        nid = m.group(1)
        self.queue(ln, lambda: setattr(self.find_target("node", nid, ln), attr, unescape(val)))

    def s_link(self, ln):
        self._meta(ln, "link")

    def s_tooltip(self, ln):
        self._meta(ln, "tooltip")

    def s_click(self, ln):
        self._meta(ln, "click")

    # -- layout controls -------------------------------------------------
    def s_same(self, ln):
        m = re.match(r"^same\s+rank\s+(.+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad statement", "write: same rank A, B, C")
        self.doc.constraints.setdefault("same_rank", []).append(self.id_list(m.group(1)))

    def s_order(self, ln):
        m = re.match(r"^order\s+(\S+)\s+before\s+(\S+)$", ln.text)
        if m:
            self.doc.constraints.setdefault("order", []).append([m.group(1), m.group(2)])
            return
        self.doc.constraints.setdefault("order", []).append(self.id_list(ln.text[5:]))

    def s_spacing(self, ln):
        m = re.match(r"^spacing\s+(rank|node|group)\s+([\d.]+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad spacing", "write: spacing rank 80")
        self.doc.constraints.setdefault("spacing", {})[m.group(1)] = float(m.group(2))

    def s_pin(self, ln):
        m = re.match(r"^pin\s+(\S+)\s+at\s+(-?[\d.]+)\s*,\s*(-?[\d.]+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad pin", "write: pin A at 100, 40")
        self.doc.constraints.setdefault("pins", {})[m.group(1)] = (float(m.group(2)), float(m.group(3)))

    def s_align(self, ln):
        m = re.match(r"^align\s+(.+?)\s+(left|center|right|top|middle|bottom)$", ln.text)
        if not m:
            raise FlowError("E080", "bad align", "write: align A, B, C center")
        self.doc.constraints.setdefault("aligns", []).append((self.id_list(m.group(1)), m.group(2)))

    def s_wrap(self, ln):
        m = re.match(r"^wrap\s+after\s+(\d+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad wrap", "write: wrap after 5")
        self.doc.constraints["wrap_after"] = int(m.group(1))

    def s_keep(self, ln):
        m = re.match(r"^keep\s+(together|apart)\s+(.+)$", ln.text)
        if not m:
            raise FlowError("E080", "bad keep", "write: keep together A, B")
        self.doc.constraints.setdefault("keep_" + m.group(1), []).append(self.id_list(m.group(2)))

    # -- views -----------------------------------------------------------
    def s_view(self, ln):
        s = ln.text.rstrip()
        toks = tokenize(s[:-1]) if s.endswith(":") else []
        if len(toks) != 2 or toks[1][0] != "str":
            raise FlowError("E080", "bad view header", 'write: view "Name":')
        v = View(toks[1][1], line=ln.no)
        for ch in ln.children:
            try:
                t = tokenize(self.interp(ch.text, ch))
                w = t[0][1]
                if w in ("show", "hide", "collapse", "expand"):
                    if w in ("collapse", "expand"):
                        kind, val = "group", t[2][1] if len(t) > 2 else None
                        if len(t) < 3 or t[1][1] != "group":
                            raise FlowError("E080", f"'{w}' takes: {w} group \"Name\"", "")
                    else:
                        if len(t) < 3 or t[1][1] not in ("tag", "layer", "node", "group"):
                            raise FlowError("E080", f"'{w}' takes: tag NAME | layer \"Name\" | node ID | group \"Name\"", "")
                        kind, val = t[1][1], t[2][1]
                    v.rules.append((w, kind, val, ch.no))
                elif w in ("share_layout", "theme", "direction", "style") and len(t) == 2:
                    val = t[1][1]
                    if w == "share_layout" and val not in LAYOUTS:
                        raise FlowError("E011", "share_layout must be 16/9, 4/5, 2/3, 1/1 or free", "")
                    if w == "direction" and val not in ("tb", "lsrs"):
                        raise FlowError("E080", "direction must be tb or lsrs", "")
                    v.overrides[w] = val
                else:
                    raise FlowError("E080", f"unknown view rule '{ch.text}'",
                                    "show/hide/collapse/expand, share_layout, theme, direction")
            except FlowError as e:
                self.err(e.code, ch, e.message, e.hint)
            except IndexError:
                self.err("E080", ch, "incomplete view rule", "")
        self.doc.views.append(v)

    # -- finalize ----------------------------------------------------------
    def finalize(self):
        d = self.doc
        used = set()
        for e in d.edges:
            if e.user_id:
                if e.id in used:
                    self.err("E020", e.line, f"duplicate edge ID '{e.id}'", "edge IDs must be unique")
                used.add(e.id)
        k = 0
        for e in d.edges:
            if not e.user_id:
                while f"e{k}" in used:
                    k += 1
                e.id = f"e{k}"
                used.add(e.id)
                k += 1
        for ln, fn in self.later:
            try:
                fn()
            except FlowError as ex:
                self.err(ex.code, ln, ex.message, ex.hint)
        for g in d.groups:
            for c in g.classes:
                self.class_uses.append((c, g.line))
        for nm, ln in self.class_uses:
            if nm not in d.classes:
                self.err("E060", ln, f"unknown class '{nm}'",
                         f"did you mean '{closest(nm, d.classes)}'?" if closest(nm, d.classes)
                         else "define it with: class NAME:")
        used_classes = {nm for nm, _ in self.class_uses}
        for nm, lno in self.class_lines.items():
            if nm not in used_classes:
                self.err("W060", lno, f"class '{nm}' is defined but never used", "remove it or apply it")
        for e in d.edges:
            for ep in (e.src, e.dst):
                if ep.startswith(GROUP_PREFIX) and not d.group(ep[len(GROUP_PREFIX):]):
                    self.err("E032", e.line, f"edge refers to unknown group '{ep[len(GROUP_PREFIX):]}'",
                             "declare the group first")
        for name, ids in d.layers.items():
            for i in ids:
                if i not in self.nid:
                    self.err("E081", 0, f"layer '{name}' refers to unknown node '{i}'", "")
        tags = {t for n in d.nodes for t in n.tags}
        for v in d.views:
            for act, kind, val, lno in v.rules:
                bad = (kind == "tag" and val not in tags) or (kind == "layer" and val not in d.layers) or \
                      (kind == "group" and not d.group(val)) or (kind == "node" and val not in self.nid)
                if bad:
                    self.err("E070", lno, f"view '{v.name}' refers to unknown {kind} '{val}'", "")
        for n in d.notes:
            for t in n.targets:
                if t not in self.nid:
                    self.err("E081", n.line, f"note refers to unknown node '{t}'", "")
        c = d.constraints
        refs = [i for g in c.get("same_rank", []) + c.get("order", []) + c.get("keep_together", [])
                + c.get("keep_apart", []) for i in g] + list(c.get("pins", {})) \
            + [i for ids, _ in c.get("aligns", []) for i in ids]
        for i in refs:
            if i not in self.nid:
                self.err("E081", 0, f"layout control refers to unknown node '{i}'", "")
        h = d.header
        d.direction = self.flow_dir or h.get("direction-default") or "tb"
        if h.get("theme") == "custom":
            missing = [k for k in ("primary", "surface", "ink") if k not in d.palette]
            if missing:
                self.err("E012", 0, "theme custom needs a palette block with: " + ", ".join(missing),
                         "palette:\n    primary #1f6feb\n    surface #ffffff\n    ink #1f2328")
        lint(d)
        strict = bool(d.devas("strict"))
        if strict:
            for x in d.diagnostics:
                if x.severity == "warning":
                    x.severity = "error"
        d.diagnostics.sort(key=lambda x: (x.severity != "error", x.line))


# --------------------------------------------------------------------------- colours
NAMED_RGB = {"white": "#ffffff", "black": "#000000", "red": "#ff0000", "green": "#008000",
             "blue": "#0000ff", "yellow": "#ffff00", "orange": "#ffa500", "purple": "#800080",
             "gray": "#808080", "grey": "#808080", "pink": "#ffc0cb", "navy": "#000080",
             "teal": "#008080", "lime": "#00ff00", "silver": "#c0c0c0", "maroon": "#800000",
             "olive": "#808000", "aqua": "#00ffff", "cyan": "#00ffff", "magenta": "#ff00ff",
             "brown": "#a52a2a", "gold": "#ffd700", "lightgray": "#d3d3d3", "lightgrey": "#d3d3d3",
             "darkgray": "#a9a9a9", "lightblue": "#add8e6", "lightgreen": "#90ee90",
             "darkblue": "#00008b", "darkgreen": "#006400", "darkred": "#8b0000",
             "crimson": "#dc143c", "coral": "#ff7f50", "salmon": "#fa8072", "tomato": "#ff6347",
             "khaki": "#f0e68c", "ivory": "#fffff0", "beige": "#f5f5dc", "lavender": "#e6e6fa",
             "violet": "#ee82ee", "indigo": "#4b0082", "skyblue": "#87ceeb", "steelblue": "#4682b4",
             "slategray": "#708090", "whitesmoke": "#f5f5f5", "gainsboro": "#dcdcdc"}


def parse_color(c: str):
    """-> (r, g, b) 0-255 or None if not resolvable."""
    if not c:
        return None
    c = c.strip().lower()
    c = NAMED_RGB.get(c, c)
    m = HEX_RE.match(c)
    if not m:
        return None
    h = m.group(1)
    if len(h) in (3, 4):
        h = "".join(ch * 2 for ch in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def luminance(rgb) -> float:
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(c1: str, c2: str):
    a, b = parse_color(c1), parse_color(c2)
    if a is None or b is None:
        return None
    l1, l2 = sorted((luminance(a), luminance(b)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


# --------------------------------------------------------------------------- style merge
def merged_props(doc: Document, obj, shape=None) -> dict:
    """Explicit properties of a node/edge/group/lane: set-all, then classes, then set."""
    out = {}
    if shape and shape in doc.set_all:
        out.update(doc.set_all[shape])
    for c in getattr(obj, "classes", []):
        out.update(doc.classes.get(c, {}))
    out.update(obj.style)
    return out


# --------------------------------------------------------------------------- lint
def _adjacency(doc: Document):
    members = {}
    for g in doc.groups:
        members[g.name] = list(g.members)
    out, inc = {}, {}

    def expand(ep):
        if ep.startswith(GROUP_PREFIX):
            return members.get(ep[len(GROUP_PREFIX):], [])
        return [ep]
    for e in doc.edges:
        und = e.op in ("--", "-.-", "===", "both")
        for a in expand(e.src):
            for b in expand(e.dst):
                out.setdefault(a, set()).add(b)
                inc.setdefault(b, set()).add(a)
                if und:
                    out.setdefault(b, set()).add(a)
                    inc.setdefault(a, set()).add(b)
    return out, inc


def _sccs(nodes, out):
    index, low, onst, st, res, cnt = {}, {}, set(), [], [], [0]
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(sorted(out.get(root, ()))))]
        index[root] = low[root] = cnt[0]
        cnt[0] += 1
        st.append(root)
        onst.add(root)
        while work:
            v, it = work[-1]
            adv = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = cnt[0]
                    cnt[0] += 1
                    st.append(w)
                    onst.add(w)
                    work.append((w, iter(sorted(out.get(w, ())))))
                    adv = True
                    break
                if w in onst:
                    low[v] = min(low[v], index[w])
            if adv:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = st.pop()
                    onst.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                res.append(comp)
    return res


def lint(doc: Document):
    D = doc.diagnostics
    strict = bool(doc.devas("strict"))
    nodes = {n.id: n for n in doc.nodes}
    h = doc.header
    if h.get("engine") == "manual":
        pins = doc.constraints.get("pins", {})
        for n in doc.nodes:
            if n.id not in pins:
                D.append(Diagnostic("E040", n.line, f"engine manual: node '{n.id}' has no pin",
                                    f"add: pin {n.id} at X, Y"))
    if h.get("engine") != "elk":
        for k in ELK_ONLY:
            if k in h:
                D.append(Diagnostic("W050", 0, f"ELK option '{k}' is ignored because engine is not elk", ""))
    if strict:
        for n in doc.nodes:
            if n.auto and n.from_edge:
                D.append(Diagnostic("W001", n.line, f"node '{n.id}' was created automatically from an edge",
                                    f"declare it: block {n.id}: Text"))
    for n in doc.nodes:
        if len(n.text) > 120:
            D.append(Diagnostic("W003", n.line, f"very long label on '{n.id}' ({len(n.text)} characters)",
                                "move detail into a note"))
    seen = {}
    for e in doc.edges:
        k = (e.src, e.dst, e.label)
        if k in seen:
            D.append(Diagnostic("W005", e.line, f"duplicate edge {e.src} to {e.dst} with the same label", ""))
        seen[k] = True
    out, inc = _adjacency(doc)
    plain = {i for i, n in nodes.items() if n.shape not in ("text", "note")}
    for n in doc.nodes:
        if n.shape == "decide":
            outs = [e for e in doc.edges if e.src == n.id]
            if len(outs) < 2:
                D.append(Diagnostic("W030", n.line, f"decision '{n.id}' has fewer than two outgoing edges",
                                    "add the missing branch"))
            for e in outs:
                if not e.label:
                    D.append(Diagnostic("W031", e.line, f"branch from decision '{n.id}' has no label",
                                        "add: when Yes / when No"))
    starts = [n.id for n in doc.nodes if n.shape == "start"]
    if doc.nodes and not starts:
        D.append(Diagnostic("W033", 0, "no start node", "declare one with: start A: Start"))
    if len(starts) > 1:
        D.append(Diagnostic("W034", nodes[starts[1]].line, f"{len(starts)} start nodes found", ""))
    isolated = {i for i in plain if not out.get(i) and not inc.get(i)}
    for i in sorted(isolated, key=lambda x: nodes[x].line):
        D.append(Diagnostic("W035", nodes[i].line, f"node '{i}' has no edges", "connect it or remove it"))
    if starts:
        seen_n, stack = set(starts), list(starts)
        while stack:
            v = stack.pop()
            for w in out.get(v, ()):
                if w not in seen_n:
                    seen_n.add(w)
                    stack.append(w)
        for i in plain:
            if i not in seen_n and i not in isolated and nodes[i].shape not in ("start",):
                D.append(Diagnostic("W032", nodes[i].line, f"node '{i}' is unreachable from any start", ""))
    for i in plain:
        n = nodes[i]
        if inc.get(i) and not out.get(i) and n.shape not in ("stop", "junction", "join") :
            D.append(Diagnostic("W037", n.line, f"'{i}' is a dead end but not a stop node",
                                f"declare it as: stop {i}: ..."))
    for comp in _sccs([n.id for n in doc.nodes], out):
        s = set(comp)
        if len(comp) > 1 or comp[0] in out.get(comp[0], ()):
            exits = any(w not in s for v in comp for w in out.get(v, ()))
            if not exits and not any(nodes[v].shape == "stop" for v in comp if v in nodes):
                first = min(comp, key=lambda x: nodes[x].line if x in nodes else 0)
                D.append(Diagnostic("W036", nodes[first].line if first in nodes else 0,
                                    "cycle with no exit: " + ", ".join(sorted(comp)[:6]),
                                    "add an edge leaving the loop"))
    if len(doc.nodes) > 2000:
        D.append(Diagnostic("W070", 0, f"{len(doc.nodes)} nodes: rendering may be slow", ""))
    if h.get("theme") == "custom" and all(k in doc.palette for k in ("surface", "ink")):
        cr = contrast(doc.palette["ink"], doc.palette["surface"])
        if cr is not None and cr < 4.5:
            D.append(Diagnostic("W040", 0, f"palette text contrast is {cr:.1f}:1 (minimum 4.5:1)",
                                "darken ink or lighten surface"))
    for n in doc.nodes:
        p = merged_props(doc, n, n.shape)
        f = p.get("fill", "").split(" to ")[0]
        if p.get("text-color") and f:
            cr = contrast(p["text-color"], f)
            if cr is not None and cr < 4.5:
                D.append(Diagnostic("W040", n.line, f"text contrast on '{n.id}' is {cr:.1f}:1 (minimum 4.5:1)", ""))


# --------------------------------------------------------------------------- public API
def make_loader(base_dir: Optional[str] = None, files: Optional[Dict[str, str]] = None):
    def load(path: str) -> str:
        if files and path in files:
            return files[path]
        if base_dir is None:
            raise FileNotFoundError(path)
        full = os.path.normpath(os.path.join(base_dir, path))
        with open(full, "r", encoding="utf-8") as fh:
            return fh.read()
    return load


def parse(source: str, loader=None, filename: Optional[str] = None, base_dir: Optional[str] = None,
          files: Optional[Dict[str, str]] = None, strict: Optional[bool] = None) -> Document:
    """Parse flow source text. Never raises for syntax problems: see doc.errors / doc.diagnostics."""
    if loader is None and (base_dir or files):
        loader = make_loader(base_dir, files)
    b = Builder(loader, filename)
    doc = b.run(source)
    if strict and not doc.devas("strict"):
        for x in doc.diagnostics:
            if x.severity == "warning":
                x.severity = "error"
        doc.header.setdefault("devas", {})["strict"] = True
    return doc


def parse_file(path: str, strict: Optional[bool] = None) -> Document:
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    return parse(text, base_dir=os.path.dirname(os.path.abspath(path)), filename=os.path.basename(path),
                 strict=strict)


def check(doc: Document) -> List[Diagnostic]:
    """All diagnostics for a parsed document (errors first, then warnings by line)."""
    return list(doc.diagnostics)


def format_source(text: str) -> str:
    """Light formatter: 4-space indentation, no trailing spaces, tidy blank lines."""
    lines = [l.rstrip().replace("\t", "    ") for l in text.replace("\r\n", "\n").split("\n")]
    out, prev_kind = [], None

    def kind(s):
        w = fword(s.strip())
        if w in SHAPES:
            return "decl"
        if w in ("flowchart",):
            return "flow"
        if re.search(r"\s(->|-\.->|==>|--|-\.-|===|then|dotted|thick|link|dots|bold|both|back|hide)\s", s) \
                or w in ("chain", "fanout", "fanin", "cycle", "retry", "merge", "split", "skip", "parallel"):
            return "edge"
        if w in ("set", "apply", "class"):
            return "style"
        return "other"
    for ln in lines:
        if not ln.strip():
            if out and out[-1] != "":
                out.append("")
            continue
        indent = len(ln) - len(ln.lstrip(" "))
        ln = " " * ((indent + 2) // 4 * 4) + ln.lstrip(" ")
        k = kind(ln) if indent == 0 else prev_kind
        if indent == 0 and prev_kind is not None and k != prev_kind and out and out[-1] != "" \
                and (k in ("edge", "style", "flow") or prev_kind == "flow"):
            out.append("")
        out.append(ln)
        if indent == 0:
            prev_kind = k
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"
