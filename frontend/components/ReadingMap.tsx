
import React from 'react';
import dynamic from 'next/dynamic';
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });

export default function ReadingMap({ data }: { data: any }) {
  return (
    <div className="w-full h-[500px] bg-gray-50 rounded-xl border border-gray-200 overflow-hidden relative">
      <div className="absolute top-4 left-4 z-10 bg-white/80 p-2 rounded text-xs shadow-sm">
        Reading map · {data.nodes.length} papers · hover to inspect
      </div>
      <ForceGraph2D
        graphData={data}
        nodeLabel="title"
        nodeColor={() => '#3b82f6'}
        nodeVal={(node: any) => node.val * 20}
        linkColor={() => '#cbd5e1'}
        linkDirectionalParticles={2}
        linkDirectionalParticleSpeed={0.005}
        backgroundColor="#f9fafb"
      />
    </div>
  );
}
