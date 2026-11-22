import os
import re
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import flowlang  # noqa: E402
from flowlang.layout import fit_canvas  # noqa: E402

EX = os.path.join(os.path.dirname(__file__), "..", "examples")


def codes(doc):
    return {d.code for d in doc.diagnostics}


def svg_of(src, **kw):
    doc = flowlang.parse(src)
    assert not doc.errors, [str(e) for e in doc.errors]
    out = flowlang.render(doc, **kw)
    ET.fromstring(out)
    return out


@pytest.mark.parametrize("name", sorted(f for f in os.listdir(EX) if f.endswith(".flow")))
def test_examples_render(name):
    doc = flowlang.parse(open(os.path.join(EX, name), encoding="utf-8").read())
    assert not doc.errors
    for v in [x.name for x in doc.views] or [None]:
        ET.fromstring(flowlang.render(doc, view=v))


def test_share_layout_worked_examples():
    for ratio, W, H, ox, oy in [("16/9", 880, 495, 40, 97.5), ("1/1", 880, 880, 40, 290),
                                ("4/5", 880, 1100, 40, 400), ("2/3", 880, 1320, 40, 510)]:
        c = fit_canvas(800, 300, {"share_layout": ratio, "share_margin": "5%"})
        assert (round(c["W"], 1), round(c["H"], 1), round(c["ox"], 1), round(c["oy"], 1)) == (W, H, ox, oy)
    for ratio, W, H, ox, oy in [("16/9", 1760, 990, 730, 45), ("1/1", 990, 990, 345, 45),
                                ("4/5", 792, 990, 246, 45), ("2/3", 660, 990, 180, 45)]:
        c = fit_canvas(300, 900, {"share_layout": ratio, "share_margin": "5%"})
        assert (round(c["W"]), round(c["H"]), round(c["ox"]), round(c["oy"])) == (W, H, ox, oy)


def test_export_width_height():
    c = fit_canvas(800, 300, {"share_layout": "4/5", "share_margin": "5%", "export_width": 1080})
    assert round(c["height_attr"]) == 1350


def test_free_layout_padding():
    c = fit_canvas(100, 50, {"share_layout": "free", "padding": 24})
    assert (c["W"], c["H"], c["ox"]) == (148, 98, 24)


def test_bad_share_layout():
    d = flowlang.parse("devas: share_layout: 16:9\nflowchart tb\nblock A: x\n")
    assert "E011" in codes(d)


def test_error_codes():
    assert "E001" in codes(flowlang.parse("block A: x\n"))
    assert "E002" in codes(flowlang.parse("flowchart tb\ngroup \"G\":\n\tblock A: x\n"))
    assert "E003" in codes(flowlang.parse("flowchart tb\ngroup \"G\":\n  block A: x\n"))
    assert "E020" in codes(flowlang.parse("flowchart tb\nblock A: x\nblock A: y\n"))
    assert "E022" in codes(flowlang.parse("flowchart tb\nblock a-b: x\n"))
    assert "E021" in codes(flowlang.parse("flowchart tb\nblock group: x\n"))
    assert "E050" in codes(flowlang.parse("flowchart tb\nblock A: $nope\n"))
    assert "E031" in codes(flowlang.parse("flowchart tb\nedge e1: A -> B -> C\n"))
    assert "E010" in codes(flowlang.parse("devas: bogus: 1\nflowchart tb\nblock A: x\n"))
    assert "E004" in codes(flowlang.parse("themes neutral\nflowchart tb\nblock A: x\n"))
    assert "E033" in codes(flowlang.parse("flowchart tb\nA.middle -> B\n"))
    assert "E060" in codes(flowlang.parse("flowchart tb\nblock A: x\nA is nothing\n"))
    assert "E040" in codes(flowlang.parse("engine manual\nflowchart tb\nblock A: x\n"))
    assert "E053" not in codes(flowlang.parse("flowchart tb\nblock A: x\n"))


def test_functions_expand():
    d = flowlang.parse("flowchart tb\nchain A, B, C\ncycle X, Y\nfanin P, Q to R\nmerge M1, M2 into J\n"
                       "split S into T, U\nskip A over B to C\nE fails to H\nE passes to N\nretry E to A max 2\n")
    pairs = {(e.src, e.dst) for e in d.edges}
    assert {("A", "B"), ("B", "C"), ("X", "Y"), ("Y", "X"), ("P", "R"), ("Q", "R"), ("M1", "J"), ("S", "T"),
            ("A", "C"), ("E", "H"), ("E", "N"), ("E", "A")} <= pairs
    assert d.node("B").style.get("state") == "skipped"


def test_deterministic_and_ids():
    src = open(os.path.join(EX, "full_feature.flow")).read()
    a, b = svg_of(src), svg_of(src)
    assert a == b
    assert 'id="flow-node-A"' in a and "<title" in a and "<desc" in a


def test_hand_drawn_seed_stable():
    src = "style hand-drawn\nflowchart tb\nstart A: a\nblock B: b\nA -> B\n"
    assert svg_of(src) == svg_of(src)
    assert svg_of(src) != svg_of("devas: seed: 5\n" + src)


def test_themes_and_styles():
    for th in ("default", "neutral", "forest", "dark", "redux-dark"):
        for stl in ("classic", "neo", "hand-drawn"):
            svg_of(f"theme {th}\nstyle {stl}\nflowchart tb\nstart A: a\ndecide B: ok\nstop C: z\nA -> B -> C\n")


def test_every_shape_and_edge_kind():
    shapes = "block start stop pill decide io sub db doc docs manual delay connector prepare cloud note junction fork join text image".split()
    lines = ["flowchart lsrs"] + [f"{s} n{i}: Shape {s}" if s not in ("junction", "fork", "join") else f"{s} n{i}"
                                  for i, s in enumerate(shapes)]
    ops = ["->", "-.->", "==>", "--", "-.-", "===", "then", "dotted", "thick", "link", "dots", "bold", "both", "back", "hide"]
    for i, op in enumerate(ops):
        lines.append(f"n{i} {op} n{i + 1} when {op}")
    lines.append("n0 -> n0 when loop")
    svg_of("\n".join(lines) + "\n")


def test_groups_nested_collapse_and_edges_to_group():
    src = '''flowchart tb
start S: Go
group "Outer":
    block A: a
    group "Inner":
        block B: b
        block C: c
        B -> C
    A -> B
block Z: z
S -> A
S -> group "Inner"
group "Outer" -> Z
C -> Z
'''
    svg_of(src)
    svg_of(src.replace('group "Inner":', 'group "Inner" collapse:'))
    svg_of(src.replace('group "Outer":', 'group "Outer" direction lsrs:'))


def test_lanes_both_directions():
    for d in ("tb", "lsrs"):
        svg_of(f'''flowchart {d}
lane "A":
    start S: s
    block X: x
lane "B":
    block Y: y
    decide D: d
chain S, Y, D, X
D -> S when no
D -> X when yes
''')


def test_notes_same_rank_order_pin_align_grid():
    svg_of('''flowchart tb
block A: a
block B: b
block C: c
block D: d
A -> B, C
C -> D
note right of B: right note
note left of C: left note
note over A, B: over
same rank B, C
order C before B
align A, D center
''')
    svg_of("flowchart tb\nblock A: a\nblock B: b\nA -> B\npin A at 300, 40\n")
    svg_of("devas: grid: 10\nflowchart tb\nblock A: a\nblock B: b\nA -> B\n")
    svg_of("engine manual\nflowchart tb\nblock A: a\nblock B: b\nA -> B\npin A at 0, 0\npin B at 200, 120\n")


def test_ports_len_weight_parallel_edges_loops():
    svg_of('''flowchart tb
block A: a
decide B: b
block C: c
A.right -> B.left when go
B.bottom-left -> C.top
A -> C len 3
A -> C weight 5 when heavy
A -> B
B -> A
C -> C when poll
E1 -> E1
''')


def test_views_autonumber_legend_watermark_autolayers():
    svg_of(open(os.path.join(EX, "views.flow")).read())
    svg_of('''devas: autonumber: both
devas: watermark: DRAFT
devas: watermark_pos: center
devas: background: transparent
devas: share_layout: 1/1
devas: share_fit: shrink
devas: export_width: 800
title: T
subtitle: S
caption: C
footer: F
flowchart tb
start A: a
block B: b
A -> B
tag B: x
layer "L": B
link A: "https://example.com"
tooltip A: hello
click A: do_it
set A: state done
set B: state failed
legend at top-right:
    fill #ffe0e0 = Fail
''')


def test_unsafe_link_not_emitted():
    out = svg_of('flowchart tb\nblock A: a\nlink A: "javascript:alert(1)"\n')
    assert "javascript" not in out


def test_text_is_escaped():
    out = svg_of('flowchart tb\nblock A: <b>&"x"</b> **bold** `m`\n')
    assert "&lt;b&gt;" in out


def test_imports_and_cycles():
    files = {"a.flow": 'let who = World\nimport "b.flow"\n', "b.flow": 'import "a.flow"\n'}
    d = flowlang.parse('import "a.flow"\nflowchart tb\nblock A: Hi $who\n', files=files)
    assert "E053" in codes(d)
    files = {"c.flow": 'let who = World\nclass k:\n    fill #fff\n'}
    d = flowlang.parse('import "c.flow"\nflowchart tb\nblock A: Hi $who\nA is k\n', files=files)
    assert not d.errors and d.node("A").text == "Hi World"


def test_converters():
    d = flowlang.parse(open(os.path.join(EX, "groups.flow")).read())
    assert "subgraph" in flowlang.render(d, format="mermaid")
    assert "digraph" in flowlang.render(d, format="dot")
    assert '"layout"' in flowlang.render(d, format="json")


def test_large_graph_speed():
    import time
    lines = ["flowchart tb", "start S: s"]
    for i in range(120):
        lines.append(f"block n{i}: node {i}")
    lines += [f"n{i} -> n{i + 1}" for i in range(119)] + [f"n{i} -> n{i + 7}" for i in range(0, 110, 3)]
    lines.append("S -> n0")
    t = time.time()
    svg_of("\n".join(lines) + "\n")
    assert time.time() - t < 20
