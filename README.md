# Kurapika

**Kurapika** is a declarative Domain-Specific Language (DSL) and deterministic vector layout engine built from scratch in Python to compile plain-text `.flow` scripts into structured, publication-ready diagrams.

---

## Why Kurapika?

Manual diagramming tools trap system logic inside proprietary GUIs, while generic auto-layout tools often tangle complex workflows. **Kurapika** treats diagrams as deterministic, version-controllable source code—chaining nodes, control loops, and multi-actor lanes through a custom compilation pipeline so architectures can be diffed, parameterized, and rendered reliably.

---

## System Architecture

```text
  .flow Source ──▶ flowlang/parser.py (AST) ──▶ flowlang/layout.py (Solver) ──▶ flowlang/render.py & export.py
