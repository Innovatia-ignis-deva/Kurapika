"""Kurapika Flow Syntax v2 engine: parse, check, and render diagrams."""
from __future__ import annotations

from typing import Dict, List, Optional

from .parser import (Diagnostic, Document, FlowError, FlowParseError, check, format_source, parse,
                     parse_file)
from .layout import Layout, compute_layout
from .render import paint

__all__ = ["parse", "parse_file", "check", "render", "render_views", "layout", "Document", "Diagnostic",
           "FlowParseError", "format_source", "NAME", "__version__"]
__version__ = "2.0.0"
NAME = "Kurapika"  # Public product name; keep the flowlang import package unchanged.


def layout(doc: Document, view: Optional[str] = None, **overrides) -> Layout:
    return compute_layout(doc, view, overrides)


def render(doc: Document, format: str = "svg", view: Optional[str] = None, share_layout: Optional[str] = None,
           export_width: Optional[int] = None, theme: Optional[str] = None, style: Optional[str] = None,
           engine: Optional[str] = None, direction: Optional[str] = None, export_dpi: Optional[int] = None,
           return_layout: bool = False, **extra):
    """Render a parsed document. Raises FlowParseError if the document has errors."""
    if doc.errors:
        raise FlowParseError(doc.errors)
    from . import export
    ov = dict(share_layout=share_layout, export_width=export_width, theme=theme, style=style, engine=engine,
              direction=direction, export_dpi=export_dpi, **extra)
    lay = compute_layout(doc, view, ov)
    out = export.convert(lay, format)
    return (out, lay) if return_layout else out


def render_views(doc: Document, format: str = "svg", **kw) -> Dict[str, object]:
    names = [v.name for v in doc.views] or [None]
    return {(n or "default"): render(doc, format=format, view=n, **kw) for n in names}
