import React, { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

type Node = {
  id: number;
  title: string;
  val: number;
  cluster?: string;
};

type Link = {
  source: number | Node;
  target: number | Node;
  weight: number;
};

type GraphData = {
  nodes: Node[];
  links: Link[];
};

const CLUSTER_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444',
  '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1',
];

export default function ReadingMap({ data }: { data: GraphData }) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);
  const [dims, setDims] = useState({ width: 800, height: 500 });

  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const measure = () =>
      setDims({ width: el.clientWidth, height: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const clusterList = useMemo(() => {
    if (!data?.nodes) return [] as string[];
    return Array.from(
      new Set(data.nodes.map((n) => n.cluster).filter(Boolean))
    ) as string[];
  }, [data]);

  const colorOf = (c?: string) => {
    const i = c ? clusterList.indexOf(c) : -1;
    return i >= 0 ? CLUSTER_COLORS[i % CLUSTER_COLORS.length] : '#94a3b8';
  };

  const hasData = !!data && Array.isArray(data.nodes) && data.nodes.length > 0;

  return (
    <div
      ref={wrapperRef}
      className="w-full h-[500px] bg-gray-50 rounded-xl border border-gray-200 overflow-hidden relative"
    >
      {!hasData ? (
        <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm">
          No graph data
        </div>
      ) : (
        <>
          <div className="absolute top-3 left-3 z-10 bg-white/90 backdrop-blur border border-gray-200 rounded-lg px-3 py-1.5 text-xs text-gray-600">
            Reading map · {data.nodes.length} papers · hover to inspect
          </div>

          <ForceGraph2D
            ref={fgRef}
            graphData={data}
            width={dims.width}
            height={dims.height}
            backgroundColor="#f9fafb"
            warmupTicks={100}
            cooldownTicks={60}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            onEngineStop={() => fgRef.current?.zoomToFit(400, 80)}
            nodeRelSize={6}
            nodeVal={(n: any) => Math.max((n.val || 0.5) * 40, 8)}
            nodeColor={(n: any) => colorOf(n.cluster)}
            nodeLabel={(n: any) => `${n.title}\n${n.cluster ?? ''}`}
            linkColor={(l: any) => `rgba(59, 130, 246, ${Math.min(0.35 + (l.weight ?? 0.5), 0.9)})`}
            linkWidth={(l: any) => Math.max((l.weight || 0) * 2.5, 1.5)}
            linkDirectionalParticles={2}
            linkDirectionalParticleWidth={1.5}
            linkDirectionalParticleSpeed={0.004}
            linkCurvature={0.15}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={0.5}
          />

          {clusterList.length > 0 && (
            <div className="absolute bottom-3 left-3 z-10 bg-white/90 backdrop-blur border border-gray-200 rounded-lg p-3">
              <div className="text-xs font-semibold text-gray-500 mb-1.5">
                Clusters
              </div>
              <div className="flex flex-wrap gap-x-3 gap-y-1">
                {clusterList.map((c) => (
                  <div
                    key={c}
                    className="flex items-center gap-1.5 text-xs text-gray-700"
                  >
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: colorOf(c) }}
                    />
                    {c}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
