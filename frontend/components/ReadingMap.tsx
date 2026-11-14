'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';
import { ArrowUpRight, X } from 'lucide-react';

/*
 * Reading map. Design rules: .claude/skills/kavosh-ui/SKILL.md
 * - Year is ordered, so it is one hue (the accent) on a pale->deep ramp, never a rainbow.
 * - Size = number of connections. Labels only where they help: the ranked
 *   results and whatever is connected to the selection.
 * - Nothing moves on its own: layout is computed before the first frame.
 */

interface GraphNode {
  id: number;
  title: string;
  val: number;
  // Optional so older responses (and the narrower type in lib/api.ts) still fit
  cluster?: string | null;
  year?: number;
  short_label?: string;
  degree?: number;
  primary_category?: string;
  author_surnames?: string[];
  arxiv_url?: string;
  pdf_url?: string;
}

interface GraphLink {
  // The force engine replaces ids with node objects once it starts.
  source: number | GraphNode;
  target: number | GraphNode;
  weight: number;
}

type Props = {
  data: { nodes: GraphNode[]; links: GraphLink[] };
  /** Titles of the ranked results; these keep a permanent label and ring. */
  rankedTitles?: string[];
  /** Title selected elsewhere (the ranked list); the map follows it. */
  selectedTitle?: string | null;
  /** Called when a node is picked in the map. */
  onSelectTitle?: (title: string | null) => void;
};

const endId = (end: number | GraphNode) => (typeof end === 'object' ? end.id : end);

/** arXiv returns http:// entry URLs; links should be https. */
const https = (url?: string) => (url ? url.replace(/^http:\/\//, 'https://') : '');
const arxivId = (url?: string) => (url ? url.split('/').pop() ?? '' : '');

const LINK_PILL =
  'inline-flex items-center gap-1 rounded-full border px-3 py-1 font-mono text-[11px] uppercase tracking-[0.12em] transition-colors duration-200';

/** arXiv page and PDF buttons for a paper in the map. */
function PaperLinks({ node }: { node: GraphNode }) {
  if (!node.arxiv_url && !node.pdf_url) {
    return <p className="text-[12px] text-muted">Links appear after the backend restarts.</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {node.arxiv_url && (
        <a
          href={https(node.arxiv_url)}
          target="_blank"
          rel="noreferrer"
          className={`${LINK_PILL} border-line text-ink-2 hover:border-accent hover:text-accent`}
        >
          arXiv page <ArrowUpRight className="h-3 w-3" aria-hidden />
        </a>
      )}
      {node.pdf_url && (
        <a
          href={https(node.pdf_url)}
          target="_blank"
          rel="noreferrer"
          className={`${LINK_PILL} border-accent text-accent hover:bg-accent hover:text-accent-ink`}
        >
          PDF <ArrowUpRight className="h-3 w-3" aria-hidden />
        </a>
      )}
    </div>
  );
}

function mix(a: string, b: string, t: number) {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const ch = (p: number, s: number) => (p >> s) & 255;
  const c = (s: number) => Math.round(ch(pa, s) + (ch(pb, s) - ch(pa, s)) * t);
  return `#${((c(16) << 16) | (c(8) << 8) | c(0)).toString(16).padStart(6, '0')}`;
}

function rampAt(ramp: string[], t: number) {
  const x = Math.max(0, Math.min(1, t)) * (ramp.length - 1);
  const i = Math.min(ramp.length - 2, Math.floor(x));
  return mix(ramp[i], ramp[i + 1], x - i);
}

type Tokens = { surface: string; line: string; ink2: string; muted: string; accent: string; font: string; dark: boolean };

/** Reads the design tokens from CSS so the WebGL scene matches the page theme. */
function useTokens(el: React.RefObject<HTMLElement | null>): Tokens | null {
  const [tokens, setTokens] = useState<Tokens | null>(null);
  useEffect(() => {
    const read = () => {
      const node = el.current;
      if (!node) return;
      const cs = getComputedStyle(node);
      const v = (name: string) => cs.getPropertyValue(name).trim();
      setTokens({
        surface: v('--surface'),
        line: v('--line'),
        ink2: v('--ink-2'),
        muted: v('--muted'),
        accent: v('--accent'),
        font: cs.fontFamily,
        dark: cs.colorScheme.includes('dark'),
      });
    };
    read();
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener('change', read);
    const mo = new MutationObserver(read);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => {
      mq.removeEventListener('change', read);
      mo.disconnect();
    };
  }, [el]);
  return tokens;
}

function ringSprite(color: string, radius: number, width: number) {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.arc(size / 2, size / 2, size / 2 - width, 0, Math.PI * 2);
  ctx.stroke();
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthWrite: false, transparent: true }),
  );
  const s = radius * 2 + 3;
  sprite.scale.set(s, s, 1);
  return sprite;
}

function labelSprite(text: string, color: string, font: string, weight: number) {
  const scale = 3; // draw at 3x so labels stay sharp when zoomed
  const fontSize = 13 * scale;
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  ctx.font = `${weight} ${fontSize}px ${font}`;
  const w = Math.ceil(ctx.measureText(text).width) + 8 * scale;
  canvas.width = w;
  canvas.height = fontSize * 1.6;
  ctx.font = `${weight} ${fontSize}px ${font}`;
  ctx.fillStyle = color;
  ctx.textBaseline = 'middle';
  ctx.fillText(text, 4 * scale, canvas.height / 2);
  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false, transparent: true }));
  const h = 5.5;
  sprite.scale.set((w / canvas.height) * h, h, 1);
  return sprite;
}

export default function ReadingMap({ data, rankedTitles = [], selectedTitle, onSelectTitle }: Props) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);
  const tokens = useTokens(wrapperRef);
  const [dims, setDims] = useState({ width: 0, height: 0 });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [cluster, setCluster] = useState<string | null>(null);

  // The 3D canvas sizes itself to the window unless told otherwise.
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const measure = () => setDims({ width: el.clientWidth, height: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const byId = useMemo(() => new Map(data.nodes.map((n) => [n.id, n])), [data.nodes]);
  const ranked = useMemo(() => new Set(rankedTitles), [rankedTitles]);

  // Follow selections made in the ranked list.
  useEffect(() => {
    if (selectedTitle === undefined) return;
    const hit = data.nodes.find((n) => n.title === selectedTitle);
    setSelectedId(hit ? hit.id : null);
  }, [selectedTitle, data.nodes]);

  const { minYear, maxYear } = useMemo(() => {
    const years = data.nodes.map((n) => n.year ?? 0).filter((y) => y > 0);
    return {
      minYear: years.length ? Math.min(...years) : 0,
      maxYear: years.length ? Math.max(...years) : 0,
    };
  }, [data.nodes]);

  const maxDegree = useMemo(() => Math.max(1, ...data.nodes.map((n) => n.degree ?? 0)), [data.nodes]);

  const clusters = useMemo(() => {
    const counts = new Map<string, number>();
    for (const n of data.nodes) if (n.cluster) counts.set(n.cluster, (counts.get(n.cluster) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [data.nodes]);

  // Neighbours of the selection, strongest link first.
  const neighbours = useMemo(() => {
    if (selectedId === null) return [];
    const out: { node: GraphNode; weight: number }[] = [];
    for (const l of data.links) {
      const s = endId(l.source);
      const t = endId(l.target);
      const other = s === selectedId ? t : t === selectedId ? s : null;
      const node = other === null ? undefined : byId.get(other);
      if (node) out.push({ node, weight: l.weight || 0 });
    }
    return out.sort((a, b) => b.weight - a.weight);
  }, [selectedId, data.links, byId]);
  const neighbourIds = useMemo(() => new Set(neighbours.map((n) => n.node.id)), [neighbours]);

  // One hue, old -> new: pale to deep on light surfaces, dim to bright on dark.
  const ramp = useMemo(() => {
    if (!tokens) return ['#cfe1ef', '#0b66c3'];
    return tokens.dark
      ? [mix(tokens.accent, tokens.surface, 0.62), tokens.accent, mix(tokens.accent, '#ffffff', 0.5)]
      : [mix(tokens.accent, tokens.surface, 0.7), tokens.accent, mix(tokens.accent, '#000000', 0.42)];
  }, [tokens]);
  const yearColor = useCallback(
    (year?: number) => {
      if (!year || !tokens) return tokens?.muted || '#8d93a1';
      const t = maxYear > minYear ? (year - minYear) / (maxYear - minYear) : 1;
      return rampAt(ramp, t);
    },
    [ramp, minYear, maxYear, tokens],
  );

  const isActive = useCallback(
    (n: GraphNode) => {
      if (selectedId !== null) return n.id === selectedId || neighbourIds.has(n.id);
      if (cluster) return n.cluster === cluster;
      return true;
    },
    [selectedId, neighbourIds, cluster],
  );

  const radiusOf = (n: GraphNode) => 1.8 + Math.sqrt(n.degree ?? 0) * 1.15;

  const nodeObject = useCallback(
    (raw: object) => {
      const n = raw as GraphNode;
      const group = new THREE.Group();
      if (!tokens) return group;
      const active = isActive(n);
      const r = radiusOf(n);
      const sphere = new THREE.Mesh(
        new THREE.SphereGeometry(r, 20, 20),
        new THREE.MeshBasicMaterial({
          color: yearColor(n.year),
          transparent: true,
          opacity: active ? 1 : 0.16,
        }),
      );
      group.add(sphere);

      const isSelected = n.id === selectedId;
      const isRanked = ranked.has(n.title);
      if (isSelected) group.add(ringSprite(tokens.accent, r, 9));
      else if (isRanked && active) group.add(ringSprite(tokens.ink2, r, 4));

      const showLabel = active && (isSelected || isRanked || neighbourIds.has(n.id));
      if (showLabel && n.short_label) {
        const label = labelSprite(n.short_label, tokens.ink2, tokens.font, isSelected ? 600 : 500);
        label.position.set(0, r + 3.2, 0);
        group.add(label);
      }
      return group;
    },
    [tokens, isActive, yearColor, selectedId, ranked, neighbourIds],
  );

  const linkColor = useCallback(
    (raw: object) => {
      if (!tokens) return '#888';
      const l = raw as GraphLink;
      if (selectedId !== null) {
        const touches = endId(l.source) === selectedId || endId(l.target) === selectedId;
        return touches ? tokens.accent : tokens.line;
      }
      return tokens.line;
    },
    [tokens, selectedId],
  );

  // Hover card: follows the pointed-at node and stays open while the pointer
  // moves onto it, so its links can be clicked.
  const [hover, setHover] = useState<{ node: GraphNode; x: number; y: number } | null>(null);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const overCard = useRef(false);
  const cancelHide = () => {
    if (hideTimer.current) clearTimeout(hideTimer.current);
    hideTimer.current = null;
  };
  const scheduleHide = () => {
    cancelHide();
    hideTimer.current = setTimeout(() => {
      if (!overCard.current) setHover(null);
    }, 350);
  };
  useEffect(() => cancelHide, []);
  const onNodeHover = (raw: object | null) => {
    if (!raw) return scheduleHide();
    const n = raw as GraphNode & { x?: number; y?: number; z?: number };
    const pt = fgRef.current?.graph2ScreenCoords(n.x ?? 0, n.y ?? 0, n.z ?? 0);
    if (!pt) return;
    cancelHide();
    setHover({ node: n, x: pt.x, y: pt.y });
  };

  const select = (n: GraphNode | null) => {
    setSelectedId(n ? n.id : null);
    onSelectTitle?.(n ? n.title : null);
  };

  const selected = selectedId !== null ? byId.get(selectedId) : undefined;

  // Frame the connected papers from their laid-out positions. Isolated papers
  // can drift far out and would shrink the map to a dot. Only after the
  // layout exists: fitting earlier frames a single point.
  const laidOut = useRef(false);
  const fit = useCallback(() => {
    const fg = fgRef.current;
    if (!laidOut.current || !fg) return;
    type P = GraphNode & { x?: number; y?: number; z?: number };
    const placed = (data.nodes as P[]).filter((n) => Number.isFinite(n.x) && Number.isFinite(n.y) && Number.isFinite(n.z));
    const linked = placed.filter((n) => (n.degree ?? 0) > 0);
    const pts = linked.length ? linked : placed;
    if (!pts.length) return;
    const c = { x: 0, y: 0, z: 0 };
    for (const n of pts) { c.x += n.x!; c.y += n.y!; c.z += n.z!; }
    c.x /= pts.length; c.y /= pts.length; c.z /= pts.length;
    let r = 1;
    for (const n of pts) r = Math.max(r, Math.hypot(n.x! - c.x, n.y! - c.y, n.z! - c.z) + radiusOf(n) + 6);
    const cam = fg.camera() as THREE.PerspectiveCamera;
    const vFov = THREE.MathUtils.degToRad(cam.fov);
    const hFov = 2 * Math.atan(Math.tan(vFov / 2) * cam.aspect);
    const dist = r / Math.sin(Math.min(vFov, hFov) / 2);
    fg.cameraPosition({ x: c.x, y: c.y, z: c.z + dist }, c, 0);
  }, [data.nodes]);
  useEffect(() => {
    laidOut.current = false;
  }, [data]);
  useEffect(() => {
    fit();
  }, [fit, dims.width, dims.height]);
  const onLayoutDone = useCallback(() => {
    laidOut.current = true;
    fit();
  }, [fit]);

  return (
    <div ref={wrapperRef} className="flex h-full min-h-0 flex-col bg-surface">
      <div className="flex h-11 shrink-0 items-center justify-between gap-3 border-b border-line px-4 font-mono text-[11px] uppercase tracking-[0.14em]">
        <p className="text-ink">
          Reading map{' '}
          <span className="text-muted tabular-nums">
            / {data.nodes.length} papers · {data.links.length} links
          </span>
        </p>
        <p className="hidden text-muted 2xl:block">Drag · zoom · click</p>
      </div>

      <div ref={canvasRef} className="relative min-h-[320px] flex-1 overflow-hidden">
        {tokens && dims.width > 0 && (
          <ForceGraph3D
            ref={fgRef}
            graphData={data}
            width={dims.width}
            height={dims.height}
            backgroundColor={tokens.surface}
            showNavInfo={false}
            nodeLabel={() => ''}
            onNodeHover={onNodeHover}
            nodeThreeObject={nodeObject}
            linkColor={linkColor}
            linkOpacity={1}
            linkWidth={0}
            onNodeClick={(n: object) => select(n as GraphNode)}
            onBackgroundClick={() => select(null)}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            warmupTicks={400}
            cooldownTicks={0}
            enableNodeDrag={false}
            onEngineStop={onLayoutDone}
          />
        )}
        {hover && (
          <div
            role="dialog"
            aria-label={hover.node.title}
            onMouseEnter={() => {
              overCard.current = true;
              cancelHide();
            }}
            onMouseLeave={() => {
              overCard.current = false;
              scheduleHide();
            }}
            className="absolute z-10 w-[280px] animate-rise rounded-md border border-line bg-surface p-3 shadow-[0_8px_24px_-12px_rgba(0,0,0,0.35)]"
            style={{
              left: Math.max(8, Math.min(hover.x + 16, dims.width - 288)),
              top: Math.max(8, Math.min(hover.y - 24, dims.height - 150)),
              animationDuration: '180ms',
            }}
          >
            <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted">
              {[arxivId(hover.node.arxiv_url) && `arXiv:${arxivId(hover.node.arxiv_url)}`, hover.node.short_label]
                .filter(Boolean)
                .join(' · ')}
            </p>
            <p className="mt-1.5 line-clamp-3 text-[13px] font-medium leading-snug text-ink">{hover.node.title}</p>
            <div className="mt-3">
              <PaperLinks node={hover.node} />
            </div>
          </div>
        )}
      </div>

      {/* Legend and cluster filter, or the selected paper's neighbourhood */}
      <div className="max-h-[45%] shrink-0 overflow-y-auto border-t border-line">
        {selected ? (
          <section className="px-4 py-3">
            <div className="flex items-start gap-3">
              <span
                className="mt-1.5 h-2.5 w-2.5 shrink-0"
                style={{ background: yearColor(selected.year) }}
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <h3 className="text-[15px] font-medium leading-snug tracking-[-0.01em] text-ink">{selected.title}</h3>
                <p className="mt-1 font-mono text-[12px] text-muted">
                  {[selected.short_label, selected.primary_category].filter(Boolean).join(' · ')}
                  {' · '}
                  {selected.degree ?? neighbours.length} links
                </p>
                {selected.cluster && <p className="mt-0.5 text-[12px] text-ink-2">{selected.cluster}</p>}
                <div className="mt-2.5">
                  <PaperLinks node={selected} />
                </div>
              </div>
              <button
                type="button"
                onClick={() => select(null)}
                aria-label="Clear selection"
                className="-mr-1 rounded-sm p-1 text-muted transition-colors duration-200 hover:bg-surface-2 hover:text-ink"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="mb-1 mt-4 font-mono text-[11px] uppercase tracking-[0.14em] text-accent">
              Most similar
            </p>
            {neighbours.length === 0 ? (
              <p className="text-[13px] text-muted">No links to other papers in this map.</p>
            ) : (
              <ul className="-mx-2">
                {neighbours.slice(0, 8).map(({ node, weight }) => (
                  <li key={node.id}>
                    <button
                      type="button"
                      onClick={() => select(node)}
                      className="flex w-full items-baseline gap-3 rounded-sm px-2 py-1.5 text-left transition-colors duration-200 hover:bg-surface-2"
                    >
                      <span className="w-9 shrink-0 font-mono text-[12px] text-muted tabular-nums">
                        {weight.toFixed(2)}
                      </span>
                      <span className="min-w-0 flex-1 truncate text-[13px] text-ink">{node.title}</span>
                      <span className="shrink-0 font-mono text-[11px] text-muted">{node.short_label}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ) : (
          <section className="flex flex-col gap-3 px-4 py-3">
            <dl className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-2 text-[12px]">
              <dt className="text-muted">Colour</dt>
              <dd className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-muted tabular-nums">{minYear || '—'}</span>
                <span
                  className="h-2 w-28 rounded-sm"
                  style={{ background: `linear-gradient(to right, ${ramp.join(', ')})` }}
                  aria-hidden
                />
                <span className="font-mono text-muted tabular-nums">{maxYear || '—'}</span>
                <span className="text-ink-2">publication year</span>
              </dd>
              <dt className="text-muted">Size</dt>
              <dd className="text-ink-2">links to other papers (most: {maxDegree})</dd>
              <dt className="text-muted">Ring</dt>
              <dd className="text-ink-2">one of your ranked results</dd>
            </dl>

            {clusters.length > 0 && (
              <div>
                <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.14em] text-accent">Clusters</p>
                <div className="flex flex-wrap gap-1.5">
                  {clusters.map(([name, count]) => {
                    const on = cluster === name;
                    return (
                      <button
                        key={name}
                        type="button"
                        aria-pressed={on}
                        onClick={() => setCluster(on ? null : name)}
                        className={`rounded-full border px-3 py-1 text-[12px] transition-colors duration-200 ${
                          on
                            ? 'border-accent bg-accent text-accent-ink'
                            : 'border-line text-ink-2 hover:bg-surface-2 hover:text-ink'
                        }`}
                      >
                        {name}
                        <span className={`ml-1.5 font-mono tabular-nums ${on ? '' : 'text-muted'}`}>{count}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
