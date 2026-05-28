'use client';

import { Search, Satellite, X } from 'lucide-react';
import { SidebarItem } from './SidebarItem';
import type { LocationWithBriefing, DisruptionStats } from '@/lib/types';

interface SidebarProps {
  locations: LocationWithBriefing[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  stats: DisruptionStats;
}

export function Sidebar({
  locations,
  selectedId,
  onSelect,
  searchQuery,
  onSearchChange,
  stats,
}: SidebarProps) {
  return (
    <aside className="w-80 shrink-0 flex flex-col bg-slate-900 border-r border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-slate-700">
        <Satellite className="w-5 h-5 text-blue-400 shrink-0" />
        <h1 className="text-base font-semibold text-slate-50 tracking-tight">SupplyWatch</h1>
        <span className="ml-auto inline-flex items-center justify-center min-w-[1.25rem] h-5 rounded-full bg-slate-700 text-xs font-medium text-slate-300 px-1.5">
          {locations.length}
        </span>
      </div>

      {/* Search bar */}
      <div className="px-3 py-2.5 border-b border-slate-700">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search ports…"
            className="w-full bg-slate-800 text-sm text-slate-200 placeholder-slate-500 rounded-lg pl-8 pr-7 py-1.5 border border-slate-700 focus:border-blue-500 focus:outline-none transition-colors"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => onSearchChange('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Quick stats row */}
      {stats.totalPorts > 0 && (
        <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700/50 text-[10px] text-slate-500 uppercase tracking-wider">
          <span>
            {stats.disruptedPorts}/{stats.totalPorts} disrupted
          </span>
          <span>
            Avg severity {stats.avgSeverity}
          </span>
        </div>
      )}

      {/* Location list */}
      <div className="flex-1 overflow-y-auto sidebar-scroll">
        {locations.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-slate-500">
            {searchQuery ? 'No ports match your search.' : 'No monitored locations yet.'}
          </div>
        ) : (
          locations.map((loc) => (
            <SidebarItem
              key={loc.id}
              location={loc}
              isSelected={selectedId === loc.id}
              onClick={() => onSelect(loc.id)}
            />
          ))
        )}
      </div>
    </aside>
  );
}
