'use client';

import { useCallback, useState } from 'react';
import { useFirestoreData } from '@/hooks/useFirestoreData';
import { Sidebar } from '@/components/Sidebar';
import { MapPane } from '@/components/MapPane';
import { BriefingDrawer } from '@/components/BriefingDrawer';
import { StatsHeader } from '@/components/StatsHeader';
import { slugifyLocationName } from '@/lib/slugs';
import { List, Map } from 'lucide-react';

interface DashboardContentProps {
  portSlug: string | null;
}

type MobileView = 'list' | 'map';

export function DashboardContent({ portSlug }: DashboardContentProps) {
  const [selectedId, setSelectedId] = useState<string | null | undefined>(undefined);
  const [searchQuery, setSearchQuery] = useState('');
  const [mobileView, setMobileView] = useState<MobileView>('list');
  const { locations, stats, loading, error } = useFirestoreData();
  const handleSelect = useCallback((id: string) => setSelectedId(id), []);
  const handleCloseBriefing = useCallback(() => setSelectedId(null), []);

  const portMatchedId = portSlug
    ? locations.find((loc) => slugifyLocationName(loc.location_name) === portSlug)?.id
    : null;
  const activeSelectedId = selectedId === undefined ? portMatchedId ?? null : selectedId;

  const filteredLocations = searchQuery.trim()
    ? locations.filter((loc) =>
        loc.location_name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : locations;

  const selectedLocation = locations.find((loc) => loc.id === activeSelectedId) ?? null;

  return (
    // `relative` here is the containing block for the mobile absolute overlay below.
    // Do NOT put overflow:hidden on this element — that would clip the overlay on iOS Safari.
    <div className="flex flex-col h-[100dvh] bg-slate-950 relative">

      {/* Content row — overflow:hidden keeps the desktop flex layout tight */}
      <div className="flex-1 flex overflow-hidden min-h-0">

        {/* Sidebar — full width on mobile (list tab), fixed width on desktop */}
        <div className={`flex flex-col overflow-hidden w-full md:w-80 md:shrink-0 ${
          mobileView === 'list' ? 'flex' : 'hidden md:flex'
        }`}>
          <Sidebar
            locations={filteredLocations}
            selectedId={activeSelectedId}
            onSelect={handleSelect}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            stats={stats}
          />
        </div>

        {/* Map area */}
        <main className={`flex-1 flex flex-col overflow-hidden relative ${
          mobileView === 'map' ? 'flex' : 'hidden md:flex'
        }`}>
          {loading && (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950">
              <div className="flex flex-col items-center gap-4">
                <div className="w-10 h-10 border-2 border-slate-700 border-t-blue-400 rounded-full animate-spin" />
                <p className="text-sm text-slate-400">Loading locations…</p>
              </div>
            </div>
          )}

          {error && !loading && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 bg-red-900/80 border border-red-700 text-red-200 text-sm px-4 py-2 rounded-lg max-w-sm text-center">
              Failed to load data: {error.message}
            </div>
          )}

          {!loading && locations.length > 0 && (
            <StatsHeader stats={stats} />
          )}

          <div className="flex-1 relative">
            <MapPane
              locations={filteredLocations}
              selectedId={activeSelectedId}
              onSelect={handleSelect}
            />
          </div>
        </main>

        {/* Desktop briefing drawer — inside the overflow:hidden row, no fixed positioning */}
        {selectedLocation && (
          <div className="hidden md:block w-[420px] shrink-0 h-full">
            <BriefingDrawer
              location={selectedLocation}
              onClose={handleCloseBriefing}
            />
          </div>
        )}
      </div>

      {/* Mobile bottom tab bar */}
      <div className="md:hidden shrink-0 flex border-t border-slate-700/80 bg-slate-900">
        <button
          type="button"
          onClick={() => setMobileView('list')}
          className={`flex-1 flex flex-col items-center gap-0.5 py-2.5 text-xs font-medium transition-colors ${
            mobileView === 'list' ? 'text-blue-400' : 'text-slate-500'
          }`}
        >
          <List className="w-4 h-4" />
          Ports
        </button>
        <button
          type="button"
          onClick={() => setMobileView('map')}
          className={`flex-1 flex flex-col items-center gap-0.5 py-2.5 text-xs font-medium transition-colors ${
            mobileView === 'map' ? 'text-blue-400' : 'text-slate-500'
          }`}
        >
          <Map className="w-4 h-4" />
          Map
        </button>
      </div>

      {/*
        Mobile briefing drawer overlay.
        Rendered as absolute within this `relative` container, NOT inside the
        overflow:hidden row above. This sidesteps the iOS Safari bug where
        fixed/absolute descendants of overflow:hidden containers get clipped.
      */}
      {selectedLocation && (
        <div className="md:hidden absolute inset-0 z-50">
          <BriefingDrawer
            location={selectedLocation}
            onClose={handleCloseBriefing}
          />
        </div>
      )}
    </div>
  );
}
