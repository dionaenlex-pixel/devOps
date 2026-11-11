// AnimoNav front end: pick two places, ask the server for the route, draw it.

const $ = (id) => document.getElementById(id);
const fromSel = $("from"), toSel = $("to"), search = $("search");
let places = [];           // buildings from /api/locations, each with its entrances
const markers = [];        // { building id, Leaflet circle marker } for every entrance
let routeLayer = null;
let routes = [];           // the shortest route first, then other ways
let lastRequest = 0;       // only the newest route request may draw (an older one can finish later)

// ---------- Map ----------
const map = createCampusMap("map");
showBagChecks(map);

// Bigger dots on phones, so they're easy to tap with a finger
const big = window.matchMedia("(max-width: 760px)").matches ? 1 : 0;

function markerStyle(kind) {
  if (kind === "start") return { radius: 9 + big, color: "#fff", weight: 3, fillColor: "#0b6b3a", fillOpacity: 1 };
  if (kind === "end") return { radius: 9 + big, color: "#fff", weight: 3, fillColor: "#c62828", fillOpacity: 1 };
  return { radius: 6 + big, color: "#fff", weight: 2, fillColor: "#33524a", fillOpacity: 0.9 };
}

// ---------- Load locations ----------
async function loadPlaces() {
  const res = await fetch("/api/locations");
  places = await res.json();

  // Group options by category for the dropdowns
  const groups = {};
  for (const p of places) (groups[p.category] ||= []).push(p);
  for (const sel of [fromSel, toSel]) {
    sel.innerHTML = '<option value="">Choose a place…</option>';
    for (const [category, list] of Object.entries(groups)) {
      const og = document.createElement("optgroup");
      og.label = category;
      for (const p of list) og.append(new Option(p.name, p.id));
      sel.append(og);
    }
  }
  $("places").innerHTML = places.map((p) => `<option value="${escapeHtml(p.name)}"></option>`).join("");

  // One pin per entrance; tapping any of them picks the whole building
  for (const p of places) {
    for (const e of p.entrances) {
      const m = L.circleMarker(toLatLng(e.map_x, e.map_y), markerStyle()).addTo(map);
      m.bindTooltip(e.name);
      m.on("click", () => {
        // First tap sets the start, the next sets the destination
        if (!fromSel.value || (fromSel.value && toSel.value)) {
          fromSel.value = p.id;
          toSel.value = "";
        } else {
          toSel.value = p.id;
        }
        onSelectionChange();
      });
      markers.push({ id: String(p.id), marker: m });
    }
  }

  // Start at the Main Gate by default
  if (places.some((p) => p.id === 1)) fromSel.value = 1;
  onSelectionChange();
}

function placeById(id) {
  return places.find((p) => String(p.id) === String(id));
}

function onSelectionChange() {
  for (const { id, marker } of markers) {
    const kind = id === fromSel.value ? "start" : id === toSel.value ? "end" : null;
    marker.setStyle(markerStyle(kind));
    if (kind) marker.bringToFront();
  }
  showInfo(placeById(toSel.value));
  if (fromSel.value && toSel.value) getRoute();
  else clearRoute();
}

function showInfo(p) {
  $("info").hidden = !p;
  if (!p) return;
  $("info-category").textContent = p.category;
  $("info-name").textContent = p.name;
  $("info-desc").textContent = p.description || "";
}

// ---------- Route ----------
async function getRoute() {
  const request = ++lastRequest;
  $("error").hidden = true;
  if (fromSel.value === toSel.value) {
    showError("You're already there. Pick a different destination.");
    clearRoute();
    return;
  }
  const res = await fetch(`/api/route?from=${fromSel.value}&to=${toSel.value}`);
  const data = await res.json();
  if (request !== lastRequest) return;   // the places were changed while this one was loading
  if (!res.ok) {
    showError(data.error || "Something went wrong. Try again.");
    clearRoute();
    return;
  }
  routes = [data, ...(data.alternatives || [])];
  drawRoute(0);
  map.fitBounds(routeLayer.getBounds(), { padding: [40, 40], maxZoom: 1 });
}

// Draw every route: the chosen one bold and blue, the others grey and dashed (tap one to choose it)
const ROUTE_BLUE = "#1a73e8";

function drawRoute(chosen) {
  clearRoute();
  routeLayer = L.featureGroup().addTo(map);
  routes.forEach((r, i) => {
    if (i === chosen) return;
    L.polyline(r.line.map(([x, y]) => toLatLng(x, y)),
      { color: "#4a5560", weight: 6, opacity: 0.7, dashArray: "2 10", lineCap: "round" })
      .bindTooltip(`Other way · ${Math.round(r.total_m)} m (tap to use it)`)
      .on("click", () => drawRoute(i))
      .addTo(routeLayer);
  });
  const route = routes[chosen];
  const line = route.line.map(([x, y]) => toLatLng(x, y));
  // A white outline under a bright blue line stands out on the coloured campus map,
  // and moving white dashes on top show which way to walk
  L.polyline(line, { color: "#ffffff", weight: 14 + big * 2, opacity: 1, interactive: false }).addTo(routeLayer);
  L.polyline(line, { color: ROUTE_BLUE, weight: 8 + big * 2, opacity: 1, interactive: false }).addTo(routeLayer);
  L.polyline(line, { color: "#ffffff", weight: 3, opacity: 0.9, dashArray: "1 14", lineCap: "round",
                     className: "route-flow", interactive: false }).addTo(routeLayer);
  // Name the two ends
  const label = (at, text, cls) => L.tooltip({ permanent: true, direction: "top", offset: [0, -12],
                                               className: `route-label ${cls}`, interactive: false })
    .setLatLng(at).setContent(escapeHtml(text)).addTo(routeLayer);
  label(line[0], "Start", "route-label-start");
  label(line[line.length - 1], route.to, "route-label-end");
  focusOnRoute(true);

  // One button per route, when there's more than one way
  $("route-options").hidden = routes.length < 2;
  $("route-options").innerHTML = routes.map((r, i) => `
    <button type="button" class="route-option${i === chosen ? " chosen" : ""}" data-i="${i}">
      <strong>${i === 0 ? (r.total_m <= Math.min(...routes.map((o) => o.total_m)) ? "Shortest" : "Best") : `Way ${i + 1}`} · ${Math.round(r.total_m)} m${r.bag_check ? ' <span class="tag">Bag check</span>' : ""}</strong>
      <small>${escapeHtml(r.via || "")}</small>
    </button>`).join("");
  for (const b of $("route-options").querySelectorAll("button")) {
    b.addEventListener("click", () => drawRoute(Number(b.dataset.i)));
  }

  $("total").textContent = `${Math.round(route.total_m)} m`;
  $("time").textContent = `about ${route.minutes} min walk`;
  const leave = route.leave ? `<li><span>${escapeHtml(route.leave)}</span></li>` : "";
  $("steps").innerHTML = leave + route.steps
    .map((s) => `<li><span>${escapeHtml(s.text)}</span><small>${Math.round(s.distance_m)} m</small></li>`)
    .join("") + `<li class="arrive"><span>${escapeHtml(route.arrive)}</span></li>`;
  $("result").hidden = false;
}

function clearRoute() {
  lastRequest++;   // a route still loading for the old places mustn't be drawn
  if (routeLayer) map.removeLayer(routeLayer);
  routeLayer = null;
  $("result").hidden = true;
  focusOnRoute(false);
}

// While a route is shown, fade the map and the pins that aren't the start or the
// destination, so the route is what you see first
function focusOnRoute(on) {
  if (map.campusImage) map.campusImage.setOpacity(on ? 0.55 : 1);
  for (const { id, marker } of markers) {
    const endpoint = id === fromSel.value || id === toSel.value;
    marker.setStyle({ opacity: on && !endpoint ? 0.25 : 1, fillOpacity: on && !endpoint ? 0.25 : (endpoint ? 1 : 0.9) });
    if (endpoint) marker.bringToFront();
  }
}

function showError(msg) {
  $("error").textContent = msg;
  $("error").hidden = false;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- Controls ----------
fromSel.addEventListener("change", onSelectionChange);
toSel.addEventListener("change", () => { search.value = ""; onSelectionChange(); });

search.addEventListener("change", () => {
  const q = search.value.trim().toLowerCase();
  const match = places.find((p) => p.name.toLowerCase() === q) ||
                places.find((p) => p.name.toLowerCase().includes(q));
  if (match) {
    toSel.value = match.id;
    onSelectionChange();
  } else if (q) {
    showError(`No place called "${search.value}". Try another name or pick from the list.`);
  }
});

$("swap").addEventListener("click", () => {
  [fromSel.value, toSel.value] = [toSel.value, fromSel.value];
  onSelectionChange();
});

$("route-form").addEventListener("submit", (e) => {
  e.preventDefault();
  if (!fromSel.value || !toSel.value) showError("Choose a starting point and a destination.");
  else getRoute();
});

// "Use my location": find the nearest campus location to the phone's GPS
$("locate").addEventListener("click", () => {
  const msg = $("locate-msg");
  msg.hidden = false;
  if (!navigator.geolocation) {
    msg.textContent = "This browser can't share your location. Pick your starting point from the list.";
    return;
  }
  msg.textContent = "Finding your location…";
  navigator.geolocation.getCurrentPosition(async (pos) => {
    const { latitude, longitude, accuracy } = pos.coords;
    const res = await fetch(`/api/nearest?lat=${latitude}&lon=${longitude}`);
    const data = await res.json();
    if (!data.on_campus) {
      msg.textContent = "You don't seem to be on campus. Pick your starting point from the list.";
      return;
    }
    fromSel.value = data.id;
    msg.textContent = `You're near ${data.name} (GPS accuracy about ${Math.round(accuracy)} m). Change it above if that's wrong.`;
    onSelectionChange();
  }, () => {
    msg.textContent = "Location isn't available. Allow location access, or pick your starting point from the list.";
  }, { enableHighAccuracy: true, timeout: 10000 });
});

loadPlaces().catch(() => showError("Couldn't load the campus locations. Is the server running?"));
