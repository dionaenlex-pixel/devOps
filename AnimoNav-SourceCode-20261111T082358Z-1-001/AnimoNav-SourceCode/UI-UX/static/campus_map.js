// Shared Leaflet setup for the DLSL campus map image (used by the main page and admin tracing).
// Positions are stored as image pixels (x from the left, y from the top) on a 2000 x 1006 image.

const MAP_W = 2000, MAP_H = 1006;

// Leaflet's simple map puts y = 0 at the bottom, so flip the image's y axis
function toLatLng(x, y) { return L.latLng(MAP_H - y, x); }
function toPixel(latlng) { return [Math.round(latlng.lng), Math.round(MAP_H - latlng.lat)]; }

// Red rings where the bag checks are (from /api/bag-checks)
async function showBagChecks(map) {
  const res = await fetch("/api/bag-checks");
  if (!res.ok) return;
  for (const c of await res.json()) {
    L.circleMarker(toLatLng(c.map_x, c.map_y), {
      radius: 7, color: "#c62828", weight: 3, fill: false, interactive: true,
    }).bindTooltip(c.name[0].toUpperCase() + c.name.slice(1)).addTo(map);
  }
}

function createCampusMap(elementId) {
  const map = L.map(elementId, {
    crs: L.CRS.Simple,
    minZoom: -2,
    maxZoom: 2,
    zoomSnap: 0.25,
    attributionControl: false,
  });
  const bounds = L.latLngBounds(toLatLng(0, MAP_H), toLatLng(MAP_W, 0));
  // CAMPUS_MAP_URL (from _leaflet.html) carries a version, so an updated map isn't hidden by the cache
  // map.campusImage lets a page fade the map, e.g. so a route stands out
  map.campusImage = L.imageOverlay(typeof CAMPUS_MAP_URL === "string" ? CAMPUS_MAP_URL : "/static/campus-map.webp",
                                   bounds).addTo(map);
  map.setMaxBounds(bounds.pad(0.15));
  map.fitBounds(bounds);
  return map;
}
