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
    if (!fgRef.current) return;
    fgRef.current.d3Force('charge')?.strength(-300);
    fgRef.current.d3Force('link')?.distance(140);
  }, [data]);


  const sortedNodes = useMemo(() => {
    if (!data?.nodes) return [];
    return [...data.nodes].sort((a, b) => (b.val || 0) - (a.val || 0));
  }, [data]);

  const rankOf = (n: Node) => {
    return sortedNodes.findIndex((sn) => sn.id === n.id);
  };

  const radiusOf = (n: Node) => {
    const totalNodes = data?.nodes?.length || 0;
    return 32 - (rankOf(n) / Math.max(totalNodes - 1, 1)) * 13;
  };


  const colorOf = (n: Node) => {
    const totalNodes = data?.nodes?.length || 0;
    const hue = (rankOf(n) / Math.max(totalNodes - 1, 1)) * 280;
    return `hsl(${hue}, 72%, 48%)`;
  };


  const hasData = !!data && Array.isArray(data.nodes) && data.nodes.length > 0;


  const yearColorScale = (year: number) => {
    if (!year || year === 0) return '#9ca3af'; // fallback gray
    const minYear = 1990;
    const maxYear = 2025;
    const t = Math.max(0, Math.min(1, (year - minYear) / (maxYear - minYear)));
    // Gradient from #fcd34d (yellow) to #3b82f6 (blue)
    const r = Math.round(252 + (59 - 252) * t);
    const g = Math.round(211 + (130 - 211) * t);
    const b = Math.round(77 + (246 - 77) * t);
    return `rgb(${r}, ${g}, ${b})`;
  };

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
        graphData={data}
        nodeVal={(n: any) => 3 + (n.val || 0) * 15}
        nodeColor={(n: any) => yearColorScale(n.year)}
        linkColor={(l: any) => `rgba(156, 163, 175, ${0.2 + (l.weight || 0.5) * 0.5})`}
        linkWidth={(l: any) => 0.5 + (l.weight || 0) * 2}
        nodeCanvasObject={(node: any, ctx: any, globalScale: number) => {
          const label = node.short_label || node.title;
          const fontSize = 12 / globalScale;
          ctx.font = `${fontSize}px Sans-Serif`;
          const textWidth = ctx.measureText(label).width;
          const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);
          
          // Draw label background
          ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
          ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, bckgDimensions[0], bckgDimensions[1]);
          
          // Draw label text
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = '#1f2937';
          ctx.fillText(label, node.x, node.y);
          
          // Draw the node circle
          const radius = 3 + (node.val || 0) * 15;
          ctx.beginPath();
          ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
          ctx.fillStyle = yearColorScale(node.year);
          ctx.fill();
          ctx.lineWidth = 1 / globalScale;
          ctx.strokeStyle = '#ffffff';
          ctx.stroke();
        }}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
        cooldownTicks={100}
      />

          {hasData && (
            <div className="absolute bottom-3 left-3 z-10 bg-white/90 backdrop-blur border border-gray-200 rounded-lg p-3">
              <div className="flex items-center gap-3 text-xs text-gray-700">
                <div className="flex items-center gap-1.5">
                  <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: 'hsl(0, 72%, 48%)' }} />
                  <span className="text-gray-500">Most relevant</span>
                </div>
                <div className="flex-1 h-1 bg-gradient-to-r from-[#ef4444] via-[#f59e0b] to-[#8b5cf6] rounded-full" />
                <div className="flex items-center gap-1.5">
                  <span className="text-gray-500">Least relevant</span>
                  <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: 'hsl(280, 72%, 48%)' }} />
                </div>
              </div>
            </div>
          )}

        </>
      )}
    </div>
  );
}
