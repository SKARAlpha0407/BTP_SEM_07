---
name: research-copilot-ui
description: Design system and rules for the Research Copilot frontend (frontend/). Load before changing any page, component, colour, font, animation or the reading-map graph, and before any "make it look better" request.
---

# Research Copilot UI

Precedence: the owner's words in the current request, then this file, then your
own taste.

## History (why it looks like this)

1. An indigo/violet dark redesign was rejected as "AI slopfest".
2. A quiet, hairline, serif reading-tool version was rejected as "boring, like a
   Soviet-era brutalist building".
3. The owner asked for the feel of the groq.com landing page, with more
   animation. That is the current layout, type and motion language.
4. The owner then asked for a palette like langchain.com: ice-blue / deep
   navy with a blue accent. That is the current palette (our own values).

Take the *language* of groq.com, never its brand: no Groq logo, wordmark, name,
copy or exact brand orange. Our mark is the three-block `PixelMark` in
`components/Motion.tsx`; our accent is our own blue (do not copy LangChain's exact values either).

## The language

- Ice-blue page and near-black navy ink in light; near-black navy page and
  pale ink in dark. One blue signal colour used sparingly (labels, active
  states, pixels, meters). The primary button is `--cta`: near-black in light,
  pale blue in dark.
- Big, tight grotesk display type (Geist, medium weight, negative tracking).
- Labels, nav, tabs, metadata: Geist Mono, 11px, UPPERCASE, `tracking-[0.14em]`
  (the `LABEL` constant in `pages/index.tsx`).
- Pill shapes for actions: outline pill in accent for secondary actions, filled
  accent pill for the primary one. Hairline `--line` dividers between sections
  and panes; no cards with shadows.
- Pixel motif: small accent squares that blink and hop (`Pixels`), segmented
  meters (`PixelMeter`), block progress (`PixelProgress`), a block cursor.
- The start page ends with a giant uppercase "RESEARCH COPILOT" wordmark.

## Motion (wanted, but purposeful)

All primitives live in `components/Motion.tsx`, keyframes in `styles/globals.css`.

| Effect | Where |
|---|---|
| `RevealWords`: words arrive pale (`--ghost`) and settle into ink | hero headline, synthesis text, TL;DR, loading topic |
| `ScrollInk`: a line darkens as it scrolls into the middle of the screen | "What happens when you search" section |
| `animate-rise`: fade up 10px, staggered | result rows, reader sections, buttons below the hero |
| `PixelMeter` blocks filling one by one | relevance in ranked rows |
| `Pixels` blinking/hopping squares | start page hero (md and up only), loading map pane |
| Sliding accent underline / side bar | active tab, selected row |

Rules: everything settles into a still, fully readable state within about two
seconds; the search field is usable within 0.5 s; `prefers-reduced-motion`
skips to the end state (globals.css); pixels never sit on top of text (hide them
below `md`). The reading map does **not** animate: the owner explicitly asked
for no animation in the graph.

## Tokens

All text pairs checked with the dataviz validator (>= 4.5:1 on page and surface).

| Token | Light | Dark | Use |
|---|---|---|---|
| `--page` | `#f1f7fc` | `#04070d` | app background |
| `--surface` | `#f8fbfe` | `#080c14` | reader and map panes, inputs |
| `--surface-2` | `#e2eef8` | `#0f1622` | empty meter blocks, chips |
| `--line` | `#cfe1ef` | `#1b2533` | hairlines |
| `--ink` | `#0a0f1a` | `#edf3fa` | primary text |
| `--ink-2` | `#3e4a5c` | `#a9b8ca` | secondary text |
| `--muted` | `#5a6678` | `#7f8da0` | labels, metadata |
| `--ghost` | `#c3d5e4` | `#1f2a38` | unrevealed text only (decorative) |
| `--accent` | `#0b66c3` | `#7cc4f4` | signal colour |
| `--accent-ink` | `#ffffff` | `#04070d` | text on accent fills |
| `--cta` | `#0a0f1a` | `#e3f2fd` | primary button fill |
| `--cta-ink` | `#ffffff` | `#04070d` | primary button text |
| `--mark` | `#d4e9fa` | `#0e3557` | query-term highlight, focus halo |
| `--warn` | `#8a5a00` | `#f0b44c` | warnings, always with an icon |

Components use the Tailwind names (`bg-page`, `text-ink`, `border-line`,
`text-accent`, ...). Never raw hex or palette classes (`zinc-*`, `indigo-*`).

## Still banned

Indigo/violet/purple accents, multi-hue gradients, gradient text, glow blobs,
glassmorphism/backdrop blur, emoji, sparkles icons for "AI", shimmering or
pulsing skeleton walls, animated particles on the graph, and copy like
"Unlock", "Supercharge", "Discover the frontier".

## Layout

- Start page: sticky nav (mark + name, "How it works", outline "Start
  searching" pill) and a mono status bar fed by `/health`; hero headline at
  `clamp(38px,4.7vw,66px)`, one sentence per line, offset left (`md:pl-[14%]`);
  pill search; mono example links; the scroll section; the wordmark footer with
  arXiv's requested acknowledgement.
- Results: three panes (ranked list | reader | map), stacking below 1024px.
  Ranked rows: zero-padded rank, title with highlighted query terms, author ·
  year · category, `PixelMeter` + score. Reader tabs: Synthesis / Paper.
- Reading map: year on a single-hue accent ramp, derived from `--accent` (pale
  -> deep on light, dim -> bright on dark), size = links, ring = ranked result, accent ring = selection,
  cluster filter pills. The camera is framed from laid-out node positions after
  `onEngineStop` (the library's `zoomToFit` framed a single point here).

## Before you finish any UI change

1. `cd frontend && npx tsc --noEmit && npm run build` passes.
2. `grep -rnE "indigo|violet|purple|fuchsia|bg-clip-text|backdrop-blur|blur-\[|animate-pulse|zinc-|gray-" frontend/pages frontend/components`
   prints nothing.
3. Look at it rendered: light and dark, 1440, 1180 and 400px wide, and assert
   `document.documentElement.scrollWidth` equals the viewport width.
   - The backend's CORS only allows `http://localhost:3000`, so serve the build
     there (`npx next start -p 3000`, with `./dev.sh` stopped).
   - Brave is Chromium: drive it with `puppeteer-core` from a tool folder outside
     the repo (`/Applications/Brave Browser.app/Contents/MacOS/Brave Browser`,
     args `--use-angle=swiftshader --enable-unsafe-swiftshader` for WebGL).
   - Wait ~3 s before screenshots so reveals have settled.
   - Flex children holding inputs need `min-w-0`, or the top bar overflows.
