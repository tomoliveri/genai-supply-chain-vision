import { Satellite } from 'lucide-react';
import { SidebarItem } from './SidebarItem';
import type { LocationWithBriefing } from '@/lib/types';

interface SidebarProps {
  locations: LocationWithBriefing[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function Sidebar({ locations, selectedId, onSelect }: SidebarProps) {
  return (
    <aside className="w-80 shrink-0 flex flex-col bg-slate-900 border-r border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-slate-700">
        <Satellite className="w-5 h-5 text-blue-400 shrink-0" />
        <h1 className="text-base font-semibold text-slate-50 tracking-tight">SupplyWatch</h1>
        <span className="ml-auto inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-700 text-xs font-medium text-slate-300">
          {locations.length}
        </span>
      </div>

      {/* Location list */}
      <div className="flex-1 overflow-y-auto sidebar-scroll">
        {locations.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-slate-500">
            No monitored locations yet.
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
