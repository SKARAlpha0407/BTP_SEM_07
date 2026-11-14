'use client';

import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';

interface GraphNode {
  id: number;
  title: string;
  val: number;
  // Optional so older responses (and index.tsx's narrower type) still fit
  cluster?: string | null;
  year?: number;
  short_label?: string;
  degree?: number;
  primary_category?: string;
  author_surnames?: string[];
}

interface GraphLink {
  // The force engine replaces ids with node objects once it starts.
  source: number | GraphNode;
  target: number | GraphNode;
  weight: number;
}

const endId = (end: number | GraphNode) => (typeof end === 'object' ? end.id : end);

export default function ReadingMap({ data }: { data: { nodes: GraphNode[], links: GraphLink[] } }) {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // The 3D canvas sizes itself to the window unless told otherwise, so track
  // the container and hand it the real width and height.
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const measure = () => setDims({ width: el.clientWidth, height: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Dynamically calculate the min and max years from the actual data
  const { minYear, maxYear } = useMemo(() => {
    const years = data.nodes.map(n => n.year ?? 0).filter(y => y > 0);
    return {
      minYear: years.length ? Math.min(...years) : 2018,
      maxYear: years.length ? Math.max(...years) : 2025,
    };
  }, [data.nodes]);

  // A vibrant gradient (Turbo/Plasma style) that maps to the actual year range
  const yearColorScale = useCallback((year?: number) => {
    if (!year || year === 0) return '#9ca3af';
    const t = Math.max(0, Math.min(1, (year - minYear) / Math.max(1, maxYear - minYear)));
    // Gradient from Purple (old) -> Red -> Orange -> Yellow -> Green (new)
    const r = Math.round(255 * Math.min(1, Math.max(0, 1.5 - Math.abs(t * 4 - 3))));
    const g = Math.round(255 * Math.min(1, Math.max(0, 1.5 - Math.abs(t * 4 - 2))));
    const b = Math.round(255 * Math.min(1, Math.max(0, 1.5 - Math.abs(t * 4 - 1))));
    return `rgb(${r}, ${g}, ${b})`;
  }, [minYear, maxYear]);

  // Papers linked to the selected one, strongest link first
  const neighbours = useMemo(() => {
    if (!selectedNode) return [];
    const byId = new Map(data.nodes.map(n => [n.id, n]));
    const out: { node: GraphNode; weight: number }[] = [];
    for (const l of data.links) {
      const s = endId(l.source);
      const t = endId(l.target);
      const other = s === selectedNode.id ? t : t === selectedNode.id ? s : null;
      const node = other === null ? undefined : byId.get(other);
      if (node) out.push({ node, weight: l.weight || 0 });
    }
    return out.sort((a, b) => b.weight - a.weight);
  }, [selectedNode, data.nodes, data.links]);

  return (
    <div ref={wrapperRef} className="relative w-full h-full min-h-[320px] bg-transparent overflow-hidden">
      <div className="absolute top-3 left-3 z-10 bg-white/5 border border-white/10 text-zinc-300 backdrop-blur-md px-3 py-1.5 rounded-full text-[11px] font-medium tracking-wide">
        Reading map <span className="text-zinc-500">·</span> {data.nodes.length} papers{' '}
        <span className="text-zinc-500">· drag to rotate, scroll to zoom</span>
      </div>

      {dims.width > 0 && (
      <ForceGraph3D
        graphData={data}
        width={dims.width}
        height={dims.height}
        backgroundColor="rgba(0,0,0,0)"
        showNavInfo={false}
        nodeLabel={(n: any) => `${n.title} (${n.short_label})`}
        nodeColor={(n: any) => yearColorScale(n.year)}
        linkColor={(l: any) => `rgba(161, 161, 170, ${0.25 + (l.weight || 0.5) * 0.35})`}
        linkWidth={(l: any) => 0.5 + (l.weight || 0) * 1.5}
        linkOpacity={0.4}
        onNodeClick={(node: any) => {
          setSelectedNode(node);
        }}
        onBackgroundClick={() => setSelectedNode(null)}
        nodeThreeObject={(node: any) => {
          const radius = 1.5 + (node.val || 0) * 6;
          const geometry = new THREE.SphereGeometry(radius, 16, 16);
          const material = new THREE.MeshLambertMaterial({
            color: yearColorScale(node.year),
            transparent: true,
            opacity: 0.9,
          });
          const sphere = new THREE.Mesh(geometry, material);

          // Create text label sprite
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d');
          if (ctx) {
            canvas.width = 256;
            canvas.height = 64;
            ctx.font = '24px Sans-Serif';
            ctx.fillStyle = '#e4e4e7';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(node.short_label || '', 128, 32);

            const texture = new THREE.CanvasTexture(canvas);
            const spriteMaterial = new THREE.SpriteMaterial({ map: texture, depthTest: false });
            const sprite = new THREE.Sprite(spriteMaterial);
            sprite.scale.set(20, 5, 1);
            sprite.position.set(0, radius + 3, 0);

            const group = new THREE.Group();
            group.add(sphere);
            group.add(sprite);
            return group;
          }
          return sphere;
        }}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
        // No animation: run the whole layout before the first frame (alpha
        // decays to its floor in ~340 ticks at 0.02), then keep it still.
        // Node dragging would restart the simulation, so it is off;
        // rotate and zoom still work.
        warmupTicks={400}
        cooldownTicks={0}
        enableNodeDrag={false}
      />
      )}

      {/* Details panel for the clicked paper */}
      {selectedNode && (
        <aside className="absolute top-4 right-4 bottom-4 z-10 w-72 max-w-[calc(100%-2rem)] bg-zinc-950/80 backdrop-blur-md border border-white/10 rounded-xl shadow-2xl shadow-black/50 flex flex-col overflow-hidden">
          <div className="flex items-start gap-2 p-3 border-b border-white/10">
            <span
              className="mt-1 w-3 h-3 shrink-0 rounded-full"
              style={{ background: yearColorScale(selectedNode.year) }}
            />
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-semibold text-zinc-100 leading-snug">{selectedNode.title}</h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                {selectedNode.short_label || 'Unknown author'}
                {selectedNode.year && !(selectedNode.short_label || '').includes(String(selectedNode.year))
                  ? ` · ${selectedNode.year}` : ''}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedNode(null)}
              aria-label="Close details"
              className="shrink-0 text-zinc-500 hover:text-zinc-200 text-lg leading-none px-1 transition-colors"
            >
              ×
            </button>
          </div>

          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 px-3 py-2.5 text-xs border-b border-white/10">
            {selectedNode.primary_category && (
              <>
                <dt className="text-zinc-500">Category</dt>
                <dd className="text-zinc-200">{selectedNode.primary_category}</dd>
              </>
            )}
            {selectedNode.cluster && (
              <>
                <dt className="text-zinc-500">Cluster</dt>
                <dd className="text-zinc-200">{selectedNode.cluster}</dd>
              </>
            )}
            <dt className="text-zinc-500">Connections</dt>
            <dd className="text-zinc-200">{selectedNode.degree ?? neighbours.length}</dd>
            {selectedNode.author_surnames && selectedNode.author_surnames.length > 0 && (
              <>
                <dt className="text-zinc-500">Authors</dt>
                <dd className="text-zinc-200">{selectedNode.author_surnames.join(', ')}</dd>
              </>
            )}
          </dl>

          <div className="flex-1 min-h-0 overflow-y-auto px-3 py-2.5">
            <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-wide mb-1.5">
              Connected papers
            </p>
            {neighbours.length === 0 ? (
              <p className="text-xs text-zinc-500">No links to other papers in this map.</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {neighbours.map(({ node, weight }) => (
                  <li key={node.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedNode(node)}
                      className="w-full text-left rounded-md px-2 py-1.5 hover:bg-white/5 flex items-start gap-2 transition-colors"
                    >
                      <span
                        className="mt-1 w-2 h-2 shrink-0 rounded-full"
                        style={{ background: yearColorScale(node.year) }}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block text-xs text-zinc-200 leading-snug line-clamp-2">{node.title}</span>
                        <span className="block text-[10px] text-zinc-500">
                          {node.short_label ? `${node.short_label} · ` : ''}similarity {weight.toFixed(2)}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      )}

      {/* Dynamic Legend */}
      <div className="absolute bottom-3 left-3 z-10 bg-white/5 border border-white/10 text-zinc-300 backdrop-blur-md rounded-xl p-3 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-zinc-400 tabular-nums">{minYear}</span>
          <div className="w-24 h-2 rounded-full" style={{
            background: `linear-gradient(to right, ${yearColorScale(minYear)}, ${yearColorScale(minYear + (maxYear-minYear)/2)}, ${yearColorScale(maxYear)})`
          }} />
          <span className="text-[10px] text-zinc-400 tabular-nums">{maxYear}</span>
          <span className="text-[10px] font-medium text-zinc-300 ml-1">Year</span>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-zinc-400">
          <div className="w-2 h-2 rounded-full bg-zinc-500" />
          <div className="w-3.5 h-3.5 rounded-full bg-zinc-500" />
          <span className="ml-1">Node size = connections (degree)</span>
        </div>
      </div>
    </div>
  );
}
