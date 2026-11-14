import React, { useEffect, useRef, useState } from 'react';

/*
 * Motion primitives for Research Copilot. Everything settles into a still,
 * fully readable state, and prefers-reduced-motion (globals.css) skips straight
 * to it.
 */

/** Words arrive pale and settle into ink, one after another. */
export function RevealWords({
  text,
  delay = 0,
  step = 28,
  className,
}: {
  text: string;
  delay?: number;
  step?: number;
  className?: string;
}) {
  const words = text.split(/(\s+)/);
  let i = 0;
  return (
    <span className={className}>
      {words.map((w, k) =>
        /^\s+$/.test(w) ? (
          w
        ) : (
          <span key={k} className="animate-ink" style={{ animationDelay: `${delay + step * i++}ms` }}>
            {w}
          </span>
        ),
      )}
    </span>
  );
}

/**
 * A line that is pale until it scrolls into the middle of the screen, then
 * darkens to ink, like reading down a page. Scrolling back fades it again.
 */
export function ScrollInk({ children, className }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const [lit, setLit] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setLit(e.isIntersecting || e.boundingClientRect.top < 0), {
      rootMargin: '0px 0px -38% 0px',
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <p
      ref={ref}
      className={`transition-colors duration-700 ease-[var(--ease-out-soft)] ${lit ? 'text-ink' : 'text-ghost'} ${className ?? ''}`}
    >
      {children}
    </p>
  );
}

type Px = { top?: string; left?: string; right?: string; bottom?: string; w: number; h: number; dx: number; dy: number; d: number };

// Fixed positions so server and client render the same markup.
const PIXELS: Px[] = [
  { top: '22%', left: '5%', w: 14, h: 14, dx: 14, dy: 0, d: 0 },
  { top: '46%', right: '11%', w: 13, h: 26, dx: 0, dy: -14, d: 900 },
  { top: '71%', left: '2.5%', w: 13, h: 26, dx: 13, dy: 0, d: 1800 },
  { top: '64%', right: '6%', w: 26, h: 13, dx: -26, dy: 13, d: 2700 },
  { top: '12%', right: '22%', w: 10, h: 10, dx: 10, dy: 10, d: 3600 },
  { bottom: '14%', left: '9%', w: 36, h: 13, dx: 0, dy: -13, d: 1300 },
];

/** Blocky accent pixels that blink and hop near the page edges. Decorative. */
export function Pixels({ className }: { className?: string }) {
  return (
    <div aria-hidden className={`pointer-events-none absolute inset-0 overflow-hidden ${className ?? ''}`}>
      {PIXELS.map((p, i) => (
        <span
          key={i}
          className="absolute animate-pixel bg-accent"
          style={
            {
              top: p.top,
              left: p.left,
              right: p.right,
              bottom: p.bottom,
              width: p.w,
              height: p.h,
              animationDelay: `${p.d}ms`,
              '--px-dx': `${p.dx}px`,
              '--px-dy': `${p.dy}px`,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}

/** A segmented meter: `value` 0..1 fills that share of blocks, one by one. */
export function PixelMeter({ value, blocks = 20, delay = 0 }: { value: number; blocks?: number; delay?: number }) {
  const on = Math.round(Math.max(0, Math.min(1, value)) * blocks);
  return (
    <span className="flex flex-1 gap-[2px]" aria-hidden>
      {Array.from({ length: blocks }, (_, i) => (
        <span key={i} className="h-[6px] flex-1 bg-surface-2">
          {i < on && (
            <span className="block h-full animate-fill bg-accent" style={{ animationDelay: `${delay + i * 18}ms` }} />
          )}
        </span>
      ))}
    </span>
  );
}

/** Progress made of blocks, with a scanning block while work is running. */
export function PixelProgress({ step, steps }: { step: number; steps: number }) {
  const blocks = 24;
  const done = Math.round(((Math.max(0, step) + 1) / steps) * blocks);
  return (
    <div className="relative flex gap-[3px]" role="progressbar" aria-valuemin={0} aria-valuemax={steps} aria-valuenow={step + 1}>
      {Array.from({ length: blocks }, (_, i) => (
        <span
          key={i}
          className={`h-3 flex-1 transition-colors duration-300 ${i < done ? 'bg-accent' : 'bg-surface-2'}`}
        />
      ))}
    </div>
  );
}

/** A block cursor that blinks after a label, terminal style. */
export function Cursor() {
  return <span aria-hidden className="ml-1 inline-block h-[0.9em] w-[0.5em] translate-y-[0.1em] animate-blink bg-accent" />;
}

/** Our mark: a small pixel glyph (three blocks), not anyone else's logo. */
export function PixelMark({ size = 18 }: { size?: number }) {
  const u = size / 3;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden className="shrink-0">
      <rect x={0} y={0} width={u * 2} height={u} fill="var(--accent)" />
      <rect x={0} y={u} width={u} height={u * 2} fill="var(--accent)" />
      <rect x={u * 2} y={u * 2} width={u} height={u} fill="var(--accent)" />
    </svg>
  );
}
