'use client';

import { useState } from 'react';
import { useFirestoreData } from '@/hooks/useFirestoreData';
import { Sidebar } from '@/components/Sidebar';
import { MapPane } from '@/components/MapPane';
import { BriefingDrawer } from '@/components/BriefingDrawer';

export default function DashboardPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { locations, loading, error } = useFirestoreData();

  const selectedLocation = locations.find((loc) => loc.id === selectedId) ?? null;

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      <Sidebar
        locations={locations}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />

      <main className="flex-1 relative overflow-hidden">
        {/* Loading overlay */}
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950">
            <div className="flex flex-col items-center gap-4">
              <div className="w-10 h-10 border-2 border-slate-700 border-t-blue-400 rounded-full animate-spin" />
              <p className="text-sm text-slate-400">Loading locations…</p>
            </div>
          </div>
        )}

        {/* Error banner */}
        {error && !loading && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 bg-red-900/80 border border-red-700 text-red-200 text-sm px-4 py-2 rounded-lg max-w-sm text-center">
            Failed to load data: {error.message}
          </div>
        )}

        <MapPane
          locations={locations}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
      </main>

      {selectedLocation && (
        <BriefingDrawer
          location={selectedLocation}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
