export interface WatchlistItem {
  id: string;
  user_id: string;
  location_name: string;
  latitude: number;
  longitude: number;
  geofence_radius_meters: number;
  created_at: { seconds: number; nanoseconds: number } | null;
}

export interface DailyBriefing {
  id: string;
  disruption_detected: boolean;
  severity_score: number;
  confidence_grade: 'High' | 'Medium' | 'Low';
  explanation: string;
  current_image_path: string;
  baseline_image_path: string;
  location_context: string;
  analysed_at: string;
  // Phase 2 — structured metrics
  container_yard_fill_pct?: number;
  vessel_count?: number;
  vessel_count_anchorage?: number;
  disruption_category?: string;
  // Phase 3 — external context
  weather_summary?: string;
  weather_severity?: number;
  labor_status?: string;
  peak_season_flag?: boolean;
  analysis_version?: number;
  // Phase 4 — geopolitical context
  geopolitical_active_events?: string[];
  geopolitical_max_severity?: number;
  geopolitical_category?: string;
}

/** Watchlist item merged with its latest briefing, ready for display. */
export interface LocationWithBriefing extends WatchlistItem {
  latestBriefing: DailyBriefing | null;
  /** Mirrors latestBriefing.severity_score, or 0 when no briefing exists. */
  severityScore: number;
  /** All historical briefings for this location, sorted newest-first. */
  history: DailyBriefing[];
}

/** Aggregate disruption statistics for the dashboard header. */
export interface DisruptionStats {
  totalPorts: number;
  disruptedPorts: number;
  avgSeverity: number;
  byCategory: Record<string, number>;
  regionsAffected: string[];
}
