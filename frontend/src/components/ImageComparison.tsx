'use client';

import { useState, useRef, useCallback, useEffect } from 'react';

interface ImageComparisonProps {
  baselineUri: string;
  currentUri: string;
}

function gcsToHttps(uri: string): string {
  if (!uri.startsWith('gs://')) return uri;
  return `https://storage.googleapis.com/${uri.slice(5)}`;
}

export function ImageComparison({ baselineUri, currentUri }: ImageComparisonProps) {
  const [splitPct, setSplitPct] = useState(50);
  const [baselineLoaded, setBaselineLoaded] = useState(false);
  const [currentLoaded, setCurrentLoaded] = useState(false);
  const [error, setError] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const baselineUrl = gcsToHttps(baselineUri);
  const currentUrl = gcsToHttps(currentUri);
  const bothLoaded = baselineLoaded && currentLoaded;

  const updateSplit = useCallback((clientX: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    setSplitPct(Math.min(100, Math.max(0, ((clientX - rect.left) / rect.width) * 100)));
  }, []);

  // Non-passive touchmove so we can preventDefault and block page scroll while dragging.
  // React attaches touchmove as passive by default, so we wire this up via useEffect.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handler = (e: TouchEvent) => {
      if (!dragging.current) return;
      e.preventDefault();
      if (e.touches[0]) updateSplit(e.touches[0].clientX);
    };
    el.addEventListener('touchmove', handler, { passive: false });
    return () => el.removeEventListener('touchmove', handler);
  }, [updateSplit]);

  // Any touch/click anywhere on the container starts dragging from that position.
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    dragging.current = true;
    updateSplit(e.clientX);
  }, [updateSplit]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (dragging.current) updateSplit(e.clientX);
  }, [updateSplit]);

  const stopDrag = useCallback(() => { dragging.current = false; }, []);

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    dragging.current = true;
    if (e.touches[0]) updateSplit(e.touches[0].clientX);
  }, [updateSplit]);

  if (error) {
    return (
      <div className="flex items-center justify-center rounded-lg bg-slate-800 py-10 text-xs text-slate-500">
        Imagery unavailable
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <div
        ref={containerRef}
        className="relative w-full overflow-hidden rounded-lg bg-slate-900 select-none cursor-col-resize"
        style={{ aspectRatio: '1 / 1', touchAction: 'none' }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={stopDrag}
        onMouseLeave={stopDrag}
        onTouchStart={onTouchStart}
        onTouchEnd={stopDrag}
      >
        {!bothLoaded && (
          <div className="absolute inset-0 bg-slate-800 animate-pulse" />
        )}

        <img
          src={baselineUrl}
          alt="Baseline satellite image"
          className="absolute inset-0 h-full w-full object-cover"
          draggable={false}
          onLoad={() => setBaselineLoaded(true)}
          onError={() => setError(true)}
        />

        <div
          className="absolute inset-0"
          style={{ clipPath: `inset(0 0 0 ${splitPct}%)` }}
        >
          <img
            src={currentUrl}
            alt="Current satellite image"
            className="h-full w-full object-cover"
            draggable={false}
            onLoad={() => setCurrentLoaded(true)}
            onError={() => setError(true)}
          />
        </div>

        {bothLoaded && (
          <>
            <span className="absolute left-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-xs font-semibold text-white backdrop-blur-sm pointer-events-none">
              Baseline
            </span>
            <span className="absolute right-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-xs font-semibold text-white backdrop-blur-sm pointer-events-none">
              Current
            </span>
          </>
        )}

        {/* Drag handle — visual only, interaction is on the whole container */}
        {bothLoaded && (
          <div
            className="absolute bottom-0 top-0 w-px bg-white/80 pointer-events-none"
            style={{ left: `${splitPct}%` }}
          >
            <div className="absolute left-1/2 top-1/2 flex h-9 w-9 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white shadow-lg">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                <path d="M4 7H10M4 7L2 5M4 7L2 9M10 7L12 5M10 7L12 9"
                  stroke="#374151" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>
        )}
      </div>

      {bothLoaded && (
        <p className="text-center text-xs text-slate-600">Drag anywhere to compare</p>
      )}
    </div>
  );
}
