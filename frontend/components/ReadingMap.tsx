'use client';

import React, { useMemo, useState, useCallback } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';

interface GraphNode {
  id: number;
  title: string;
  val: number;
  cluster: string;
  year: number;
  short_label: string;
  degree: number;
}

interface GraphLink {
  source: number;
  target: number;
  weight: number;
}

export default function ReadingMap({ data }: { data: { nodes: GraphNode[], links: GraphLink[] } }) {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Dynamically calculate the min and max years from the actual data
  const { minYear, maxYear } = useMemo(() => {
    const years = data.nodes.map(n => n.year).filter(y => y > 0);
    return {
      minYear: years.length ? Math.min(...years) : 2018,
      maxYear: years.length ? Math.max(...years) : 2025,
    };
  }, [data.nodes]);

  // A vibrant gradient (Turbo/Plasma style) that maps to the actual year range
  const yearColorScale = useCallback((year: number) => {
    if (!year || year === 0) return '#9ca3af';
    const t = Math.max(0, Math.min(1, (year - minYear) / Math.max(1, maxYear - minYear)));
    // Gradient from Purple (old) -> Red -> Orange -> Yellow -> Green (new)
    const r = Math.round(255 * Math.min(1, Math.max(0, 1.5 - Math.abs(t * 4 - 3))));
    const g = Math.round(255 * Math.min(1, Math.max(0, 1.5 - Math.abs(t * 4 - 2))));
    const b = Math.round(255 * Math.min(1, Math.max(0, 1.5 - Math.abs(t * 4 - 1))));
    return `rgb(${r}, ${g}, ${b})`;
  }, [minYear, maxYear]);

  return (
    <div className="relative w-full h-[600px] bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="absolute top-4 left-4 z-10 bg-white/80 backdrop-blur border border-gray-200 px-3 py-1.5 rounded-md text-xs font-medium text-gray-600 shadow-sm">
        Reading map · {data.nodes.length} papers · drag to rotate, scroll to zoom
      </div>

      <ForceGraph3D
        graphData={data}
        nodeLabel={(n: any) => `${n.title} (${n.short_label})`}
        nodeColor={(n: any) => yearColorScale(n.year)}
        linkColor={(l: any) => `rgba(156, 163, 175, ${0.2 + (l.weight || 0.5) * 0.3})`}
        linkWidth={(l: any) => 0.5 + (l.weight || 0) * 1.5}
        linkOpacity={0.4}
        linkDirectionalParticles={2}
        linkDirectionalParticleWidth={1.5}
        linkDirectionalParticleSpeed={0.005}
        onNodeClick={(node: any) => {
          setSelectedNode(node);
        }}
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
            ctx.fillStyle = '#1f2937';
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
        cooldownTicks={100}
      />

      {/* Dynamic Legend */}
      <div className="absolute bottom-4 left-4 z-10 bg-white/90 backdrop-blur border border-gray-200 rounded-md shadow-sm p-3 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-500">{minYear}</span>
          <div className="w-24 h-2 rounded-full" style={{
            background: `linear-gradient(to right, ${yearColorScale(minYear)}, ${yearColorScale(minYear + (maxYear-minYear)/2)}, ${yearColorScale(maxYear)})`
          }} />
          <span className="text-[10px] text-gray-500">{maxYear}</span>
          <span className="text-[10px] font-medium text-gray-700 ml-1">Year</span>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-gray-500">
          <div className="w-2 h-2 rounded-full bg-gray-400" />
          <div className="w-3.5 h-3.5 rounded-full bg-gray-400" />
          <span className="ml-1">Node size = connections (degree)</span>
        </div>
      </div>
    </div>
  );
}
