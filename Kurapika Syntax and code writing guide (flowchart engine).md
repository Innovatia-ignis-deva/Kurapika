# Flow Syntax v2 (flowchart engine)

Full specification for the custom structured English flowchart language and its renderer.
Raw reference. Written to be implemented in Python or JavaScript.

## 0. About this document

- Scope: flowcharts only. Other diagram types are out of scope for v2.
- Placeholders are written in CAPITAL LETTERS (ID, TEXT, N, HEX). No angle brackets are used anywhere.
- The only angle character used is the greater-than sign inside arrow operators such as `->`. The less-than sign is never used.
- Comparisons in rules and pseudocode are written in words (is less than, is greater than).
- Everything marked v1.1 is optional and can be left out of the first build.
- Everything marked reserved is a keyword set aside for future use. The parser must reject it as an ID.

## 1. Quick start

```
title: Login Flow
theme neutral
devas: share_layout: 4/5

flowchart tb

start A: Start
block B: Enter password
decide C: Password valid
block D: Open dashboard
block E: Show error
stop F: Done

A -> B -> C
C -> D when Yes
C -> E when No
E -> B
D -> F
```

Ten lines of structure produce a full diagram. Remove the `devas: share_layout` line and the renderer lays the diagram out freely.

## 2. File anatomy

A file has four zones, in this order. Zones can be empty except zone 3.

1. Header options: title, theme, style, engine, devas options, version.
2. Definitions: variables, classes, templates, imports, palettes.
3. The `flowchart` line (required, exactly once).
4. Body: nodes, edges, groups, lanes, functions, notes, views.

Rules:
- Header lines and definitions must appear before the `flowchart` line.
- Body statements must appear after it.
- Extension: `.flow`. Encoding: UTF-8. Line endings: LF or CRLF, both accepted.
- A file with no `flowchart` line is an error (E001).

## 3. Lexical rules

### 3.1 Lines and statements
- One statement per line.
- Blank lines are ignored.
- A line that starts with `+ ` (plus and a space) continues the previous line. The continuation text is joined with a single space.
- Maximum recommended line length: 120 characters. Not enforced.

### 3.2 Indentation
- Indentation is 4 spaces per level.
- Tabs are an error (E002).
- An indent that is not a multiple of 4 is an error (E003).
- Indentation only matters after a line that ends with a colon and opens a block (group, lane, class, view, template, repeat, ask, from, legend, palette).

### 3.3 Comments
```
# full line comment
note: full line comment
block A: Text   # trailing comment is allowed only after two or more spaces
```
- A `#` inside node text with a single space before it is literal text. A trailing comment needs two spaces before the `#`.
- Hex colors such as `#ff8800` are never comments. A `#` followed directly by 3, 6 or 8 hex digits inside a color position is a color.

### 3.4 Identifiers (IDs)
- Letters, digits and underscore only. Must start with a letter.
- Case-sensitive. `A` and `a` are different.
- v1 allowed hyphens. v2 does not. Hyphens collide with the operators `--` and `->`.
- Maximum length 64.
- An ID must not equal a reserved word (section 3.8).
- Recommended style: short capitals for tiny charts (A, B, C), snake_case words for larger charts (check_login, send_mail).

### 3.5 Strings and quotes
- Node text after the colon needs no quotes.
- Group names, lane names, view names, and labels written with `label` use double quotes.
- Escapes inside quotes: `\"` quote, `\\` backslash, `\n` line break, `\t` tab (renders as 4 spaces).
- A literal colon inside an ID position is impossible. A literal colon inside node text is fine because only the first colon splits.

### 3.6 Numbers, colors, units
- Numbers: integers or decimals, no thousands separators.
- Default length unit: px. A trailing `%` means percent where noted.
- Colors: `#rgb`, `#rrggbb`, `#rrggbbaa`, CSS color names, or theme tokens (primary, accent, success, warning, danger, muted, surface, ink).
- Booleans: `true` or `false`. In header options `on` and `off` are accepted as synonyms.

### 3.7 Text formatting (markdown-lite) inside node and label text
- `**bold**`, `*italic*`, `` `mono` ``.
- `\n` forces a line break.
- `[icon: NAME]` inserts an icon. Example: `[icon: fa-ban] forbidden`.
- `[img: PATH_OR_DATA_URI]` inserts a small inline image (v1.1).
- `[emoji: NAME]` or a raw Unicode emoji.
- `$name` inserts a variable (section 12). Use `$(name)` when the next character is a letter or digit.
- To print a literal `$`, write `\$`.

### 3.8 Reserved words
These cannot be used as IDs.

```
flowchart tb lsrs
block start stop pill decide io sub db doc manual delay connector prepare cloud note junction fork join text image
group lane class apply set is in when label then link both back hide
from go to ask chain fanout fanin cycle pipeline parallel via retry up max
let repeat as template use import view show tag layer legend autonumber edge
title subtitle caption footer theme style engine devas version mode palette
true false on off free auto collapse expand same rank order pin spacing align
```

Reserved for future use: `timeline`, `swim`, `mermaid`, `export`, `plugin`, `macro`, `test`, `assert`.

## 4. Header options

Header options use a keyword followed by a value. Options with a colon (title, subtitle, caption, footer, devas) keep the colon.

| Syntax | Values | Mermaid equivalent |
|---|---|---|
| `version 2` | integer | none |
| `title: TEXT` | any text | frontmatter title |
| `subtitle: TEXT` | any text | none |
| `caption: TEXT` | text under the diagram | none |
| `footer: TEXT` | small text at the bottom edge | none |
| `mode compact` | compact or normal | displayMode |
| `theme NAME` | default, neutral, forest, dark, redux-dark, custom | theme |
| `style NAME` | classic, neo, hand-drawn | look |
| `engine NAME` | dagre, elk, manual | layout, defaultRenderer |
| `merge-edges true` | true or false | elk mergeEdges |
| `placement NAME` | simple, network-simplex, linear-segments, brandes-koepf | elk nodePlacementStrategy |
| `align NAME` | none, left-up, left-down, right-up, right-down, balanced | elk nodePlacementAlignment |
| `preset NAME` | depth-first, legacy, model-order, default | elk preset |
| `edge-routing NAME` | orthogonal, polyline, splines | elk edge routing |
| `crossing-min NAME` | layer-sweep, none | elk crossing minimization |
| `node-spacing N` | number in px | elk spacing.nodeNode |
| `layer-spacing N` | number in px | elk spacing.nodeNodeBetweenLayers |
| `border-color HEX` | color | nodeBorder |
| `gradient on` | on or off | useGradient |
| `font NAME` | family name, quotes optional | fontFamily |
| `font-size N` | px, default 14 | fontSize |
| `corner-radius N` | px, default 6 | none |
| `line-width N` | px, default 1.5 | none |
| `arrow-size N` | px, default 8 | none |
| `shadow on` | on or off | none |
| `direction-default tb` | tb or lsrs | none |

Notes:
- The ELK options (merge-edges, placement, align, preset, edge-routing, crossing-min, node-spacing, layer-spacing) apply only when `engine elk`. Under dagre or manual they are ignored silently.
- If elk is requested and cannot run, fall back to dagre and emit warning W010.
- `engine manual` means every node must have a `pin` (section 14.4). Unpinned nodes in manual mode are error E040.
- `theme custom` requires a `palette:` block (section 13.6).
- Unknown header keywords are error E004 with a suggestion of the closest known keyword.

## 5. devas options

The `devas:` prefix marks options that belong to this language only and have no Mermaid equivalent.

Form: `devas: OPTION: VALUE`
One option per line, header zone only. Unknown option is error E010.

### 5.1 Option table

| Option | Values | Default | Purpose |
|---|---|---|---|
| `share_layout` | 16/9, 4/5, 2/3, 1/1, free | free | aspect ratio of the output canvas |
| `share_anchor` | center, top, bottom, left, right, top-left, top-right, bottom-left, bottom-right | center | where content sits inside the canvas |
| `share_margin` | number in px or percent | 5% | empty border around content |
| `share_reflow` | off, wrap | off | allow the renderer to wrap long chains into rows (v1.1) |
| `share_fit` | grow, shrink | grow | grow the canvas to hold content, or shrink content to a fixed canvas |
| `padding` | number in px | 24 | padding used in free layout |
| `background` | color or transparent | theme surface | canvas fill |
| `transparent` | true or false | false | alias for background transparent |
| `export_format` | svg, png, pdf, jpg, webp, json, dot, mermaid | svg | default output type |
| `export_width` | integer px | auto | output pixel width. Height derived from ratio |
| `export_dpi` | integer | 96 | raster density |
| `seed` | integer | 1 | random seed for hand-drawn style and any tie breaks |
| `grid` | off or integer px | off | snap node positions to a grid |
| `lock` | true or false | false | mark the output as final. Renderers may refuse manual edits (reserved for editors) |
| `alt` | text | auto | alt text for the exported image |
| `watermark` | text | none | faint diagonal or corner text |
| `watermark_pos` | center, bottom-right, bottom-left, top-right, top-left | bottom-right | watermark position |
| `units` | px or pt | px | unit for all sizes |
| `max_width` | px | none | in free layout, scale down if natural width exceeds this |
| `max_height` | px | none | same, for height |
| `min_node_width` | px | 80 | smallest node width |
| `max_node_width` | px | 240 | text wraps beyond this |
| `wrap_text` | true or false | true | wrap node text at max_node_width |
| `rank_gap` | px | 56 | gap between ranks (rows in tb, columns in lsrs) |
| `node_gap` | px | 40 | gap between nodes in the same rank |
| `edge_style` | orthogonal, straight, curved, step | curved | default edge routing |
| `autonumber` | off, nodes, edges, both | off | step numbering badges |
| `strict` | true or false | false | treat all warnings as errors |

### 5.2 share_layout

Allowed values:

| Value | Width : Height | Shape | Typical use |
|---|---|---|---|
| `16/9` | 16 : 9 | wide landscape | slides, video, desktop wallpaper, web banner |
| `4/5` | 4 : 5 | portrait | Instagram and LinkedIn feed posts |
| `2/3` | 2 : 3 | tall portrait | Pinterest, posters, phone screens |
| `1/1` | 1 : 1 | square | profile posts, chat stickers, thumbnails |
| `free` | none | natural | default |

Reserved for later versions: `9/16`, `3/2`, `3/4`, `21/9`, `A4`, `A4L`, `custom W/H`.

Any other value is error E011 with the message: `share_layout must be 16/9, 4/5, 2/3, 1/1 or free`.

Meaning of the ratio: first number is width, second number is height. So `4/5` is four wide, five tall.

### 5.3 Default behavior when share_layout is not given (free layout)

If the `devas: share_layout` line is absent, or its value is `free`, the diagram is in free layout. The renderer is not constrained by any aspect ratio.

Rules for free layout:
1. Direction (tb or lsrs) is honored exactly as written.
2. The layout engine chooses spacing, edge routing and node placement as it sees fit, using the options the file sets (or its own defaults).
3. The canvas is the tight bounding box of everything drawn, plus `padding` (default 24 px) on every side.
4. The final aspect ratio is whatever comes out. It is not adjusted, padded or cropped to match anything.
5. The renderer may choose to wrap or compress long chains only if `share_reflow wrap` is set. Otherwise it keeps the natural shape.
6. If `max_width` or `max_height` is set, scale the whole canvas down uniformly until it fits. Never scale up.
7. No warning is raised about empty space or shape, because there is no target shape.

In short: no ratio line means the diagram goes on its own and renders as it desires.

### 5.4 Fit algorithm when share_layout is a ratio

Let the ratio be W over H, written R = W / H (a number).

Step 1. Run the normal layout. Get positions of all nodes, edges, edge labels, group boxes, lane headers, notes, legend, title block, caption, footer, watermark and autonumber badges.

Step 2. Compute the content box: the smallest rectangle that holds all of the above, including stroke widths, shadows and arrowheads. Call its size Wc by Hc.

Step 3. Margin M:
- If `share_margin` is a percent, M is that percent of the larger of Wc and Hc.
- If it is a number, M is that number.
- Default 5 percent. Minimum 16 px in all cases.

Step 4. Padded content size: Wp = Wc + 2M, Hp = Hc + 2M.

Step 5. Canvas size (share_fit grow, the default):
- If Wp divided by Hp is greater than R, then Wv = Wp and Hv = Wv divided by R.
- Otherwise Hv = Hp and Wv = Hv times R.

Step 6. Place the content box according to `share_anchor`. Default center: x offset = (Wv minus Wc) divided by 2, y offset = (Hv minus Hc) divided by 2.

Step 7. Paint the background across the full canvas. Output viewBox is 0 0 Wv Hv.

Step 8. If `export_width` is given, scale uniformly: pixel scale = export_width divided by Wv. Export height = round(export_width divided by R).

Rules:
- Uniform scale only. Never stretch or squash.
- Never clip. If content does not fit, the canvas grows.
- With `share_fit shrink` and a fixed `export_width`: canvas pixel size is fixed first, then the whole content is scaled down uniformly to fit inside the canvas minus margin. Never scale up.
- Title, subtitle, caption, footer and legend are part of the content box. They are included in the ratio.
- Watermark is painted over the canvas and does not affect the content box.

### 5.5 Worked examples

Content box 800 by 300 (wide flow). Margin 5 percent of 800 = 40.
Wp = 880, Hp = 380. Wp divided by Hp = 2.316.

| Ratio | R | Branch | Canvas Wv by Hv | Content offset x, y |
|---|---|---|---|---|
| 16/9 | 1.778 | 2.316 is greater than R, width rules | 880 by 495 | 40, 97.5 |
| 1/1 | 1.000 | width rules | 880 by 880 | 40, 290 |
| 4/5 | 0.800 | width rules | 880 by 1100 | 40, 400 |
| 2/3 | 0.667 | width rules | 880 by 1320 | 40, 510 |

Content box 300 by 900 (tall flow). Margin 5 percent of 900 = 45.
Wp = 390, Hp = 990. Wp divided by Hp = 0.394.

| Ratio | R | Branch | Canvas Wv by Hv | Content offset x, y |
|---|---|---|---|---|
| 16/9 | 1.778 | 0.394 is less than R, height rules | 1760 by 990 | 730, 45 |
| 1/1 | 1.000 | height rules | 990 by 990 | 345, 45 |
| 4/5 | 0.800 | height rules | 792 by 990 | 246, 45 |
| 2/3 | 0.667 | height rules | 660 by 990 | 180, 45 |

### 5.6 Fill quality and warnings

Fill ratio = (Wc times Hc) divided by (Wv times Hv). A value near 1 means the content fills the canvas.

- If fill ratio is less than 0.45 the renderer emits warning W020: `share_layout 16/9 leaves much empty space. Consider a different direction or ratio`.
- If a flowchart is `tb` with 16/9, or `lsrs` with 4/5 or 2/3, the usual result is low fill. The warning is expected, not an error.
- A suggestion table the renderer may print with W020:

| Content shape | Best ratio |
|---|---|
| wide (Wc over Hc greater than 1.5) | 16/9 |
| near square | 1/1 |
| tall (Hc over Wc greater than 1.25) | 4/5 |
| very tall (Hc over Wc greater than 1.6) | 2/3 |

### 5.7 Reflow (v1.1)

With `devas: share_reflow: wrap` and a ratio set, the renderer may improve fill instead of only padding:
1. Try up to 2 extra layouts, increasing `node_gap` or `rank_gap` on the short axis by 20 percent then 40 percent.
2. If fill ratio is still less than 0.45 and a long linear chain exists, wrap the chain into rows (snake layout). The wrap point is chosen so the content aspect ratio gets as close to R as possible.
3. Pick the attempt with the highest fill ratio. Ties go to the one with fewer edge crossings.
4. Direction semantics remain readable: a snake turn is drawn with a clear connector and never reverses meaning of an arrow.

Reflow is never applied in free layout.

### 5.8 share_layout with groups, lanes and views
- Groups and lanes are part of the content box. Their borders and titles count.
- A view (section 15.6) may override `share_layout` for its own output. The header value is the default for all views.
- If a view hides a group, the content box is recomputed for that view.

## 6. Direction

| Syntax | Meaning | Mermaid |
|---|---|---|
| `flowchart tb` | top to bottom | TD or TB |
| `flowchart lsrs` | left to right | LR |
| `flowchart` | uses `direction-default`, else tb | none |

Groups may override direction: `group "Name" direction lsrs:`. Lanes always run perpendicular to the main flow.

## 7. Nodes

Form: `KEYWORD ID: TEXT`

### 7.1 Shape keywords

| Keyword | Shape | Typical meaning | Mermaid shape |
|---|---|---|---|
| `block` | rectangle | process step | A[text] |
| `start` | stadium (pill with full round ends) | begin | A(["text"]) |
| `stop` | double-outline stadium | end | A(["text"]) |
| `pill` | rounded rectangle | soft step | A(text) |
| `decide` | diamond | decision | A{text} |
| `io` | parallelogram | input or output | A[/text/] |
| `sub` | rectangle with double side bars | subroutine, call | A[[text]] |
| `db` | cylinder | database, storage | A[(text)] |
| `doc` | rectangle with wavy bottom | document | asymmetric flag shape |
| `docs` | stacked documents | multiple documents | none |
| `manual` | trapezoid | manual operation | A[/text\] |
| `delay` | half stadium | wait | none |
| `connector` | small circle | on-page connector | A((text)) |
| `prepare` | hexagon | setup, preparation | A{{text}} |
| `cloud` | cloud | external service | none |
| `note` | folded corner box | annotation node | none |
| `junction` | tiny filled dot | merge point, no text | none |
| `fork` | thick bar | start parallel branches | none |
| `join` | thick bar | end parallel branches | none |
| `text` | no border | free label | none |
| `image` | image frame | picture node (v1.1) | none |

### 7.2 Rules
- ID: section 3.4. Unique across the whole file.
- Text: everything after the first colon and one space, up to end of line or a trailing comment.
- `junction` and `fork` and `join` may omit text: `junction J`.
- Multi-line text: use `\n`.
- Empty text is allowed for `junction`, `fork`, `join`. For other shapes it is warning W002 (empty label).
- Redeclaring an ID is error E020.
- A node used first in an edge and never declared is auto-created as `block` with text equal to the ID. Warning W001 appears in strict mode only.
- Declaration may appear after the edges that use it. A declaration overrides the auto-created block.

### 7.3 Node size
- Default: width fits text between `min_node_width` and `max_node_width`. Height fits wrapped text plus padding 10 px.
- Set explicitly with `set`: `set A: width 160, height 60`.
- Diamonds size to hold their text, so they run about 1.6 times wider than a block with the same text.

### 7.4 Node states (visual)
`set A: state done` accepts: normal, active, done, failed, skipped, disabled. Each maps to a theme color. Useful for progress diagrams.

## 8. Edges

### 8.1 Operators

| Operator | Word alias | Meaning |
|---|---|---|
| `->` | `then` | solid line, arrow at end |
| `-.->` | `dotted` | dotted line, arrow at end |
| `==>` | `thick` | thick line, arrow at end |
| `--` | `link` | solid line, no arrows |
| `-.-` | `dots` | dotted line, no arrows |
| `===` | `bold` | thick line, no arrows |
| none | `both` | arrows on both ends |
| none | `back` | arrow at the start only (A back B draws an arrow pointing at A) |
| none | `hide` | invisible edge, affects layout only |

Examples:
```
A -> B
A then B
A dotted B
A thick B
A both B
A back B
A hide B
```

### 8.2 Labels
```
A -> B when Yes
A -> B label "Yes"
A -> B when Payment failed
```
- `when` text runs to the end of the line (or to a comma that begins another fan-out target, see 8.3).
- `label` text must be quoted.
- A label attaches to the last edge in a chain.
- Multi-line label: `label "Line one\nLine two"`.

### 8.3 Chains and fan-out
```
A -> B -> C -> D
A -> B, C, D
A -> B when Yes, C when No
A -> B, C -> E
```
- Chain: each pair becomes one edge.
- Fan-out: after an operator, a comma list means one edge from the source to each target.
- Each fan-out target can carry its own `when`.
- A comma list in the middle of a chain applies to the next operator: `A -> B, C -> E` means A to B, A to C, C to E. To connect both B and C to E use fan-in (section 11).

### 8.4 Loops and back edges
```
D -> E -> B
loop back to B from E
E -> B when Retry
A -> A when Poll again
```
- No special marker is needed. The layout engine reverses back edges internally for ranking and draws them returning.
- `loop back to B from E` is an English alias for `E -> B`.
- A self-loop `A -> A` is drawn as a small arc on the side facing the flow.

### 8.5 Edge IDs
Give an edge an ID to style or reference it:
```
edge e1: A -> B when Yes
set edge e1: color red, width 3
```
- Only a single edge per `edge` line. Chains are not allowed with an ID (error E031).
- Edge IDs share the same character rules as node IDs and live in a separate namespace.

### 8.6 Ports (connection sides)
```
A.right -> B.left
A.bottom -> B.top when Yes
```
- Ports: top, bottom, left, right, and for diamonds also top-left, top-right, bottom-left, bottom-right.
- A port is a hint. The router follows it when it can.
- Ports work only with a dot. IDs can't contain dots, so there is no clash.

### 8.7 Edge heads and tails
`set edge e1: head arrow, tail none`
- Values: arrow, open, dot, cross, diamond, circle, bar, none.
- `->` defaults to head arrow. `--` defaults to none.

### 8.8 Edge length and weight
```
A -> B len 2
A -> B weight 5
```
- `len N`: ask the layout to span at least N ranks (default 1).
- `weight N`: higher weight keeps the edge short and straight (default 1).
- These follow the label: `A -> B when Yes len 2` is valid. Keywords `len` and `weight` end the label text.

### 8.9 Edge routing
`set edge e1: route orthogonal`
- Values: straight, curved, orthogonal, step, spline.
- Default comes from `devas: edge_style`.

### 8.10 Edge label placement
`set edge e1: label-pos 0.3` where 0 is the start, 1 is the end, 0.5 is the middle (default). Labels get a background patch in the surface color so lines never cross text.

### 8.11 Parallel edges
Two edges between the same pair are drawn side by side with a small offset. Identical labels on identical pairs trigger warning W005.

### 8.12 Edges to groups
```
A -> group "Build Stage"
group "Build Stage" -> B
```
The edge attaches to the group's border. Needed for diagrams where internals are hidden by `collapse`.

## 9. Groups

```
group "Build Stage":
    block C: Compile
    block D: Test
    C -> D
```

Rules:
- Name in quotes. Unique across the file.
- Ends when indentation returns to the parent level.
- Nested groups are allowed to any depth.
- A node belongs to exactly one group (the one it was declared in). Moving it needs a new declaration.
- Edges can cross borders in any direction.
- Group options on the header line:

```
group "Build Stage" direction lsrs:
group "Build Stage" class soft:
group "Build Stage" collapse:
```
- `direction lsrs` or `tb` overrides flow inside the group.
- `class NAME` applies a class (section 13).
- `collapse` draws the group as one node showing its name. Internal edges vanish. Edges from outside attach to the group border.
- To expand it again: `expand group "Build Stage"` (used in views).

## 10. Lanes (swimlanes)

```
lane "Customer":
    start A: Place order
    block D: Receive item
lane "Shop":
    block B: Confirm
    block C: Ship

A -> B -> C -> D
```

Rules:
- Lanes run perpendicular to the flow. In `tb`, lanes are columns. In `lsrs`, lanes are rows.
- Lane order follows declaration order.
- Inside a lane, nodes keep the flow order of their ranks.
- A node can be assigned to a lane after the fact: `block X: Audit` then `X in lane "Shop"`.
- Lanes and groups can mix: a group can sit inside a lane, a lane cannot sit inside a group.
- Lane header text sits on the outer edge of the lane. Style with `set lane "Shop": fill #eef`.

## 11. Functions (statement macros)

Functions expand into core statements during the resolve step. They exist to cut typing. Each shows its expansion.

### 11.1 chain
```
chain A, B, C, D
```
Expands to `A -> B -> C -> D`.

### 11.2 fanout
```
fanout A to B, C, D
```
Expands to `A -> B, C, D`.

### 11.3 fanin
```
fanin B, C, D to E
```
Expands to `B -> E`, `C -> E`, `D -> E`.

### 11.4 cycle
```
cycle A, B, C
```
Expands to `A -> B -> C -> A`.

### 11.5 ask (decision with answers)
```
ask C: Password valid
    yes D
    no E
    "not sure" F
```
Expands to `decide C: Password valid`, `C -> D when yes`, `C -> E when no`, `C -> F when not sure`.
- Each answer line is: answer text (quoted if it has spaces), then a target ID.
- Targets that do not exist are auto-created as blocks.
- Fewer than two answers is warning W030.

### 11.6 from (branch block)
```
from B:
    go to C when Yes
    go to D when No
```
Expands to `B -> C when Yes` and `B -> D when No`. Works on any node, not only decide nodes.

### 11.7 parallel
```
parallel F to J via A, B, C
```
Expands to:
- `fork F` and `join J` if they are not declared.
- `F -> A`, `F -> B`, `F -> C`.
- `A -> J`, `B -> J`, `C -> J`.

### 11.8 pipeline
```
pipeline Build:
    Compile
    Run tests
    Package
    Publish
```
Expands to blocks with IDs `build_1`, `build_2`, `build_3`, `build_4` joined by a chain. The pipeline name becomes the ID prefix in lowercase. Add `as group` to also wrap them in a group named after the pipeline:
```
pipeline Build as group:
```

### 11.9 retry
```
retry E to B max 3
```
Expands to a dotted edge from E to B labeled `retry up to 3`. With text: `retry E to B max 3 when Network error` uses the given text.

### 11.10 on failure and on success
```
E3 fails to Handler
E3 passes to Next
```
Expands to `E3 -.-> Handler when failed` (red, dashed) and `E3 -> Next when ok` (green).

### 11.11 merge
```
merge A, B into M
```
Expands to `junction M` (if not declared) and `A -> M`, `B -> M`.

### 11.12 split
```
split M into A, B
```
Expands to `junction M` (if not declared) and `M -> A`, `M -> B`.

### 11.13 skip
```
skip A over B to C
```
Expands to a dotted edge `A -.-> C when skip` and marks B as `state skipped`.

### 11.14 Function rules
- A function name is a reserved word. The ID rules in section 3.4 apply to arguments.
- Functions cannot nest on one line.
- Expanded statements keep the source line number of the function for error messages.

## 12. Variables, templates, repeat, import

### 12.1 let
```
let env = production
let step_color = #3366cc
block A: Deploy to $env
```
- `let NAME = VALUE`. VALUE is the rest of the line.
- Use `$name` or `$(name)`.
- Redefining a variable is allowed. The latest value wins from that line on.
- Undefined variable is error E050.

### 12.2 repeat
```
repeat 3 as i:
    block check_$i: Check number $i
```
Generates `check_1`, `check_2`, `check_3`. The counter starts at 1. Use `from 0` to change: `repeat 3 from 0 as i:`.

Also over a list:
```
repeat each name in Alpha, Beta, Gamma:
    block n_$name: $name server
```
Maximum 1000 iterations (error E051 beyond that).

### 12.3 template and use
```
template service(NAME, PORT):
    block NAME_app: NAME app
    db NAME_db: NAME database
    NAME_app -> NAME_db when port PORT

use service(auth, 8080)
use service(billing, 9090)
```
- Parameters replace identifier text and text values.
- A template body can hold any body statements.
- IDs generated inside should include the parameter to stay unique.
- Templates can call other templates. Recursion is error E052.

### 12.4 import
```
import "common_styles.flow"
import "shapes/db_layer.flow"
```
- Imports bring in definitions (let, class, template, palette) and body statements.
- Path is relative to the importing file.
- A file imported twice is loaded once.
- Circular import is error E053.

### 12.5 Conditional blocks (v1.1)
```
if env is production:
    block X: Sign release
```
- Conditions: `NAME is VALUE`, `NAME is not VALUE`.
- No arithmetic. No loops inside conditions.

## 13. Styling

### 13.1 set
```
set A: fill #ffe0e0, border #cc0000, bold
set edge e1: color red, width 3
set group "Build Stage": fill #f4f8ff, dash
set lane "Shop": fill #eef
set all block: font-size 13
```
- `set TARGET: PROP VALUE, PROP VALUE, FLAG`.
- Flags (no value): bold, italic, underline, shadow, dash, dot, hidden.
- `set all KEYWORD:` styles every node of that shape.

### 13.2 Node style properties

| Property | Values |
|---|---|
| `fill` | color or gradient (two colors: `fill #fff to #ccc`) |
| `border` | color |
| `border-width` | px |
| `text-color` | color |
| `font` | family |
| `font-size` | px |
| `width`, `height` | px |
| `radius` | px |
| `opacity` | 0 to 1 |
| `shadow` | flag |
| `dash` | flag |
| `icon` | icon name placed before text |
| `state` | normal, active, done, failed, skipped, disabled |
| `align` | left, center, right (text alignment) |

### 13.3 Edge style properties

| Property | Values |
|---|---|
| `color` | color |
| `width` | px |
| `dash` | flag |
| `dot` | flag |
| `head`, `tail` | arrow, open, dot, cross, diamond, circle, bar, none |
| `route` | straight, curved, orthogonal, step, spline |
| `label-pos` | 0 to 1 |
| `label-color` | color |
| `label-size` | px |
| `animate` | true or false (animated dashes in SVG, v1.1) |

### 13.4 Classes
```
class warn:
    fill #fff3cd
    border #d39e00
    text-color #664d03

A is warn
apply warn to B, C, D
```
- A class is a named set of properties. Indented lines are `PROP VALUE` (or a flag).
- `NODE is CLASS` and `apply CLASS to NODE, NODE` do the same thing.
- Multiple classes: `A is warn, big`. Later classes override earlier ones.
- `set` beats class. A class beats theme defaults.
- Classes can apply to edges, groups, lanes by writing `apply warn to edge e1` or `apply warn to group "Build Stage"`.

### 13.5 Style precedence (lowest to highest)
1. Theme defaults.
2. Header options (font, font-size, and so on).
3. Class (in the order applied).
4. `set` statements (in file order).
5. State (`state failed` adds its color if no explicit fill is set).

### 13.6 Palette (for theme custom)
```
palette:
    primary #1f6feb
    accent #f78166
    success #2da44e
    warning #bf8700
    danger #cf222e
    muted #6e7781
    surface #ffffff
    ink #1f2328
```
Required keys: primary, surface, ink. Missing optional keys fall back to the neutral theme.

### 13.7 Built-in themes
| Theme | Surface | Notes |
|---|---|---|
| `default` | white | blue and violet outlines, closest to Mermaid default |
| `neutral` | white | gray scale only, good for print |
| `forest` | light green tint | green accents |
| `dark` | near black | light text, muted lines |
| `redux-dark` | dark navy | high contrast accent |
| `custom` | from palette | needs palette block |

### 13.8 Styles (look)
- `classic`: clean vector lines, no randomness.
- `neo`: soft shadows, larger radius, subtle gradient.
- `hand-drawn`: wobbly lines. Uses `devas: seed` so the same file always produces the same drawing. Options: `roughness N` (0 to 3, default 1) as a header line.

## 14. Layout controls

### 14.1 same rank
Force nodes onto the same row (tb) or column (lsrs):
```
same rank A, B, C
```

### 14.2 order
Keep a left-to-right (or top-to-bottom) order inside a rank:
```
order A before B
order A, B, C
```

### 14.3 spacing
```
spacing rank 80
spacing node 50
spacing group 30
```
Local override of the header gaps. `spacing rank 80` applies from that line on to the ranks that follow in the layout sense (the engine treats it as a global minimum when the engine cannot do local gaps).

### 14.4 pin
```
pin A at 100, 40
```
Fix a node position in diagram units. Needed for `engine manual`. In an auto engine a pin is a hard constraint; the engine lays out the rest around it.

### 14.5 align
```
align A, B, C center
```
Aligns the listed nodes on one axis. Values: left, center, right, top, middle, bottom.

### 14.6 wrap after
```
wrap after 5
```
Break a long linear chain into rows of N nodes. Only used when `share_reflow wrap` is on or when the file asks explicitly with this line.

### 14.7 keep together and keep apart
```
keep together A, B
keep apart C, D
```
Hints for engines that support it. Others ignore.

### 14.8 Engine hints
- `engine dagre`: fast, classic layered layout.
- `engine elk`: better for large graphs and orthogonal routing.
- `engine manual`: positions come only from `pin`.

## 15. Annotations and metadata

### 15.1 Notes
```
note on A: Runs once per day
note over A, B: Handshake happens here
note left of C: Fallback
```
Attached notes draw a small dashed connector to the node.

### 15.2 Legend
```
legend:
    fill #ffe0e0 = Failure path
    fill #e0ffe0 = Success path
```
Entries are `STYLE = TEXT`. The legend sits at a corner (default bottom-left). Move it with `legend at top-right:`.

### 15.3 Autonumber
`devas: autonumber: nodes` numbers nodes in breadth-first order from the first start node. `edges` numbers edges. `both` does both. Skip a node: `set A: nonumber`.

### 15.4 Links, tooltips, clicks
```
link A: "https://example.com"
tooltip A: Opens the console
click A: open_console
```
- `link`: hyperlink on the node (SVG anchor).
- `tooltip`: hover text.
- `click`: names a callback for host pages. Name is a plain word. No code is executed by the renderer itself.

### 15.5 Tags and layers
```
tag A: main
tag B, C: detail, error
layer "Errors": E, F, G
```
- A node can hold many tags.
- A layer is a named set of nodes drawn on top and toggled as a unit.

### 15.6 Views
```
view "Overview":
    show tag main
    hide tag detail
    collapse group "Build Stage"
    share_layout 16/9

view "Errors only":
    show layer "Errors"
    share_layout 1/1
```
- Each view produces its own output file named after the view.
- Without any view, the whole diagram is the single default view.
- `show` and `hide` take `tag NAME`, `layer "Name"`, `node ID`, `group "Name"`.
- Edges are shown only when both endpoints are shown.
- A view can override `share_layout`, `theme`, `direction`.

### 15.7 Step status
Combine `state` with `autonumber` to produce progress diagrams. Example: `set A: state done`, `set B: state active`.

## 16. Accessibility

- `devas: alt: TEXT` sets the image alt text. If missing, the renderer builds one: `Flowchart with N steps and M decisions starting at START_TEXT`.
- The SVG output carries a title element and a description element. The description lists every node and edge in reading order (breadth-first from start).
- Never rely on color alone. Failure edges get a dashed style plus a label even when colored red.
- Minimum contrast ratio 4.5 to 1 between text and fill. The renderer should warn (W040) when a custom palette fails this.
- A color-blind safe palette is available: `theme custom` with the palette `primary #0072B2, accent #E69F00, success #009E73, danger #D55E00, muted #666666, surface #ffffff, ink #111111`.

## 17. Errors, warnings and lint

Every message carries: code, line number, column, short text, and a fix hint. With `devas: strict: true` all warnings become errors.

### 17.1 Errors

| Code | Meaning |
|---|---|
| E001 | no flowchart line |
| E002 | tab used for indentation |
| E003 | indentation not a multiple of 4 |
| E004 | unknown header keyword |
| E010 | unknown devas option |
| E011 | bad share_layout value |
| E012 | bad value for a devas option |
| E020 | duplicate node ID |
| E021 | ID equals a reserved word |
| E022 | invalid ID characters |
| E030 | unknown operator |
| E031 | edge ID used on a chain |
| E032 | edge refers to an unknown group or lane |
| E033 | unknown port name |
| E040 | engine manual with an unpinned node |
| E050 | undefined variable |
| E051 | repeat limit exceeded |
| E052 | template recursion |
| E053 | circular import |
| E060 | unknown class |
| E061 | unknown property |
| E062 | bad property value |
| E070 | view refers to an unknown tag, layer or group |

### 17.2 Warnings

| Code | Meaning |
|---|---|
| W001 | node auto-created from an edge (strict only) |
| W002 | empty label |
| W003 | very long label (over 120 characters) |
| W005 | duplicate parallel edges with same label |
| W010 | elk unavailable, fell back to dagre |
| W020 | low fill ratio for the chosen share_layout |
| W021 | share_layout with an unsuited direction |
| W030 | decision with fewer than two outgoing edges |
| W031 | decision branch without a label |
| W032 | unreachable node (no path from any start) |
| W033 | no start node |
| W034 | more than one start node |
| W035 | node with no edges |
| W036 | cycle with no exit |
| W037 | dead end that is not a stop node |
| W040 | text contrast below 4.5 to 1 |
| W050 | ELK option ignored under dagre |
| W060 | class defined but never used |

### 17.3 Lint order
Run lint after resolve and before layout. Report errors first, then warnings sorted by line.

## 18. Core grammar (loose EBNF)

No angle brackets. Terminals in quotes. Rules use `=`. `|` means or. `[ ]` optional. `{ }` repeat zero or more. `( )` group.

```
file         = { header } { definition } flowline { body }
flowline     = "flowchart" [ direction ] NL
direction    = "tb" | "lsrs"

header       = titleh | subtitleh | captionh | footerh | simpleh | devash
titleh       = "title:" TEXT NL
devash       = "devas:" NAME ":" VALUE NL
simpleh      = KEYWORD VALUE NL

definition   = letdef | classdef | templatedef | importdef | palettedef
letdef       = "let" NAME "=" TEXT NL
classdef     = "class" NAME ":" NL INDENT { PROP [ VALUE ] NL } DEDENT
templatedef  = "template" NAME "(" PARAMS ")" ":" NL INDENT { body } DEDENT
importdef    = "import" QSTRING NL
palettedef   = "palette:" NL INDENT { TOKEN COLOR NL } DEDENT

body         = node | edgeline | group | lane | function | setline
             | classline | note | legend | taggy | view | repeat | use | comment

node         = SHAPE ID [ ":" TEXT ] NL
SHAPE        = "block" | "start" | "stop" | "pill" | "decide" | "io" | "sub"
             | "db" | "doc" | "docs" | "manual" | "delay" | "connector"
             | "prepare" | "cloud" | "note" | "junction" | "fork" | "join"
             | "text" | "image"

edgeline     = [ "edge" ID ":" ] endpoint { OP endpoint { "," endpoint } } [ tail ] NL
endpoint     = ID [ "." PORT ] | "group" QSTRING
OP           = "->" | "-.->" | "==>" | "--" | "-.-" | "===" 
             | "then" | "dotted" | "thick" | "link" | "dots" | "bold"
             | "both" | "back" | "hide"
tail         = ( "when" TEXT | "label" QSTRING ) [ "len" N ] [ "weight" N ]

group        = "group" QSTRING { "direction" ( "tb" | "lsrs" ) | "class" NAME | "collapse" } ":" NL
               INDENT { body } DEDENT
lane         = "lane" QSTRING ":" NL INDENT { body } DEDENT

function     = chain | fanout | fanin | cycle | ask | from | parallel
             | pipeline | retry | failpass | merge | split | skip
chain        = "chain" IDLIST NL
fanout       = "fanout" ID "to" IDLIST NL
fanin        = "fanin" IDLIST "to" ID NL
cycle        = "cycle" IDLIST NL
ask          = "ask" ID ":" TEXT NL INDENT { ANSWER ID NL } DEDENT
from         = "from" ID ":" NL INDENT { "go to" ID [ "when" TEXT ] NL } DEDENT
parallel     = "parallel" ID "to" ID "via" IDLIST NL
pipeline     = "pipeline" NAME [ "as group" ] ":" NL INDENT { TEXT NL } DEDENT
retry        = "retry" ID "to" ID "max" N [ "when" TEXT ] NL
failpass     = ID ( "fails" | "passes" ) "to" ID NL
merge        = "merge" IDLIST "into" ID NL
split        = "split" ID "into" IDLIST NL
skip         = "skip" ID "over" ID "to" ID NL

setline      = "set" [ "edge" | "group" | "lane" | "all" ] TARGET ":" PROPLIST NL
classline    = ID "is" NAMELIST NL | "apply" NAME "to" TARGETLIST NL
note         = "note" ( "on" | "over" | "left of" | "right of" ) IDLIST ":" TEXT NL
legend       = "legend" [ "at" POSITION ] ":" NL INDENT { PROPLIST "=" TEXT NL } DEDENT
taggy        = "tag" IDLIST ":" NAMELIST NL | "layer" QSTRING ":" IDLIST NL
view         = "view" QSTRING ":" NL INDENT { viewrule NL } DEDENT
repeat       = "repeat" ( N [ "from" N ] | "each" NAME "in" LIST ) "as" NAME ":" NL
               INDENT { body } DEDENT
use          = "use" NAME "(" ARGS ")" NL
```

## 19. Tokens

| Token | Pattern |
|---|---|
| ID | letter followed by letters, digits, underscore |
| NAME | same as ID |
| N | integer or decimal |
| COLOR | hex, CSS name or theme token |
| QSTRING | double quoted text with escapes |
| TEXT | rest of line up to a trailing comment |
| NL | end of line |
| INDENT, DEDENT | virtual tokens made from 4 space indentation changes |
| OP | one of the edge operators in 8.1 |

Tokenizer approach: read line by line. Compute indentation. Emit INDENT or DEDENT tokens when it changes. Read the first word of the stripped line. Use it to choose a line parser. The line parsers are small and independent (header line, node line, edge line, block opener).

Edge line detection: a line is an edge line if its first word is an ID or `edge` or `group` and the line contains an operator surrounded by spaces. Check the keyword table first, so a line starting with a shape keyword is always a node line.

## 20. AST and JSON model

The parser returns one document object. Everything later (resolve, layout, paint) uses it.

```json
{
  "version": 2,
  "header": {
    "title": "Login Flow",
    "theme": "neutral",
    "style": "classic",
    "engine": "dagre",
    "devas": { "share_layout": "4/5", "padding": 24, "seed": 1 }
  },
  "direction": "tb",
  "nodes": [
    { "id": "A", "shape": "start", "text": "Start", "group": null, "lane": null,
      "classes": [], "style": {}, "tags": [], "line": 7 },
    { "id": "C", "shape": "decide", "text": "Password valid", "group": null,
      "classes": [], "style": {}, "tags": [], "line": 9 }
  ],
  "edges": [
    { "id": "e0", "from": "A", "from_port": null, "to": "B", "to_port": null,
      "op": "->", "label": null, "style": {}, "len": 1, "weight": 1, "line": 13 },
    { "id": "e1", "from": "C", "to": "D", "op": "->", "label": "Yes", "line": 14 }
  ],
  "groups": [
    { "name": "Build Stage", "parent": null, "direction": null, "collapsed": false, "members": ["C", "D"] }
  ],
  "lanes": [],
  "classes": {},
  "variables": {},
  "views": [],
  "notes": [],
  "legend": null,
  "diagnostics": []
}
```

Rules:
- Auto-generated edge IDs: e0, e1, e2 in order of appearance. User IDs must not start with `e` followed only by digits (error E022) to keep this space free.
- Every expanded function produces plain nodes and edges. After resolve, no function remains in the AST.
- `line` is kept on every item for error messages and for editor click-to-source.

## 21. Renderer pipeline

Stages, in order. Each stage takes the output of the previous one.

1. Read: load file text, apply imports.
2. Tokenize and parse into the AST.
3. Resolve: apply let and interpolation, expand repeat, template, use, functions, classes, apply.
4. Lint: errors stop here. Warnings are collected.
5. View select: pick the nodes and edges for the current view.
6. Measure: compute text size per node (font metrics), pick node width and height.
7. Layout: assign positions with the chosen engine.
8. Route: compute edge paths, ports, label positions.
9. Content box: bounding box of everything.
10. Fit: free layout (tight box plus padding) or share_layout (section 5.4).
11. Paint: produce SVG (and other formats from it).
12. Export: write files.

### 21.1 Text measuring
- Browser: draw text on a canvas and use measureText. Or use an off-screen SVG text element and read its bounding box.
- Python: use Pillow ImageFont with the same font file you embed in the SVG. If the font is unknown, use an average character width of 0.55 times the font size.
- Wrap at `max_node_width` minus 2 times horizontal padding (default horizontal padding 14 px).
- Always measure with the same font the output will use, or the text will overflow shapes.

### 21.2 Layout (layered, for dagre style)
Classic layered drawing. Four steps.
1. Cycle removal: reverse a minimal set of edges so the graph has no cycles. Remember which were reversed.
2. Rank assignment: give each node a rank (row in tb, column in lsrs). Use longest path from sources, then tighten with network simplex if available. `len N` forces a minimum span.
3. Order within ranks: reduce edge crossings by sweeping up and down, using the barycenter (average neighbor position) of each node. Repeat 8 to 24 times, keep the best.
4. Coordinates: place nodes so that edges are as straight as possible. Brandes-Koepf is the common method. Keep `node_gap` and `rank_gap` as minimums.

Long edges (spanning more than one rank) are broken by invisible dummy nodes, one per skipped rank, so they route cleanly and the label sits on a middle dummy.

Groups: treat a group as a compound node. Lay out the inside first, then reserve its box in the parent layout. Lanes: assign each node a lane index, then keep lane bands apart on the cross axis.

### 21.3 Edge routing
- `straight`: a line between port points.
- `curved`: cubic curve through the dummy node points of long edges.
- `orthogonal` and `step`: horizontal and vertical segments with rounded corners (radius 6).
- Back edges leave from the side and return to the target from the side, so they never run through the middle of nodes.
- Self-loop: small loop on the right (tb) or bottom (lsrs).
- Arrowheads are drawn after the path is shortened by the arrow size so the tip touches the border.
- Label position: at `label-pos` of the path length, with a patch behind the text.

### 21.4 Free layout fit (default)
```
content box = bounding box of everything
canvas = content box grown by padding on all sides
no ratio rule
```
If max_width or max_height is set and the canvas exceeds it, scale uniformly down.

### 21.5 Determinism
- Same file and same options must give identical output. Use the `seed` for anything random (hand-drawn wobble, tie breaks). Never use time or system randomness.
- Sort nodes by declaration order as the final tie breaker everywhere.

### 21.6 Performance targets
- 100 nodes: under 200 ms layout.
- 1000 nodes: under 5 s, may switch to the elk engine.
- Warn (W070) above 2000 nodes.

### 21.7 SVG output notes
- One root svg with a viewBox of the canvas.
- Group order: background, lane and group boxes, edges, nodes, labels, notes, legend, title block, watermark.
- Give every node and edge the id attribute from the source ID so hosts can style or find them: `flow-node-A`, `flow-edge-e1`.
- Embed the font as a data URI or fall back to a generic stack: the stated font name, then sans-serif.
- Title and description elements first inside svg for screen readers.

### 21.8 Other outputs
- png: render the SVG at the export pixel size.
- pdf: vector, page size equal to canvas.
- jpg and webp: raster, white background unless transparent is allowed.
- json: the resolved AST plus layout positions. Useful for editors and tests.
- dot: Graphviz text (section 23).
- mermaid: Mermaid text (section 23).

## 22. CLI and API sketch

### 22.1 Command line
```
flow render login.flow --out login.svg
flow render login.flow --out login.png --share 4/5 --width 1080
flow render login.flow --view "Overview" --out overview.svg
flow check login.flow
flow fmt login.flow
flow convert login.flow --to mermaid
flow convert diagram.mmd --to flow
flow ast login.flow
```

Flags:
- `--share RATIO` overrides `devas: share_layout`. Value `free` forces free layout.
- `--theme NAME`, `--style NAME`, `--engine NAME` override headers.
- `--width N` sets export_width. `--dpi N` sets export_dpi.
- `--strict` turns warnings into errors.
- `--watch` re-renders on file change.
- `--out -` writes to standard output.

Exit codes: 0 ok, 1 errors in file, 2 warnings in strict mode, 3 file or system problem.

### 22.2 Python API
```python
from flowlang import parse, render, check

source = open("login.flow").read()
doc = parse(source)
problems = check(doc)
svg = render(doc, share_layout="4/5", export_width=1080, format="svg")
open("login.svg", "w").write(svg)
```

### 22.3 JavaScript API
```javascript
import { parse, render, check } from "flowlang";

const doc = parse(sourceText);
const problems = check(doc);
const svg = render(doc, { shareLayout: "4/5", exportWidth: 1080, format: "svg" });
```

### 22.4 Web embed
- Put the source in a pre element with class `flow` (a block of text) and call `flowlang.renderAll()` on page load.
- In Markdown, use a fenced block with the language `flow`.
- Renderer options come from the file headers, so the embed needs no extra setup.

### 22.5 Formatter (flow fmt)
- 4 space indentation.
- One blank line between declarations and edges.
- Declarations first, then edges, then styling.
- Align nothing. Keep diffs small.
- Normalize `then` to `->` only if the file asks with `--symbols`.

## 23. Conversion

### 23.1 Flow to Mermaid
| Flow | Mermaid |
|---|---|
| `flowchart tb` | `flowchart TB` |
| `flowchart lsrs` | `flowchart LR` |
| `block A: Text` | `A["Text"]` |
| `start A: Text` | `A(["Text"])` |
| `stop A: Text` | `A(["Text"])` with a double border class |
| `pill A: Text` | `A("Text")` |
| `decide A: Text` | `A{"Text"}` |
| `io A: Text` | `A[/"Text"/]` |
| `sub A: Text` | `A[["Text"]]` |
| `db A: Text` | `A[("Text")]` |
| `connector A: Text` | `A(("Text"))` |
| `prepare A: Text` | `A{{"Text"}}` |
| `A -> B` | `A --> B` |
| `A -> B when Yes` | `A -->|Yes| B` |
| `A -- B` | `A --- B` |
| `A dotted B` | `A -.-> B` |
| `A thick B` | `A ==> B` |
| `A hide B` | `A ~~~ B` |
| `A both B` | two arrows, one in each direction (Mermaid double-headed arrow) |
| `group "X":` | `subgraph X` ... `end` |
| `# comment` | `%% comment` |
| `engine elk` | init directive with defaultRenderer elk |
| `theme NAME` | frontmatter config theme |
| `devas:` lines | dropped (no Mermaid equivalent) |

Conversion rules:
- Node text that contains Mermaid trouble characters is quoted.
- An ID equal to `end` is renamed `end_1`.
- Functions are expanded first, so the output uses plain nodes and edges only.
- Lanes become subgraphs.
- Lost features are reported as a short list of notes at the end of the conversion.

### 23.2 Mermaid to Flow
Reverse the table. Unknown shapes become `block`. Styling lines (style, classDef, linkStyle) become `set` and `class` statements where possible. Click and callback lines become `link` and `click`.

### 23.3 Flow to Graphviz DOT
- tb becomes rankdir TB. lsrs becomes rankdir LR.
- block, start, decide and others become shape box, ellipse, diamond and so on.
- Groups become cluster subgraphs.
- Labels become edge label attributes.
- Style properties map to color, fillcolor, style filled, penwidth.

## 24. Writing guide

How to write flow files that read well and render cleanly.

### 24.1 Order of the file
1. Header options.
2. Definitions: let, classes, templates, palette.
3. `flowchart` line.
4. Declarations: all nodes, grouped by area.
5. Edges: main path first, then branches, then loops.
6. Styling: classes and set lines.
7. Annotations: notes, legend, views.

### 24.2 Naming
- Tiny charts: single capitals (A to Z).
- Real charts: snake_case words that name the step (check_stock, send_mail).
- A decision ID starts with `is_` or `has_` or `can_` when it is a yes or no question.
- Never reuse an ID for a different meaning later in the file.

### 24.3 Text
- Verbs for steps: Validate order, Send mail.
- Questions for decisions: Stock available.
- Keep text under 6 words where possible. Long explanations belong in notes.
- Use `\n` for deliberate breaks, not for wrapping. The renderer wraps by itself.
- Sentence case. No trailing full stops.

### 24.4 Edges
- Every decision edge gets a label.
- Use Yes and No, or the real answer words.
- Write the happy path as a long chain on one line. Write branches on their own lines.
- Put loops last so the main flow reads first.

### 24.5 Layout habits
- Choose `tb` for processes with many decisions. Choose `lsrs` for pipelines and timelines.
- Pick the share ratio that matches the shape: wide flows with 16/9, tall flows with 4/5 or 2/3, balanced with 1/1.
- Leave out `devas: share_layout` while drafting. Add it when the diagram is ready to share.
- Use groups for areas with a name, lanes for areas with an owner.

### 24.6 Style habits
- Use classes for meaning (warn, ok, external) and `set` only for one-offs.
- At most 4 colors in one diagram.
- Do not use color as the only signal. Pair it with a label or dash.

### 24.7 Common mistakes
| Mistake | Fix |
|---|---|
| ID with a hyphen | use underscore |
| tab in indentation | 4 spaces |
| label on a chain meant for the middle edge | split the chain |
| edge ID on a chain | one edge per `edge` line |
| node declared twice | declare once, style with `set` |
| `end` used as an ID | any other word works, `end` is allowed only as text |
| share_layout written as 16:9 | use a slash: 16/9 |
| decision with one exit | add the missing branch |

## 25. Examples

### 25.1 Minimal
```
flowchart tb
start A: Begin
block B: Work
stop C: Finish
A -> B -> C
```

### 25.2 Decision and loop
```
flowchart tb
start A: Start
block B: Enter code
decide C: Code valid
block D: Unlock
block E: Show error
A -> B -> C
C -> D when Yes
C -> E when No
E -> B
```

### 25.3 Using ask and retry
```
flowchart tb
start A: Start
block B: Call payment API
ask C: Payment accepted
    yes D
    no E
block D: Send receipt
block E: Log failure
A -> B -> C
retry E to B max 3
```

### 25.4 Parallel work
```
flowchart lsrs
start S: Order placed
parallel F to J via pack, label, invoice
block pack: Pack items
block label: Print label
block invoice: Create invoice
block done: Ship
S -> F
J -> done
```

### 25.5 Groups and cross edges
```
flowchart lsrs
group "Build":
    block compile: Compile
    block test: Run tests
    compile -> test
group "Release":
    block tag: Tag version
    block publish: Publish
    tag -> publish
test -> tag when Green
```

### 25.6 Swimlanes
```
flowchart tb
lane "Customer":
    start A: Place order
    block D: Receive item
lane "Shop":
    block B: Confirm order
    block C: Ship item
chain A, B, C, D
```

### 25.7 Template and repeat
```
template service(NAME):
    block NAME_app: NAME service
    db NAME_db: NAME data
    NAME_app -> NAME_db

flowchart lsrs
block gateway: Gateway
use service(auth)
use service(billing)
gateway -> auth_app, billing_app
```

### 25.8 Variables
```
let env = Staging
flowchart tb
start A: Deploy to $env
block B: Run smoke tests
A -> B
```

### 25.9 Share layout in all four shapes
```
devas: share_layout: 16/9
```
```
devas: share_layout: 4/5
```
```
devas: share_layout: 2/3
```
```
devas: share_layout: 1/1
```
Each line goes in the header of the same file. Only one is active at a time. Remove the line for free layout.

### 25.10 Views
```
flowchart tb
tag A, B: main
tag E: error
start A: Start
block B: Work
block E: Handle error
stop F: Done
A -> B -> F
B -.-> E when fails

view "Happy path":
    hide tag error
    share_layout 16/9

view "Everything":
    share_layout 1/1
```

### 25.11 Styling
```
class warn:
    fill #fff3cd
    border #d39e00

flowchart tb
block A: Check disk
block B: Disk almost full
A -> B
B is warn
set edge e0: color #d39e00, width 3
```

### 25.12 Full feature file
```
version 2
title: Release Pipeline
subtitle: Weekly cycle
theme neutral
style classic
engine elk
placement brandes-koepf
devas: share_layout: 16/9
devas: share_anchor: center
devas: share_margin: 6%
devas: export_width: 1920
devas: seed: 7
devas: autonumber: nodes
devas: alt: Release pipeline from commit to production

class gate:
    fill #e8f0fe
    border #1f6feb

flowchart lsrs

start A: Commit
pipeline Build as group:
    Compile
    Unit tests
    Package
decide G: Quality gate
block R: Release candidate
block P: Production
stop Z: Done

A -> build_1
build_3 -> G
G -> R when Pass
G -> build_1 when Fail
R -> P -> Z
G is gate

legend:
    fill #e8f0fe = Gate
```

## 26. Test checklist for the renderer

Parser tests:
- each shape keyword parses with and without text
- node text with colons, hash signs, dollar signs
- chains, fan-out, labels on the last edge only
- edge with ports, edge with ID, edge to a group
- nested groups, lane assignment
- every function expands to the listed edges
- `let` interpolation, repeat, template use, import cycle
- tab indentation and bad indent errors
- duplicate ID, reserved ID, hyphen in ID

Layout tests:
- linear chain stays in one line
- diamond with two exits spreads evenly
- back edge does not cross nodes
- group box holds all members with padding
- lane order matches declaration order
- same rank puts nodes on one row

Share layout tests:
- the four worked examples in 5.5 give the listed canvases
- content centered for every anchor value
- never clipped, never stretched
- free layout has no ratio adjustment and padding equal to `padding`
- absent line equals `free`
- bad value gives E011
- export_width gives the right pixel height (1080 wide with 4/5 gives 1350 tall)

Output tests:
- same input twice gives byte-identical SVG
- every node has an id attribute
- title and description present
- png size matches export_width

## 27. Roadmap ideas

- v2.1: share_reflow wrap, conditional blocks, animated edges, `image` nodes.
- v2.2: more share ratios (9/16, 3/2, 3/4, 21/9) and paper sizes (A4, A4L).
- v2.3: live editor with click on a node to jump to its line, and drag to write `pin` lines.
- v3: other diagram families that reuse the same lexer: sequence, state, ER, timeline.
- Plugins: custom shapes, custom themes packaged as a flow file with a palette and classes.
- Data driven diagrams: `table from "file.csv"` that generates nodes from rows.
- Diff view: render two versions of a file and mark added, removed, changed nodes.
- Auto layout explain: a mode that prints why a node was placed where it is.

## 28. Changelog

v2 compared with v1:
- Added free layout as the default when `devas: share_layout` is missing, plus the explicit value `free`.
- Added share options: anchor, margin, fit, reflow.
- IDs no longer allow hyphens.
- Added shapes: stop, io, sub, db, doc, docs, manual, delay, connector, prepare, cloud, note, junction, fork, join, text, image.
- Added operators: dotted, thick, dots, bold, both, back, hide.
- Added edge IDs, ports, len, weight, heads, routing, label position.
- Added lanes, collapse, edges to groups.
- Added functions: chain, fanout, fanin, cycle, ask, from, parallel, pipeline, retry, fails and passes, merge, split, skip.
- Added let, repeat, template, use, import.
- Added classes, set, palette, states, themes list.
- Added layout controls: same rank, order, spacing, pin, align, wrap, keep.
- Added notes, legend, autonumber, links, tooltips, clicks, tags, layers, views.
- Added error and warning codes, grammar, AST, pipeline, CLI, API, conversions, writing guide, examples, tests.
- Removed all angle bracket placeholders.