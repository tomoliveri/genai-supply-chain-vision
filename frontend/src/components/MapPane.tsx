'use client';

import dynamic from 'next/dynamic';
import type { LocationWithBriefing } from '@/lib/types';

interface MapPaneProps {
  locations: LocationWithBriefing[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const MapLayer = dynamic(
  () => import('./MapLayer').then((mod) => mod.MapLayer),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full w-full items-center justify-center bg-slate-900">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-slate-600 border-t-blue-400 rounded-full animate-spin" />
          <span className="text-sm text-slate-500">Loading map…</span>
        </div>
      </div>
    ),
  },
);

export function MapPane({ locations, selectedId, onSelect }: MapPaneProps) {
  return (
    <div className="h-full w-full">
      <MapLayer locations={locations} selectedId={selectedId} onSelect={onSelect} />
    </div>
  );
}
