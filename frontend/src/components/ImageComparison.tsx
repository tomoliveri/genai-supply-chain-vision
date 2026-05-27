'use client';

import { useState, useRef, useCallback } from 'react';

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
    const pct = Math.min(100, Math.max(0, ((clientX - rect.left) / rect.width) * 100));
    setSplitPct(pct);
  }, []);

  const onMouseDown = () => { dragging.current = true; };
  const onMouseUp = () => { dragging.current = false; };
  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (dragging.current) updateSplit(e.clientX);
  }, [updateSplit]);

  const onTouchStart = () => { dragging.current = true; };
  const onTouchEnd = () => { dragging.current = false; };
  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (dragging.current && e.touches[0]) updateSplit(e.touches[0].clientX);
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
        style={{ aspectRatio: '1 / 1' }}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        {/* Loading skeleton */}
        {!bothLoaded && (
          <div className="absolute inset-0 bg-slate-800 animate-pulse" />
        )}

        {/* Baseline image — full width, bottom layer */}
        <img
          src={baselineUrl}
          alt="Baseline satellite image"
          className="absolute inset-0 h-full w-full object-cover"
          onLoad={() => setBaselineLoaded(true)}
          onError={() => setError(true)}
        />

        {/* Current image — clipped to the right of the handle */}
        <div
          className="absolute inset-0"
          style={{ clipPath: `inset(0 0 0 ${splitPct}%)` }}
        >
          <img
            src={currentUrl}
            alt="Current satellite image"
            className="h-full w-full object-cover"
            onLoad={() => setCurrentLoaded(true)}
            onError={() => setError(true)}
          />
        </div>

        {/* Labels */}
        {bothLoaded && (
          <>
            <span className="absolute left-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-xs font-semibold text-white backdrop-blur-sm">
              Baseline
            </span>
            <span className="absolute right-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-xs font-semibold text-white backdrop-blur-sm">
              Current
            </span>
          </>
        )}

        {/* Drag handle */}
        {bothLoaded && (
          <div
            className="absolute bottom-0 top-0 w-px bg-white/80"
            style={{ left: `${splitPct}%` }}
            onMouseDown={onMouseDown}
            onTouchStart={onTouchStart}
          >
            <div className="absolute left-1/2 top-1/2 flex h-7 w-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white shadow-lg">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                <path d="M4 7H10M4 7L2 5M4 7L2 9M10 7L12 5M10 7L12 9"
                  stroke="#374151" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>
        )}
      </div>

      {bothLoaded && (
        <p className="text-center text-xs text-slate-600">Drag to compare baseline vs. current</p>
      )}
    </div>
  );
}
