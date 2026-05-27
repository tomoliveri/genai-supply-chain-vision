import { SEVERITY_LABELS, SEVERITY_TAILWIND_BG } from '@/lib/severity';

interface SeverityBadgeProps {
  score: number;
  size?: 'sm' | 'md';
}

export function SeverityBadge({ score, size = 'md' }: SeverityBadgeProps) {
  const label = SEVERITY_LABELS[score] ?? 'Unknown';
  const bgClass = SEVERITY_TAILWIND_BG[score] ?? 'bg-slate-500';
  const sizeClass =
    size === 'sm' ? 'text-xs px-1.5 py-0.5' : 'text-xs font-semibold px-2 py-0.5';

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-semibold text-white ${bgClass} ${sizeClass}`}
    >
      <span className="tabular-nums">{score}</span>
      <span>{label}</span>
    </span>
  );
}
