'use client';

import { useEffect, useRef, useState, useMemo } from 'react';
import {
  collection,
  onSnapshot,
  type QuerySnapshot,
  type DocumentData,
} from 'firebase/firestore';
import { db } from '@/lib/firebase';
import type { WatchlistItem, DailyBriefing, LocationWithBriefing, DisruptionStats } from '@/lib/types';

interface UseFirestoreDataResult {
  locations: LocationWithBriefing[];
  stats: DisruptionStats;
  loading: boolean;
  error: Error | null;
}

/**
 * Merges a location name parsed from a briefing's location_context back into
 * the corresponding WatchlistItem. location_context format:
 *   "{location_name} — lat {lat:.4f} lon {lon:.4f}"
 */
function parseLocationNameFromContext(context: string): string {
  return context.split(' — lat ')[0] ?? context;
}

function snapshotToWatchlistItems(snap: QuerySnapshot<DocumentData>): WatchlistItem[] {
  return snap.docs.map((doc) => {
    const data = doc.data();
    return {
      id: doc.id,
      user_id: (data['user_id'] as string) ?? '',
      location_name: (data['location_name'] as string) ?? '',
      latitude: (data['latitude'] as number) ?? 0,
      longitude: (data['longitude'] as number) ?? 0,
      geofence_radius_meters: (data['geofence_radius_meters'] as number) ?? 0,
      created_at: (data['created_at'] as WatchlistItem['created_at']) ?? null,
    };
  });
}

function snapshotToBriefings(snap: QuerySnapshot<DocumentData>): DailyBriefing[] {
  return snap.docs.map((doc) => {
    const data = doc.data();
    return {
      id: doc.id,
      disruption_detected: (data['disruption_detected'] as boolean) ?? false,
      severity_score: (data['severity_score'] as number) ?? 1,
      confidence_grade: (data['confidence_grade'] as DailyBriefing['confidence_grade']) ?? 'Low',
      explanation: (data['explanation'] as string) ?? '',
      current_image_path: (data['current_image_path'] as string) ?? '',
      baseline_image_path: (data['baseline_image_path'] as string) ?? '',
      location_context: (data['location_context'] as string) ?? '',
      analysed_at: (data['analysed_at'] as string) ?? '',
      container_yard_fill_pct: (data['container_yard_fill_pct'] as number) ?? undefined,
      vessel_count: (data['vessel_count'] as number) ?? undefined,
      vessel_count_anchorage: (data['vessel_count_anchorage'] as number) ?? undefined,
      disruption_category: (data['disruption_category'] as string) ?? undefined,
      weather_summary: (data['weather_summary'] as string) ?? undefined,
      weather_severity: (data['weather_severity'] as number) ?? undefined,
      labor_status: (data['labor_status'] as string) ?? undefined,
      peak_season_flag: (data['peak_season_flag'] as boolean) ?? undefined,
      analysis_version: (data['analysis_version'] as number) ?? undefined,
      geopolitical_active_events: (data['geopolitical_active_events'] as string[]) ?? undefined,
      geopolitical_max_severity: (data['geopolitical_max_severity'] as number) ?? undefined,
      geopolitical_category: (data['geopolitical_category'] as string) ?? undefined,
    };
  });
}

function mergeLocations(
  watchlistItems: WatchlistItem[],
  allBriefings: DailyBriefing[],
): LocationWithBriefing[] {
  const latestBriefingByName = new Map<string, DailyBriefing>();

  for (const briefing of allBriefings) {
    const name = parseLocationNameFromContext(briefing.location_context);
    const existing = latestBriefingByName.get(name);
    if (!existing || briefing.analysed_at > existing.analysed_at) {
      latestBriefingByName.set(name, briefing);
    }
  }

  const merged: LocationWithBriefing[] = watchlistItems.map((item) => {
    const latestBriefing = latestBriefingByName.get(item.location_name) ?? null;
    const history = allBriefings
      .filter((b) => parseLocationNameFromContext(b.location_context) === item.location_name)
      .sort((a, b) => b.analysed_at.localeCompare(a.analysed_at));
    return {
      ...item,
      latestBriefing,
      severityScore: latestBriefing?.severity_score ?? 0,
      history,
    };
  });

  merged.sort((a, b) => {
    if (b.severityScore !== a.severityScore) return b.severityScore - a.severityScore;
    return a.location_name.localeCompare(b.location_name);
  });

  return merged;
}

function computeStats(locations: LocationWithBriefing[]): DisruptionStats {
  const totalPorts = locations.length;
  const disruptedPorts = locations.filter(
    (l) => l.latestBriefing?.disruption_detected
  ).length;
  const avgSeverity = totalPorts > 0
    ? Math.round(
        (locations.reduce((sum, l) => sum + l.severityScore, 0) / totalPorts) * 10
      ) / 10
    : 0;

  const byCategory: Record<string, number> = {};
  const regionsAffected: Set<string> = new Set();

  for (const loc of locations) {
    const cat = loc.latestBriefing?.disruption_category ?? 'none';
    byCategory[cat] = (byCategory[cat] || 0) + 1;

    if (loc.latestBriefing?.geopolitical_category && loc.latestBriefing.geopolitical_category !== 'none') {
      regionsAffected.add(loc.latestBriefing.geopolitical_category);
    }
  }

  return { totalPorts, disruptedPorts, avgSeverity, byCategory, regionsAffected: [...regionsAffected] };
}

/**
 * Subscribes to `watchlist_items` and `daily_briefings` collections in
 * real time, merging them so each location carries its latest briefing.
 *
 * Also computes aggregate disruption statistics for the dashboard header.
 *
 * Returns empty data (no crash) when Firebase is not configured.
 */
export function useFirestoreData(): UseFirestoreDataResult {
  const [locations, setLocations] = useState<LocationWithBriefing[]>([]);
  const [loading, setLoading] = useState<boolean>(db !== null);
  const [error, setError] = useState<Error | null>(null);

  const watchlistRef = useRef<WatchlistItem[]>([]);
  const briefingsRef = useRef<DailyBriefing[]>([]);
  const watchlistReadyRef = useRef(false);
  const briefingsReadyRef = useRef(false);

  const stats = useMemo(() => computeStats(locations), [locations]);

  useEffect(() => {
    if (!db) return;

    function handleUpdate(): void {
      if (watchlistReadyRef.current && briefingsReadyRef.current) {
        setLocations(mergeLocations(watchlistRef.current, briefingsRef.current));
        setLoading(false);
      }
    }

    const unsubscribeWatchlist = onSnapshot(
      collection(db, 'watchlist_items'),
      (snap) => {
        watchlistRef.current = snapshotToWatchlistItems(snap);
        watchlistReadyRef.current = true;
        handleUpdate();
      },
      (err) => {
        setError(err);
        setLoading(false);
      },
    );

    const unsubscribeBriefings = onSnapshot(
      collection(db, 'daily_briefings'),
      (snap) => {
        briefingsRef.current = snapshotToBriefings(snap);
        briefingsReadyRef.current = true;
        handleUpdate();
      },
      (err) => {
        setError(err);
        setLoading(false);
      },
    );

    return () => {
      unsubscribeWatchlist();
      unsubscribeBriefings();
    };
  }, []);

  return { locations, stats, loading, error };
}
