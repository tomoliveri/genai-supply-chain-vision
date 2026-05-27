export const SEVERITY_LABELS: Record<number, string> = {
  1: 'Normal',
  2: 'Minor',
  3: 'Moderate',
  4: 'Significant',
  5: 'Severe',
};

export const SEVERITY_COLORS: Record<number, string> = {
  1: '#22c55e',
  2: '#84cc16',
  3: '#f59e0b',
  4: '#f97316',
  5: '#ef4444',
};

export const SEVERITY_TAILWIND_BG: Record<number, string> = {
  1: 'bg-green-500',
  2: 'bg-lime-500',
  3: 'bg-amber-500',
  4: 'bg-orange-500',
  5: 'bg-red-500',
};

export const SEVERITY_TAILWIND_TEXT: Record<number, string> = {
  1: 'text-green-400',
  2: 'text-lime-400',
  3: 'text-amber-400',
  4: 'text-orange-400',
  5: 'text-red-400',
};
