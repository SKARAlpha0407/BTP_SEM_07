---
name: research-copilot-ui
description: Design system and rules for the Research Copilot frontend (frontend/). Load before changing any page, component, colour, font or the reading-map graph, and before any "make it look better" request. Encodes the owner's rejection of AI-slop styling.
---

# Research Copilot UI

The owner rejected the previous dark redesign as "AI slopfest". This skill is the
design system that replaces it. Precedence: the owner's words in the current
request, then this file, then your own taste.

## What the product is

A research tool. A student types a topic; the app ranks arXiv papers, summarises
them and draws how they connect. People scan, compare and read. Design it like a
reference manager or a well-made reading tool, not a marketing page. The craft is
information design and typography, not effects.

Subject details to use as content, never as ornament: arXiv IDs (`2611.17332`),
primary categories (`cs.CL`, `stat.ML`), first-author-year labels (`Gao 2024`),
cosine relevance, the cross-paper synthesis as a reading text.

## Banned (AI-slop markers)

Never ship any of these unless the owner explicitly asks for it:

- Indigo, violet, purple or fuchsia accents; purple-to-blue or any multi-hue gradient
- Gradient text (`bg-clip-text text-transparent`)
- Glow blobs, blurred colour orbs, radial "ambient" washes, coloured shadows
- Glassmorphism: `backdrop-blur` panels, `bg-white/5` with `border-white/10`
- Grid or dot-pattern backgrounds, noise textures
- Near-black page with one neon/acid accent; warm cream + serif + terracotta
- `rounded-xl`/`rounded-2xl`/`rounded-full` on everything; pills for things that are not toggles or tags
- Sparkles/magic-wand icons for "AI"; emoji as section markers
- Giant centred hero with an eyebrow badge, headline and three suggestion pills
- Zero-padded decorative numbering (`01`, `02`). Rank numbers are fine because rank is a real order, but plain (`1`, `2`).
- Pulsing skeleton walls; marquee/shimmer effects; animated particles on graphs
- Copy like "Discover the frontier of…", "Unlock", "Supercharge", "Mapping the landscape…"

## Tokens

Neutrals carry a slight cool bias toward the accent. One accent: ink blue, taken
from the validated dataviz ramp so the UI and the graph share a hue. A second,
functional colour: highlighter yellow, used only to mark query terms found in a
paper (what a reader does with a highlighter). All text pairs below were checked
with the dataviz validator: every text colour is at least 4.5:1 on its surface.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--page` | `#f6f7f8` | `#0f1114` | app background |
| `--surface` | `#ffffff` | `#16191e` | panels, list, reader |
| `--surface-2` | `#eef0f3` | `#1d2127` | hover, selected row, code |
| `--line` | `#e1e4e9` | `#272c33` | 1px hairlines, the only separators |
| `--ink` | `#14171c` | `#e6e8eb` | primary text |
| `--ink-2` | `#525866` | `#b1b7c2` | secondary text |
| `--muted` | `#666c7a` | `#8d93a1` | labels, metadata (>= 4.9:1) |
| `--accent` | `#1c5cab` | `#5598e7` | links, focus ring, selected marker, primary button |
| `--accent-ink` | `#ffffff` | `#0f1114` | text on an accent fill |
| `--mark` | `#fde7a6` | `#5a4613` | highlighter behind matched terms |
| `--warn` | `#8a5a00` | `#f0b44c` | grounding warnings (always with an icon + words) |

Define them as CSS variables in `frontend/styles/globals.css` and expose them to
Tailwind v4 with `@theme inline` (for example `--color-page: var(--page)`), so
classes read `bg-page text-ink border-line`. Light values on `:root`, dark under
`@media (prefers-color-scheme: dark)`, plus a `[data-theme]` override if a toggle
exists. Never write a raw hex or a Tailwind palette class (`zinc-*`, `indigo-*`)
in a component.

## Type

| Role | Face | Where |
|---|---|---|
| UI | Inter | controls, labels, metadata, body text |
| Reading | Source Serif 4 | paper titles, the synthesis, TL;DR, abstracts |
| Data | JetBrains Mono | arXiv IDs, scores, years, counts |

Papers are typeset documents, so titles and reading text get a text serif; the
tool chrome stays in a quiet sans. Load fonts with `next/font/google` (check
`frontend/node_modules/next/dist/docs/` first: this Next version has breaking
changes, see `frontend/AGENTS.md`). Scale (px): 12 / 13 / 14 / 16 / 20 / 28. UI
text is 13-14px; reading text 16px at line-height 1.6 and about 68ch wide.
Uppercase labels: 11px, `tracking-[0.06em]`, `--muted`. Numbers that line up use
`tabular-nums`.

## Shape and space

- Radius: 4px controls and tags, 6px panels. Nothing rounder.
- Separation comes from 1px `--line` hairlines and spacing, not cards. Use a
  bordered box only for something that is genuinely a separate object (the
  search field, a warning).
- No shadows, except a small one on floating popovers.
- 4px spacing grid; dense lists (row padding 10-12px).
- Focus: 2px `--accent` outline with 2px offset on every interactive element.
- Motion: colour/background transitions of 120ms only; nothing moves on its
  own; respect `prefers-reduced-motion`.

## Layout

- **Start page:** a working page, left-aligned in a 720px column: product name in
  plain text, one sentence on what the tool does, the search field with a
  button, then example topics as a plain list of text buttons. No hero.
- **Results:** three panes like a reference manager, separated by hairlines:
  ranked list (about 340px), reading pane (flexible) with the selected paper or
  the synthesis, and the reading map. The map is a tool for exploring, so give
  it a pane of its own or a tab; do not let it push the reading text off screen.
- **Ranked row:** rank, title in serif, first author · year · category in
  muted mono/sans, matched terms highlighted with `--mark` inside the title
  text itself, relevance as a mono number plus a 2px bar in `--accent`.
- **Loading:** keep the layout; show the five pipeline steps as a plain
  checklist with the current step named, and faint static placeholder rows. No
  pulsing.
- **Empty and error states:** say what happened and what to try, in one or two
  sentences.
- Below 1024px the panes stack: list, then reader, then map.

## Reading map (graph)

Follow the dataviz skill. Year is an ordered quantity, so it is a **single-hue
sequential ramp** (blue, from the dataviz palette: older = lighter on light
surfaces), never a rainbow. Node size = degree. Labels use `--ink-2`, links
`--line` at full opacity, the selected node gets a 2px `--accent` ring and its
neighbours stay at full strength while others dim. Canvas background is the pane
surface (`--surface`), not black and not transparent over a gradient. No particles,
no auto-rotation, no settling animation. Legend: a small year ramp with the real
min and max years, and one line on size.

## Before you finish any UI change

1. `cd frontend && npx tsc --noEmit && npm run build` passes.
2. Search the diff for banned classes:
   `grep -nE "indigo|violet|purple|fuchsia|bg-clip-text|backdrop-blur|blur-\[|rounded-(xl|2xl|3xl)|animate-pulse|shadow-.*-500" frontend/pages frontend/components`
   must print nothing.
3. Look at it rendered in both themes, at desktop and at 400px wide, when the
   session can. Say plainly if you could not.

## Checking it rendered (lessons from the first rebuild)

- The backend's CORS only allows `http://localhost:3000`, so serve the build on
  port 3000 (`npx next start -p 3000`, with `./dev.sh` stopped) or searches fail.
- Brave is installed and is Chromium: drive it with `puppeteer-core` from a tool
  folder outside the repo (`executablePath: '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser'`,
  args `--use-angle=swiftshader --enable-unsafe-swiftshader` so WebGL renders).
  Emulate `prefers-color-scheme` for both themes; check 1440, 1180 and 400 wide,
  and assert `document.documentElement.scrollWidth` equals the viewport width.
- Flex children holding inputs need `min-w-0`, or the top bar overflows on phones.
- Reading map: `zoomToFit` from react-force-graph-3d framed a single point here.
  ReadingMap frames the camera itself from laid-out node positions after
  `onEngineStop`; keep it that way.
