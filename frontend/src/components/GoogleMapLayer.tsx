'use client';

import { useEffect, useRef, useState } from 'react';
import { importLibrary, setOptions } from '@googlemaps/js-api-loader';
import type { LocationWithBriefing } from '@/lib/types';
import { computeAoiBounds } from '@/lib/geo';
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

interface MapOverlay {
  marker: google.maps.Marker;
  polygon: google.maps.Polygon;
}

function makeMarkerIcon(color: string, isSelected: boolean): google.maps.Symbol {
  return {
    path: google.maps.SymbolPath.CIRCLE,
    scale: isSelected ? 8 : 6,
    fillColor: color,
    fillOpacity: 1,
    strokeColor: 'white',
    strokeWeight: 2,
  };
}

function makeAoiPath(loc: LocationWithBriefing): google.maps.LatLngLiteral[] {
  const [[south, west], [north, east]] = computeAoiBounds(loc.latitude, loc.longitude);
  return [
    { lat: south, lng: west },
    { lat: north, lng: west },
    { lat: north, lng: east },
    { lat: south, lng: east },
  ];
}

export function GoogleMapLayer({ locations, selectedId, onSelect }: GoogleMapLayerProps) {
  const mapRef = useRef<google.maps.Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const overlaysRef = useRef<Map<string, MapOverlay>>(new Map());
  const onSelectRef = useRef(onSelect);
  const hasFitBoundsRef = useRef(false);
  const [mapType, setMapType] = useState<string>('roadmap');
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  // Load Maps API + create map
  useEffect(() => {
    const overlays = overlaysRef.current;
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
        mapTypeId: 'roadmap' as google.maps.MapTypeId,
        styles: DARK_STYLE,
        disableDefaultUI: true,
        zoomControl: true,
        zoomControlOptions: { position: google.maps.ControlPosition.RIGHT_BOTTOM },
        gestureHandling: 'greedy',
      });

      mapRef.current = map;
      setMapReady(true);
    });

    return () => {
      for (const overlay of overlays.values()) {
        overlay.marker.setMap(null);
        overlay.polygon.setMap(null);
      }
      overlays.clear();
    };
  }, []);

  // Update map type
  useEffect(() => {
    if (!mapRef.current) return;
    mapRef.current.setMapTypeId(mapType as google.maps.MapTypeId);
    mapRef.current.setOptions({
      styles: mapType === 'roadmap' ? DARK_STYLE : undefined,
    });
  }, [mapType]);

  // Fit bounds once, after the first non-empty Firestore payload arrives.
  useEffect(() => {
    if (!mapRef.current || !mapReady || hasFitBoundsRef.current || locations.length === 0) return;
    const bounds = new google.maps.LatLngBounds();
    let hasPoints = false;
    for (const loc of locations) {
      bounds.extend({ lat: loc.latitude, lng: loc.longitude });
      hasPoints = true;
    }
    if (hasPoints) {
      mapRef.current.fitBounds(bounds, { top: 50, right: 50, bottom: 50, left: 350 });
      hasFitBoundsRef.current = true;
    }
  }, [locations, mapReady]);

  // Sync markers without recreating every overlay on each Firestore snapshot.
  useEffect(() => {
    if (!mapRef.current || !mapReady) return;

    const activeIds = new Set<string>();
    for (const loc of locations) {
      activeIds.add(loc.id);
      const color = SEVERITY_COLORS[loc.severityScore] ?? '#64748b';
      const isSelected = selectedId === loc.id;
      const position = { lat: loc.latitude, lng: loc.longitude };
      const icon = makeMarkerIcon(color, isSelected);
      const existing = overlaysRef.current.get(loc.id);

      if (existing) {
        existing.marker.setPosition(position);
        existing.marker.setTitle(loc.location_name);
        existing.marker.setIcon(icon);
        existing.marker.setZIndex(isSelected ? 20 : 10);
        existing.polygon.setPath(makeAoiPath(loc));
        existing.polygon.setOptions({
          strokeColor: color,
          fillColor: color,
          zIndex: isSelected ? 20 : 10,
        });
        continue;
      }

      const marker = new google.maps.Marker({
        position,
        map: mapRef.current,
        title: loc.location_name,
        icon,
        zIndex: isSelected ? 20 : 10,
      });
      marker.addListener('click', () => onSelectRef.current(loc.id));

      const polygon = new google.maps.Polygon({
        paths: makeAoiPath(loc),
        strokeColor: color,
        strokeWeight: 1.5,
        strokeOpacity: 0.7,
        fillColor: color,
        fillOpacity: 0.12,
        map: mapRef.current,
        zIndex: isSelected ? 20 : 10,
      });
      polygon.addListener('click', () => onSelectRef.current(loc.id));
      overlaysRef.current.set(loc.id, { marker, polygon });
    }

    for (const [id, overlay] of overlaysRef.current) {
      if (!activeIds.has(id)) {
        overlay.marker.setMap(null);
        overlay.polygon.setMap(null);
        overlaysRef.current.delete(id);
      }
    }
  }, [locations, selectedId, mapReady]);

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
