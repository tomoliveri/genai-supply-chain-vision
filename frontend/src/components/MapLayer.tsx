'use client';

import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { MapContainer, TileLayer, Rectangle, Tooltip, useMap, Marker } from 'react-leaflet';
import { useEffect } from 'react';
import { computeAoiBounds } from '@/lib/geo';
import { SEVERITY_COLORS } from '@/lib/severity';
import type { LocationWithBriefing } from '@/lib/types';

// Fix Leaflet's default icon URL resolution which breaks in webpack/Next.js.
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: '/leaflet/marker-icon-2x.png',
  iconUrl: '/leaflet/marker-icon.png',
  shadowUrl: '/leaflet/marker-shadow.png',
});

interface MapLayerProps {
  locations: LocationWithBriefing[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/** Fits the map to all location markers on initial mount. */
function BoundsFitter({ locations }: { locations: LocationWithBriefing[] }) {
  const map = useMap();

  useEffect(() => {
    if (locations.length === 0) return;
    const bounds = L.latLngBounds(
      locations.map((loc) => L.latLng(loc.latitude, loc.longitude)),
    );
    map.fitBounds(bounds, { padding: [60, 60] });
  // Only run on initial mount — locations array identity is stable after first load.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}

function makeCircleIcon(color: string, isSelected: boolean): L.DivIcon {
  const size = isSelected ? 18 : 14;
  const ring = isSelected
    ? `box-shadow: 0 0 0 3px ${color}55, 0 0 0 5px ${color}22;`
    : '';
  return L.divIcon({
    className: '',
    html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background-color:${color};border:2px solid white;${ring}"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

export function MapLayer({ locations, selectedId, onSelect }: MapLayerProps) {
  return (
    <MapContainer
      center={[20, 0]}
      zoom={2}
      style={{ height: '100%', width: '100%' }}
      zoomControl={true}
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        maxZoom={19}
      />

      <BoundsFitter locations={locations} />

      {locations.map((loc) => {
        const color = SEVERITY_COLORS[loc.severityScore] ?? '#64748b';
        const isSelected = selectedId === loc.id;
        const bounds = computeAoiBounds(loc.latitude, loc.longitude);
        const icon = makeCircleIcon(color, isSelected);

        return (
          <div key={loc.id}>
            <Marker
              position={[loc.latitude, loc.longitude]}
              icon={icon}
              eventHandlers={{ click: () => onSelect(loc.id) }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                {loc.location_name}
              </Tooltip>
            </Marker>

            <Rectangle
              bounds={bounds}
              pathOptions={{
                color,
                weight: 1.5,
                fillColor: color,
                fillOpacity: 0.15,
                opacity: 0.7,
              }}
              eventHandlers={{ click: () => onSelect(loc.id) }}
            />
          </div>
        );
      })}
    </MapContainer>
  );
}
