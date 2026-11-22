"""Kurapika CLI: python -m flowlang render|check|ast|convert FILE [options]."""
from __future__ import annotations

import argparse
import json
import sys

from . import check, parse_file, render
from .parser import FlowParseError


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="Kurapika",
        description="Create, validate, and convert Flow Syntax diagrams.",
        epilog="Examples:\n"
               "  python -m flowlang render examples/quickstart.flow --out login.svg\n"
               "  python -m flowlang check examples/quickstart.flow\n"
               "  python -m flowlang convert examples/groups.flow --to mermaid",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    commands = {
        "render": "Render a diagram to SVG or the format inferred from --out.",
        "check": "Validate a Flow Syntax file and print diagnostics.",
        "ast": "Print the resolved diagram document as JSON.",
        "convert": "Convert a diagram to Mermaid or Graphviz DOT.",
    }
    for name, description in commands.items():
        p = sub.add_parser(name, help=description, description=description)
        p.add_argument("file", help="Flow Syntax source file")
        p.add_argument("--out", default=None, help="output path; use - for stdout (default)")
        p.add_argument("--view", default=None, help="named diagram view to render")
        p.add_argument("--share", default=None, help="canvas aspect ratio, such as 16/9 or 4/5")
        p.add_argument("--theme", default=None, help="diagram theme")
        p.add_argument("--style", default=None, help="diagram style")
        p.add_argument("--engine", default=None, help="layout engine")
        p.add_argument("--width", type=int, default=None, help="export width in pixels")
        p.add_argument("--dpi", type=int, default=None, help="raster export resolution")
        p.add_argument("--strict", action="store_true", help="treat warnings as errors")
        p.add_argument("--to", default=None, help="convert format: mermaid or dot (convert only)")
    a = ap.parse_args(argv)
    try:
        doc = parse_file(a.file, strict=True if a.strict else None)
    except OSError as e:
        print(e, file=sys.stderr)
        return 3
    for d in check(doc):
        print(d, file=sys.stderr)
    if doc.errors:
        return 1
    if a.cmd == "check":
        return 2 if (a.strict and doc.warnings) else 0
    if a.cmd == "ast":
        print(json.dumps(doc.to_dict(), indent=2))
        return 0
    fmt = "svg"
    if a.cmd == "convert":
        fmt = a.to or "mermaid"
    elif a.out and "." in a.out:
        fmt = a.out.rsplit(".", 1)[1].lower()
    try:
        out = render(doc, format=fmt, view=a.view, share_layout=a.share, theme=a.theme, style=a.style,
                     engine=a.engine, export_width=a.width, export_dpi=a.dpi)
    except (FlowParseError, Exception) as e:  # noqa: BLE001
        print(e, file=sys.stderr)
        return 3
    if a.out in (None, "-"):
        sys.stdout.write(out if isinstance(out, str) else out.decode("latin1"))
    else:
        with open(a.out, "wb" if isinstance(out, bytes) else "w", **({} if isinstance(out, bytes) else {"encoding": "utf-8"})) as fh:
            fh.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
