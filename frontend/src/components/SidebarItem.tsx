import { AlertTriangle } from 'lucide-react';
import { SeverityBadge } from './SeverityBadge';
import { SEVERITY_COLORS } from '@/lib/severity';
import type { LocationWithBriefing } from '@/lib/types';

interface SidebarItemProps {
  location: LocationWithBriefing;
  isSelected: boolean;
  onClick: () => void;
}

function formatTimestamp(iso: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function confidenceBadgeClass(grade: string): string {
  if (grade === 'High') return 'text-blue-400';
  if (grade === 'Medium') return 'text-amber-400';
  return 'text-slate-400';
}

export function SidebarItem({ location, isSelected, onClick }: SidebarItemProps) {
  const briefing = location.latestBriefing;
  const severityColor = SEVERITY_COLORS[location.severityScore] ?? '#64748b';

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left flex items-stretch border-b border-slate-800 transition-colors ${
        isSelected ? 'bg-slate-800' : 'bg-slate-900 hover:bg-slate-800'
      }`}
    >
      {/* Left severity color strip */}
      <div
        className="w-1 shrink-0 rounded-l"
        style={{ backgroundColor: severityColor }}
      />

      <div className="flex-1 px-3 py-3 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <span className="text-sm font-medium text-slate-50 truncate">
            {location.location_name}
          </span>
          {briefing?.disruption_detected && (
            <AlertTriangle className="shrink-0 w-3.5 h-3.5 text-amber-400" />
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {location.severityScore > 0 && (
            <SeverityBadge score={location.severityScore} size="sm" />
          )}
          {briefing && (
            <span
              className={`text-xs font-medium ${confidenceBadgeClass(briefing.confidence_grade)}`}
            >
              {briefing.confidence_grade} confidence
            </span>
          )}
        </div>

        <p className="mt-1.5 text-xs text-slate-500">
          {briefing ? formatTimestamp(briefing.analysed_at) : 'No analysis yet'}
        </p>
      </div>
    </button>
  );
}
