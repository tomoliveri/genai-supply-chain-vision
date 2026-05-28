import { AlertTriangle, Anchor, BarChart3 } from 'lucide-react';
import type { DisruptionStats } from '@/lib/types';

interface StatsHeaderProps {
  stats: DisruptionStats;
}

const CATEGORY_COLORS: Record<string, string> = {
  armed_conflict: 'text-red-400 bg-red-900/40',
  security_incident: 'text-orange-400 bg-orange-900/40',
  legal_regulatory: 'text-purple-400 bg-purple-900/40',
  congestion: 'text-amber-400 bg-amber-900/40',
  weather: 'text-cyan-400 bg-cyan-900/40',
  labor: 'text-yellow-400 bg-yellow-900/40',
  route_disruption: 'text-pink-400 bg-pink-900/40',
  trade_policy: 'text-blue-400 bg-blue-900/40',
};

export function StatsHeader({ stats }: StatsHeaderProps) {
  const disruptionPct = stats.totalPorts > 0
    ? Math.round((stats.disruptedPorts / stats.totalPorts) * 100)
    : 0;

  return (
    <div className="shrink-0 flex items-center gap-4 px-4 py-2.5 bg-slate-900/90 backdrop-blur border-b border-slate-700/50">
      {/* Ports monitored */}
      <div className="flex items-center gap-1.5 text-xs text-slate-400">
        <Anchor className="w-3 h-3" />
        <span className="font-semibold text-slate-200">{stats.totalPorts}</span>
        <span>ports</span>
      </div>

      {/* Disruption count */}
      <div className="flex items-center gap-1.5 text-xs">
        <AlertTriangle className={`w-3 h-3 ${stats.disruptedPorts > 0 ? 'text-amber-400' : 'text-green-400'}`} />
        <span className={`font-semibold ${stats.disruptedPorts > 0 ? 'text-amber-400' : 'text-green-400'}`}>
          {stats.disruptedPorts}
        </span>
        <span className="text-slate-400">disrupted ({disruptionPct}%)</span>
      </div>

      {/* Average severity */}
      <div className="flex items-center gap-1.5 text-xs text-slate-400">
        <BarChart3 className="w-3 h-3" />
        <span className="font-semibold text-slate-200">{stats.avgSeverity}</span>
        <span>avg severity</span>
      </div>

      {/* Category pills */}
      <div className="flex items-center gap-1 ml-auto flex-wrap">
        {Object.entries(stats.byCategory)
          .filter(([cat]) => cat !== 'none')
          .sort(([, a], [, b]) => b - a)
          .slice(0, 5)
          .map(([category, count]) => {
            const colors = CATEGORY_COLORS[category] ?? 'text-slate-400 bg-slate-800';
            return (
              <span
                key={category}
                className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[10px] font-medium ${colors}`}
              >
                {category.replace(/_/g, ' ')}
                <span className="opacity-70">({count})</span>
              </span>
            );
          })}
      </div>
    </div>
  );
}
