'use client';

import dynamic from 'next/dynamic';
import type { LocationWithBriefing } from '@/lib/types';

interface MapPaneProps {
  locations: LocationWithBriefing[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const MapLayer = dynamic(
  () => import('./GoogleMapLayer').then((m) => m.GoogleMapLayer),
  { ssr: false },
);

export function MapPane({ locations, selectedId, onSelect }: MapPaneProps) {
  return (
    <div className="h-full w-full">
      <MapLayer
        locations={locations}
        selectedId={selectedId}
        onSelect={onSelect}
      />
    </div>
  );
}
