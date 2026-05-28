'use client';

import { useEffect, useRef, useState } from 'react';
import { importLibrary, setOptions } from '@googlemaps/js-api-loader';
import type { LocationWithBriefing } from '@/lib/types';
import { SEVERITY_COLORS } from '@/lib/severity';

interface GoogleMapLayerProps {
  locations: LocationWithBriefing[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const DARK_STYLE: google.maps.MapTypeStyle[] = [
  { elementType: 'geometry', stylers: [{ color: '#0f172a' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#0f172a' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#94a3b8' }] },
  { featureType: 'administrative.country', elementType: 'geometry.stroke', stylers: [{ color: '#334155' }] },
  { featureType: 'administrative.locality', elementType: 'labels.text.fill', stylers: [{ color: '#cbd5e1' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#1e293b' }] },
  { featureType: 'road.arterial', elementType: 'geometry', stylers: [{ color: '#334155' }] },
  { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#475569' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#020617' }] },
  { featureType: 'transit', elementType: 'geometry', stylers: [{ color: '#1e293b' }] },
];

const MAP_TYPE_LABELS: Record<string, string> = {
  roadmap: 'Road',
  satellite: 'Satellite',
  hybrid: 'Hybrid',
};

export function GoogleMapLayer({ locations, selectedId, onSelect }: GoogleMapLayerProps) {
  const mapRef = useRef<google.maps.Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const polygonsRef = useRef<google.maps.Polygon[]>([]);
  const [mapType, setMapType] = useState<string>('roadmap');
  const [mapReady, setMapReady] = useState(false);

  // Load Maps API + create map
  useEffect(() => {
    setOptions({ key: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? '' });
    importLibrary('maps' as never).then(() => {
      if (!containerRef.current) return;

      const map = new google.maps.Map(containerRef.current, {
        center: { lat: 20, lng: 0 },
        zoom: 3,
        minZoom: 2,
        restriction: {
          latLngBounds: { north: 85, south: -85, west: -180, east: 180 },
          strictBounds: true,
        },
        mapTypeId: mapType as google.maps.MapTypeId,
        styles: mapType === 'roadmap' ? DARK_STYLE : undefined,
        disableDefaultUI: true,
        zoomControl: true,
        zoomControlOptions: { position: google.maps.ControlPosition.RIGHT_BOTTOM },
        gestureHandling: 'greedy',
      });

      mapRef.current = map;
      setMapReady(true);
    });
  }, []);

  // Update map type
  useEffect(() => {
    if (!mapRef.current) return;
    mapRef.current.setMapTypeId(mapType as google.maps.MapTypeId);
    mapRef.current.setOptions({
      styles: mapType === 'roadmap' ? DARK_STYLE : undefined,
    });
  }, [mapType]);

  // Fit bounds on first load
  useEffect(() => {
    if (!mapRef.current || !mapReady || locations.length === 0) return;
    const bounds = new google.maps.LatLngBounds();
    let hasPoints = false;
    for (const loc of locations) {
      bounds.extend({ lat: loc.latitude, lng: loc.longitude });
      hasPoints = true;
    }
    if (hasPoints) {
      mapRef.current.fitBounds(bounds, { top: 50, right: 50, bottom: 50, left: 350 });
    }
  }, [mapReady]);

  // Sync markers
  useEffect(() => {
    if (!mapRef.current) return;

    // Clear old
    for (const m of markersRef.current) m.setMap(null);
    for (const p of polygonsRef.current) p.setMap(null);
    markersRef.current = [];
    polygonsRef.current = [];

    for (const loc of locations) {
      const color = SEVERITY_COLORS[loc.severityScore] ?? '#64748b';
      const isSelected = selectedId === loc.id;

      // Marker
      const marker = new google.maps.Marker({
        position: { lat: loc.latitude, lng: loc.longitude },
        map: mapRef.current,
        title: loc.location_name,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: isSelected ? 8 : 6,
          fillColor: color,
          fillOpacity: 1,
          strokeColor: 'white',
          strokeWeight: 2,
        },
      });
      marker.addListener('click', () => onSelect(loc.id));
      markersRef.current.push(marker);

      // AOI rectangle
      const latDelta = 0.009;
      const lonDelta = 0.009 / Math.cos((loc.latitude * Math.PI) / 180);
      const polygon = new google.maps.Polygon({
        paths: [
          { lat: loc.latitude - latDelta, lng: loc.longitude - lonDelta },
          { lat: loc.latitude + latDelta, lng: loc.longitude - lonDelta },
          { lat: loc.latitude + latDelta, lng: loc.longitude + lonDelta },
          { lat: loc.latitude - latDelta, lng: loc.longitude + lonDelta },
        ],
        strokeColor: color,
        strokeWeight: 1.5,
        strokeOpacity: 0.7,
        fillColor: color,
        fillOpacity: 0.12,
        map: mapRef.current,
      });
      polygon.addListener('click', () => onSelect(loc.id));
      polygonsRef.current.push(polygon);
    }
  }, [locations, selectedId, mapReady, onSelect]);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Map type toggle */}
      <div className="absolute top-12 left-2.5 z-10 flex flex-col gap-0.5">
        {(['roadmap', 'satellite', 'hybrid'] as const).map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => setMapType(type)}
            className={`text-xs font-medium px-2.5 py-1 rounded transition-colors ${
              mapType === type
                ? 'bg-white text-slate-900 shadow'
                : 'bg-slate-900/80 text-slate-300 hover:bg-slate-800 backdrop-blur'
            }`}
          >
            {MAP_TYPE_LABELS[type]}
          </button>
        ))}
      </div>
    </div>
  );
}
