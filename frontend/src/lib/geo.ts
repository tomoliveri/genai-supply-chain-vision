/**
 * Computes a square AOI bounding box (~1 km per side) around a lat/lon point.
 *
 * Returns bounds in Leaflet's [[south, west], [north, east]] order
 * (i.e. [[minLat, minLon], [maxLat, maxLon]]), which maps directly to
 * Leaflet's LatLngBounds constructor.
 *
 * Longitude delta is adjusted for latitude so the box is roughly square on
 * the ground. This is a fast planar approximation — accurate for small AOIs
 * but not for polar regions.
 */
export function computeAoiBounds(
  lat: number,
  lon: number,
): [[number, number], [number, number]] {
  const latDelta = 0.009; // ~1 km
  const lonDelta = 0.009 / Math.cos((lat * Math.PI) / 180);
  return [
    [lat - latDelta, lon - lonDelta],
    [lat + latDelta, lon + lonDelta],
  ];
}
