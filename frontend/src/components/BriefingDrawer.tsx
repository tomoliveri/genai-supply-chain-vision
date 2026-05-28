'use client';

import {
  X,
  AlertTriangle,
  CheckCircle,
  Satellite,
  ChevronDown,
  ChevronUp,
  Info,
  CalendarDays,
} from 'lucide-react';
import { useState } from 'react';
import { SeverityBadge } from './SeverityBadge';
import { ImageComparison } from './ImageComparison';
import { SEVERITY_COLORS, SEVERITY_LABELS } from '@/lib/severity';
import type { LocationWithBriefing, DailyBriefing } from '@/lib/types';

interface BriefingDrawerProps {
  location: LocationWithBriefing;
  onClose: () => void;
}

function formatTimestamp(iso: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      dateStyle: 'medium',
      timeStyle: 'short',
      hour12: false,
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function formatDateShort(iso: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(iso));
  } catch {
    return iso.slice(0, 10);
  }
}

function confidenceBgClass(grade: string): string {
  if (grade === 'High') return 'bg-blue-500';
  if (grade === 'Medium') return 'bg-amber-500';
  return 'bg-slate-500';
}

const CATEGORY_META: Record<string, { label: string; description: string }> = {
  none: {
    label: 'Normal',
    description: 'No material operational disruption in the latest briefing.',
  },
  weather: {
    label: 'Weather',
    description: 'Storms, fog, swell, wind, flooding, or other weather that slows port work.',
  },
  labor: {
    label: 'Labor Strike',
    description: 'Strikes, stoppages, overtime bans, or other industrial action affecting throughput.',
  },
  congestion: {
    label: 'Congestion',
    description: 'Backlog from vessel queues, berth delays, equipment constraints, or dwell-time growth.',
  },
  vessel_shift: {
    label: 'Vessel Shift',
    description: 'A material change in vessel mix, berth occupancy, or anchorage pattern suggesting diversions, delays, or reallocated vessel flow.',
  },
  yard_overflow: {
    label: 'Yard Overflow',
    description: 'Container or storage areas are near capacity, slowing loading, unloading, and inland clearance.',
  },
  incident: {
    label: 'Security/Incident',
    description: 'Security events, infrastructure damage, legal closures, accidents, or conflict affecting operations.',
  },
  other: {
    label: 'Other',
    description: 'A disruption that does not fit the standard categories.',
  },
};

function categoryColorClass(cat: string): string {
  const map: Record<string, string> = {
    none: 'bg-slate-600',
    weather: 'bg-cyan-600',
    labor: 'bg-yellow-600',
    congestion: 'bg-amber-600',
    vessel_shift: 'bg-blue-600',
    yard_overflow: 'bg-orange-600',
    incident: 'bg-red-600',
    other: 'bg-purple-600',
  };
  return map[cat] ?? 'bg-slate-600';
}

function categoryLabel(cat: string): string {
  return CATEGORY_META[cat]?.label ?? cat.replace(/_/g, ' ');
}

type HistoryRow =
  | { kind: 'briefing'; key: string; entries: [DailyBriefing] }
  | { kind: 'clear-run'; key: string; entries: DailyBriefing[] };

function buildHistoryRows(history: DailyBriefing[]): HistoryRow[] {
  const rows: HistoryRow[] = [];
  let clearRun: DailyBriefing[] = [];

  function flushClearRun(): void {
    if (clearRun.length === 0) return;
    rows.push({
      kind: 'clear-run',
      key: `clear-${clearRun[clearRun.length - 1].id}-${clearRun[0].id}`,
      entries: clearRun,
    });
    clearRun = [];
  }

  for (const item of history) {
    if (!item.disruption_detected) {
      clearRun.push(item);
      continue;
    }
    flushClearRun();
    rows.push({ kind: 'briefing', key: item.id, entries: [item] });
  }

  flushClearRun();
  return rows;
}

function formatDateRange(entries: DailyBriefing[]): string {
  const sorted = [...entries].sort((a, b) => a.analysed_at.localeCompare(b.analysed_at));
  const first = formatDateShort(sorted[0].analysed_at);
  const last = formatDateShort(sorted[sorted.length - 1].analysed_at);
  return first === last ? first : `${first} - ${last}`;
}

/** Mini severity timeline chart — shows severity scores over time as colored bars. */
function SeverityTimeline({ history }: { history: DailyBriefing[] }) {
  if (history.length < 2) return null;

  const sorted = [...history].sort((a, b) => a.analysed_at.localeCompare(b.analysed_at));

  return (
    <div>
      <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
        Daily Severity
      </p>
      <p className="mb-2 text-xs text-slate-500">
        Each bar is one pipeline run. Repeated green bars mean consecutive clear daily briefings, not separate incidents.
      </p>
      <div className="flex items-end gap-1 h-16">
        {sorted.map((h) => {
          const heightPct = (h.severity_score / 5) * 100;
          const color = SEVERITY_COLORS[h.severity_score] ?? '#64748b';
          return (
            <div
              key={h.id}
              className="flex-1 min-w-[8px] rounded-t cursor-default group relative"
              style={{ height: `${Math.max(heightPct, 8)}%`, backgroundColor: color }}
              title={`${formatDateShort(h.analysed_at)}: Sev ${h.severity_score} — ${h.disruption_detected ? 'Disrupted' : 'Clear'}`}
            >
              {/* Tooltip on hover */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-20 pointer-events-none">
                <span className="inline-block bg-slate-800 text-xs text-slate-200 rounded px-2 py-1 whitespace-nowrap border border-slate-600 shadow-lg">
                  {formatDateShort(h.analysed_at)} — Sev {h.severity_score}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex justify-between mt-1 text-[10px] text-slate-600">
        <span>{formatDateShort(sorted[0].analysed_at)}</span>
        <span>{formatDateShort(sorted[sorted.length - 1].analysed_at)}</span>
      </div>
    </div>
  );
}

export function BriefingDrawer({ location, onClose }: BriefingDrawerProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [typeGuideOpen, setTypeGuideOpen] = useState(false);
  const briefing = location.history.find((h) => h.id === selectedId) ?? location.latestBriefing;
  const severityColor = SEVERITY_COLORS[location.severityScore] ?? '#64748b';
  const severityLabel = SEVERITY_LABELS[location.severityScore] ?? 'Unknown';
  const historyRows = buildHistoryRows(location.history);
  const visibleHistoryRows = showAllHistory ? historyRows : historyRows.slice(0, 6);

  return (
    <aside
      className="h-full w-full flex flex-col bg-slate-900 border-l border-slate-700 overflow-hidden animate-slide-in"
      aria-label="Location briefing"
    >
      {/* Header */}
      <div className="flex items-start gap-3 px-5 py-4 border-b border-slate-700">
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-semibold text-slate-50 truncate">
            {location.location_name}
          </h2>
          <p className="mt-0.5 text-xs font-mono text-slate-400">
            {location.latitude.toFixed(4)}, {location.longitude.toFixed(4)}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 p-1.5 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          aria-label="Close briefing"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto sidebar-scroll px-5 py-4 space-y-5">
        {briefing ? (
          <>
            {/* Severity meter */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                  Severity
                </span>
                <SeverityBadge score={briefing.severity_score} />
              </div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${(briefing.severity_score / 5) * 100}%`,
                    backgroundColor: severityColor,
                  }}
                />
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {briefing.severity_score}/5 — {severityLabel}
              </p>
            </div>

            {/* Confidence + Category */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Confidence
              </span>
              <span
                className={`text-xs font-semibold text-white px-2 py-0.5 rounded-full ${confidenceBgClass(briefing.confidence_grade)}`}
              >
                {briefing.confidence_grade}
              </span>

              {briefing.disruption_category && briefing.disruption_category !== 'none' && (
                <>
                  <span className="text-xs text-slate-600">·</span>
                  <span
                    className={`text-xs font-semibold text-white px-2 py-0.5 rounded-full ${categoryColorClass(briefing.disruption_category)}`}
                  >
                    {categoryLabel(briefing.disruption_category)}
                  </span>
                </>
              )}
            </div>

            {/* Disruption type guide */}
            <div>
              <button
                onClick={() => setTypeGuideOpen(o => !o)}
                className="flex w-full items-center justify-between text-xs font-medium text-slate-400 uppercase tracking-wider"
              >
                <span className="flex items-center gap-1.5">
                  <Info className="w-3.5 h-3.5" />
                  Type Guide
                </span>
                {typeGuideOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
              {typeGuideOpen && (
                <div className="grid gap-2 mt-2">
                  {Object.entries(CATEGORY_META)
                    .filter(([key]) => key !== 'none')
                    .map(([key, meta]) => (
                      <div key={key} className="rounded-md border border-slate-800 bg-slate-950/60 p-2.5">
                        <div className="flex items-center gap-2">
                          <span className={`h-2 w-2 rounded-full ${categoryColorClass(key)}`} />
                          <span className="text-xs font-semibold text-slate-200">{meta.label}</span>
                        </div>
                        <p className="mt-1 text-xs leading-relaxed text-slate-500">
                          {meta.description}
                        </p>
                      </div>
                    ))}
                </div>
              )}
            </div>

            {/* Disruption status */}
            <div className="flex items-center gap-2">
              {briefing.disruption_detected ? (
                <>
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span className="text-sm font-medium text-amber-400">
                    Disruption detected
                  </span>
                </>
              ) : (
                <>
                  <CheckCircle className="w-4 h-4 text-green-400" />
                  <span className="text-sm font-medium text-green-400">
                    No disruption detected
                  </span>
                </>
              )}
            </div>

            {/* Container metrics */}
            {(briefing.container_yard_fill_pct !== undefined || briefing.vessel_count !== undefined) && (
              <div>
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Operations
                </p>
                <div className="grid grid-cols-3 gap-2">
                  {briefing.container_yard_fill_pct !== undefined && (
                    <div className="bg-slate-800 rounded-lg p-2 text-center">
                      <div className="text-lg font-bold text-slate-200">
                        {briefing.container_yard_fill_pct}%
                      </div>
                      <div className="text-[10px] text-slate-500">Yard fill</div>
                    </div>
                  )}
                  {briefing.vessel_count !== undefined && (
                    <div className="bg-slate-800 rounded-lg p-2 text-center">
                      <div className="text-lg font-bold text-slate-200">
                        {briefing.vessel_count}
                      </div>
                      <div className="text-[10px] text-slate-500">At berth</div>
                    </div>
                  )}
                  {briefing.vessel_count_anchorage !== undefined && (
                    <div className="bg-slate-800 rounded-lg p-2 text-center">
                      <div className="text-lg font-bold text-slate-200">
                        {briefing.vessel_count_anchorage}
                      </div>
                      <div className="text-[10px] text-slate-500">Anchorage</div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Geopolitical context */}
            {briefing.geopolitical_active_events && briefing.geopolitical_active_events.length > 0 && (
              <div>
                <p className="text-xs font-medium text-amber-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  Geopolitical Risk
                  {briefing.geopolitical_max_severity && briefing.geopolitical_max_severity >= 4 && (
                    <span className="text-red-400">⚠ High</span>
                  )}
                </p>
                <div className="bg-red-900/20 border border-red-800/30 rounded-lg p-3 space-y-1.5">
                  {briefing.geopolitical_category && briefing.geopolitical_category !== 'none' && (
                    <p className="text-xs text-red-300 font-medium">
                      {briefing.geopolitical_category.replace(/\+/g, ' · ').replace(/_/g, ' ')}
                    </p>
                  )}
                  {briefing.geopolitical_active_events.map((event, i) => (
                    <p key={i} className="text-xs text-slate-300 leading-relaxed">
                      • {event}
                    </p>
                  ))}
                </div>
              </div>
            )}

            {/* External context badges */}
            {(briefing.weather_summary || briefing.labor_status || briefing.peak_season_flag) && (
              <div>
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Context
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {briefing.weather_summary && (
                    <span className="inline-flex items-center gap-1 rounded bg-slate-800 px-2 py-1 text-xs text-slate-300">
                      🌤️ {briefing.weather_summary.split(' / ')[0]}
                      {briefing.weather_severity && briefing.weather_severity >= 4 && (
                        <span className="text-amber-400 ml-0.5">⚠️</span>
                      )}
                    </span>
                  )}
                  {briefing.labor_status && briefing.labor_status !== 'Normal' && (
                    <span className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium ${
                      briefing.labor_status === 'Strike active'
                        ? 'bg-red-900/60 text-red-300'
                        : 'bg-amber-900/60 text-amber-300'
                    }`}>
                      ⚠️ {briefing.labor_status}
                    </span>
                  )}
                  {briefing.peak_season_flag && (
                    <span className="inline-flex items-center gap-1 rounded bg-blue-900/60 px-2 py-1 text-xs text-blue-300">
                      📦 Peak season
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Explanation */}
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                Analysis
              </p>
              <div className="bg-slate-800 rounded-lg p-4 text-sm text-slate-300 leading-relaxed">
                {briefing.explanation}
              </div>
            </div>

            {/* Satellite imagery */}
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                Satellite Imagery
              </p>
              <ImageComparison
                baselineUri={briefing.baseline_image_path}
                currentUri={briefing.current_image_path}
              />
            </div>

            {/* Timestamp */}
            <p className="text-xs text-slate-500">
              Analysed {formatTimestamp(briefing.analysed_at)}
              {briefing.analysis_version !== undefined && (
                <span className="ml-2 text-slate-600">v{briefing.analysis_version}</span>
              )}
            </p>

            {/* Severity timeline chart */}
            <SeverityTimeline history={location.history} />

            {/* Historical briefing list */}
            {location.history.length > 1 && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                    History ({location.history.length})
                  </p>
                  {historyRows.length > 6 && (
                    <button
                      type="button"
                      onClick={() => setShowAllHistory(!showAllHistory)}
                      className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-0.5"
                    >
                      {showAllHistory ? (
                        <>Show less <ChevronUp className="w-3 h-3" /></>
                      ) : (
                        <>Show all ({historyRows.length}) <ChevronDown className="w-3 h-3" /></>
                      )}
                    </button>
                  )}
                </div>
                <div className="max-h-48 overflow-y-auto sidebar-scroll space-y-1">
                  {visibleHistoryRows.map((row) => {
                    const h = row.entries[0];
                    const isActive = row.entries.some((entry) => entry.id === briefing.id);
                    const clearRunCount = row.kind === 'clear-run' ? row.entries.length : 0;

                    return (
                      <button
                        key={row.key}
                        type="button"
                        onClick={() => setSelectedId(isActive ? null : h.id)}
                        className={`w-full text-left rounded px-2.5 py-2 text-xs transition-colors ${
                          isActive
                            ? 'bg-slate-700 border-l-2 border-blue-400'
                            : 'border-l-2 border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-300'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="inline-flex items-center gap-1.5 font-mono text-slate-300">
                            <CalendarDays className="h-3 w-3 text-slate-500" />
                            {formatDateRange(row.entries)}
                          </span>
                          <span className="flex items-center gap-1.5">
                            {row.kind === 'clear-run' ? (
                              <span className="text-green-400">
                                Clear{clearRunCount > 1 ? ` x${clearRunCount}` : ''}
                              </span>
                            ) : h.disruption_detected ? (
                              <span className="text-amber-400">⚠ Sev {h.severity_score}</span>
                            ) : (
                              <span className="text-green-400">✓ Clear</span>
                            )}
                            {h.disruption_category && h.disruption_category !== 'none' && (
                              <span className={`text-[10px] text-white px-1.5 py-0.5 rounded-full ${categoryColorClass(h.disruption_category)}`}>
                                {categoryLabel(h.disruption_category)}
                              </span>
                            )}
                          </span>
                        </div>
                        {row.kind === 'clear-run' && clearRunCount > 1 && (
                          <p className="mt-1.5 text-slate-500 leading-relaxed">
                            {clearRunCount} consecutive daily analyses with no disruption detected.
                          </p>
                        )}
                        {isActive && h.explanation && (
                          <p className="mt-1.5 text-slate-400 leading-relaxed line-clamp-2">
                            {h.explanation}
                          </p>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
            <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center">
              <Satellite className="w-6 h-6 text-slate-600" />
            </div>
            <p className="text-sm text-slate-400 font-medium">No analysis available yet</p>
            <p className="text-xs text-slate-600 max-w-[200px]">
              Gemini analysis will appear here once the location has been processed.
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}
