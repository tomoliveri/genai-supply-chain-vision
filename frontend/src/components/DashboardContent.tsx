'use client';

import { useState, useEffect, useRef } from 'react';
import { useFirestoreData } from '@/hooks/useFirestoreData';
import { Sidebar } from '@/components/Sidebar';
import { MapPane } from '@/components/MapPane';
import { BriefingDrawer } from '@/components/BriefingDrawer';
import { StatsHeader } from '@/components/StatsHeader';
import { slugifyLocationName } from '@/lib/slugs';

interface DashboardContentProps {
  portSlug: string | null;
}

export function DashboardContent({ portSlug }: DashboardContentProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const { locations, stats, loading, error } = useFirestoreData();
  const autoSelectedRef = useRef(false);

  // Auto-select a port when deep-linked via ?port=<slug>
  useEffect(() => {
    if (!portSlug || autoSelectedRef.current || loading || locations.length === 0) return;

    const match = locations.find(
      (loc) => slugifyLocationName(loc.location_name) === portSlug
    );
    if (match) {
      setSelectedId(match.id);
      autoSelectedRef.current = true;
    }
  }, [portSlug, locations, loading]);

  const filteredLocations = searchQuery.trim()
    ? locations.filter((loc) =>
        loc.location_name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : locations;

  const selectedLocation = locations.find((loc) => loc.id === selectedId) ?? null;

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      <Sidebar
        locations={filteredLocations}
        selectedId={selectedId}
        onSelect={setSelectedId}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        stats={stats}
      />

      {/* Main area: stats header above map, proper flex layout — no overlap */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* Loading overlay */}
        {loading && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950">
            <div className="flex flex-col items-center gap-4">
              <div className="w-10 h-10 border-2 border-slate-700 border-t-blue-400 rounded-full animate-spin" />
              <p className="text-sm text-slate-400">Loading locations…</p>
            </div>
          </div>
        )}

        {/* Error banner */}
        {error && !loading && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 bg-red-900/80 border border-red-700 text-red-200 text-sm px-4 py-2 rounded-lg max-w-sm text-center">
            Failed to load data: {error.message}
          </div>
        )}

        {/* Stats bar — in flow, not absolute */}
        {!loading && locations.length > 0 && (
          <StatsHeader stats={stats} />
        )}

        {/* Map fills remaining height */}
        <div className="flex-1 relative">
          <MapPane
            locations={filteredLocations}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </div>
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
