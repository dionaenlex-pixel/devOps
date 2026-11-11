// Admin "Fix a route": show the route between two places, click the part that's
// wrong, and fix its line right on the map (drag, add or remove points), then save.

const $ = (id) => document.getElementById(id);
const map = createCampusMap("map");
map.doubleClickZoom.disable();   // double-click removes a point here
const nodeById = Object.fromEntries(ROUTE_NODES.map((n) => [n.id, n]));
const edgeById = Object.fromEntries(ROUTE_EDGES.map((e) => [e.id, e]));
const routeLayer = L.layerGroup().addTo(map);
const editLayer = L.layerGroup().addTo(map);

let ways = [];        // the route and its other ways, from /api/route
let shown = 0;        // which of them is on the map
let editing = null;   // { step, edge, points, history } while a part is being fixed

// ---------- Places ----------
async function loadPlaces() {
  const res = await fetch("/api/locations");
  if (!res.ok) return showMsg("Couldn't load the places. Reload the page.", true);
  const places = await res.json();
  for (const sel of [$("from"), $("to")]) {
    sel.innerHTML = '<option value="">Choose a place…</option>';
    for (const p of places) sel.append(new Option(p.name, p.id));
  }
}

// ---------- The route ----------
// A pathway's line in map pixels, from its start pin to its end pin
function lineOf(edge, points) {
  const a = nodeById[edge.from_node], b = nodeById[edge.to_node];
  return [[a.map_x, a.map_y], ...points, [b.map_x, b.map_y]];
}

async function showRoute(keepWay) {
  const from = $("from").value, to = $("to").value;
  if (!from || !to) return showMsg("Choose a starting point and a destination.", true);
  if (from === to) return showMsg("Pick two different places.", true);
  const res = await fetch(`/api/route?from=${from}&to=${to}&parts=1`);   // one step per pathway
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return showMsg(data.error || "Couldn't find a route.", true);
  $("msg").hidden = true;
  ways = [data, ...(data.alternatives || [])];
  if (!keepWay || shown >= ways.length) shown = 0;
  drawRoute(!keepWay);
}

function drawRoute(zoom) {
  const way = ways[shown];
  routeLayer.clearLayers();
  const all = [];
  way.steps.forEach((s, i) => {
    const edge = edgeById[s.edge_id];
    const line = lineOf(edge, edge.waypoints).map(([x, y]) => toLatLng(x, y));
    all.push(...line);
    const isEdited = editing && editing.step === i;
    if (isEdited) return;   // the editor draws this part
    // Every other part a slightly different green, so the parts are easy to tell apart
    L.polyline(line, { color: i % 2 ? "#2e9d5b" : "#0b6b3a", weight: 7, opacity: 0.8,
                       interactive: !editing })
      .bindTooltip(`Step ${i + 1}: click to fix this part`)
      .on("click", (ev) => { L.DomEvent.stopPropagation(ev); startEdit(i); })
      .addTo(routeLayer);
    const mid = line[Math.floor(line.length / 2)];
    L.marker(mid, { interactive: false,
                    icon: L.divIcon({ className: "step-number", html: String(i + 1), iconSize: [22, 22] }) })
      .addTo(routeLayer);
    // Every bend can be dragged straight away: that part opens for fixing with the point moved
    edge.waypoints.forEach((p, k) => {
      const dot = L.marker(toLatLng(...p), { draggable: true,
                                             icon: L.divIcon({ className: "route-dot", iconSize: [12, 12] }) })
        .bindTooltip(`Step ${i + 1}: drag to move`).addTo(routeLayer);
      dot.on("dragend", () => {
        const moved = toPixel(dot.getLatLng());
        if (editing && editing.step !== i && unsaved()) {
          dot.setLatLng(toLatLng(...p));
          return showMsg("Save or cancel the part you're fixing first.", true);
        }
        startEdit(i, false);
        remember();
        editing.points[k] = moved;
        drawEditor();
      });
    });
  });
  drawPins(way);
  if (zoom) map.fitBounds(L.latLngBounds(all), { padding: [60, 60], maxZoom: 1 });

  // One button per way
  const box = $("ways");
  box.hidden = ways.length < 2;
  box.innerHTML = "";
  ways.forEach((w, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "route-option" + (i === shown ? " chosen" : "");
    b.append(Object.assign(document.createElement("strong"),
      { textContent: `${i === 0 ? "Shortest" : `Way ${i + 1}`} · ${Math.round(w.total_m)} m` }));
    b.append(Object.assign(document.createElement("small"), { textContent: w.via }));
    b.addEventListener("click", () => {
      if (editing) return showMsg("Save or cancel the part you're fixing first.", true);
      shown = i;
      drawRoute(true);
    });
    box.append(b);
  });

  // The steps
  $("route").hidden = false;
  $("route-summary").textContent = `${way.from} → ${way.to} · ${Math.round(way.total_m)} m`;
  const list = $("steps");
  list.innerHTML = "";
  way.steps.forEach((s, i) => {
    const li = document.createElement("li");
    li.className = editing && editing.step === i ? "editing" : "";
    li.tabIndex = 0;
    li.textContent = s.text;
    li.addEventListener("click", () => startEdit(i));
    li.addEventListener("keydown", (ev) => { if (ev.key === "Enter") startEdit(i); });
    list.append(li);
  });
}

// ---------- Pins ----------
// The places and walkway junctions the route passes. A pin is shared by every pathway
// that starts or ends there, so dragging one saves straight away (like on Entrances & pins).
function drawPins(way) {
  const ids = new Set();
  for (const s of way.steps) {
    const e = edgeById[s.edge_id];
    ids.add(e.from_node);
    ids.add(e.to_node);
  }
  for (const id of ids) {
    const n = nodeById[id];
    const pin = L.marker(toLatLng(n.map_x, n.map_y), { draggable: true,
                                                       icon: L.divIcon({ className: "route-pin", iconSize: [18, 18] }) })
      .bindTooltip(`${n.name}: drag to move this pin`).addTo(routeLayer);
    pin.on("dragend", () => movePin(n, toPixel(pin.getLatLng())));
  }
}

async function movePin(node, [x, y]) {
  const body = new FormData();
  body.append("csrf", $("csrf").value);
  body.append("x", x);
  body.append("y", y);
  const res = await fetch(`/admin/nodes/${node.id}/position`, { method: "POST", body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    showMsg(data.error || "Couldn't move the pin. Reload the page and try again.", true);
  } else {
    node.map_x = x;
    node.map_y = y;
    showMsg(`Moved the ${node.name} pin. Every pathway that starts or ends there uses the new spot.`);
  }
  drawRoute(false);
  drawEditor();
}

// ---------- Fixing one part ----------
function startEdit(i, zoom = true) {
  if (editing && editing.step !== i && unsaved()) {
    return showMsg("Save or cancel the part you're fixing first.", true);
  }
  if (editing && editing.step === i) return;   // already fixing this part
  const edge = edgeById[ways[shown].steps[i].edge_id];
  editing = { step: i, edge, points: edge.waypoints.map((p) => [...p]), history: [], redraw: false };
  $("editor").hidden = false;
  $("edit-title").textContent = `Fixing step ${i + 1}: ${edge.from_name} → ${edge.to_name}`;
  $("msg").hidden = true;
  drawRoute(false);
  drawEditor();
  if (zoom) {
    const line = lineOf(edge, editing.points).map(([x, y]) => toLatLng(x, y));
    map.fitBounds(L.latLngBounds(line), { padding: [80, 80], maxZoom: 1 });
  }
}

function unsaved() {
  return editing && JSON.stringify(editing.points) !== JSON.stringify(editing.edge.waypoints);
}

function remember() {
  editing.history.push(editing.points.map((p) => [...p]));
}

function drawEditor() {
  editLayer.clearLayers();
  if (!editing) return;
  const { edge, points } = editing;
  const poly = L.polyline(lineOf(edge, points).map(([x, y]) => toLatLng(x, y)),
    { color: "#e07000", weight: 6, opacity: 0.95, interactive: false }).addTo(editLayer);
  // (The two ends are pins, drawn with the route so they can be dragged too)
  points.forEach((p, i) => {
    const dot = L.marker(toLatLng(...p), {
      draggable: true,
      icon: L.divIcon({ className: "edit-dot", iconSize: [16, 16] }),
    }).bindTooltip("Drag to move · double-click to remove").addTo(editLayer);
    dot.on("dragstart", remember);
    dot.on("drag", () => {
      points[i] = toPixel(dot.getLatLng());
      poly.setLatLngs(lineOf(edge, points).map(([x, y]) => toLatLng(x, y)));
    });
    dot.on("dragend", () => { points[i] = toPixel(dot.getLatLng()); drawEditor(); });
    dot.on("dblclick", (ev) => {
      L.DomEvent.stopPropagation(ev);
      remember();
      points.splice(i, 1);
      drawEditor();
    });
  });
  const changed = unsaved() ? " · not saved yet" : "";
  $("edit-status").textContent = editing.redraw
    ? `Drawing again: click along the walkway from one pin to the other${changed}.`
    : `${points.length} point${points.length === 1 ? "" : "s"} · measured ${edge.distance_m} m${changed}`;
}

// Clicking the map adds a bend where it fits best along the line
// (or at the end, when drawing the part again from scratch)
map.on("click", (e) => {
  if (!editing) return;
  const p = toPixel(e.latlng);
  if (p[0] < 0 || p[1] < 0 || p[0] > MAP_W || p[1] > MAP_H) return;
  remember();
  if (editing.redraw) {
    editing.points.push(p);
  } else {
    const line = lineOf(editing.edge, editing.points);
    let best = 0, cost = Infinity;
    for (let j = 0; j < line.length - 1; j++) {
      const extra = dist(line[j], p) + dist(p, line[j + 1]) - dist(line[j], line[j + 1]);
      if (extra < cost) { cost = extra; best = j; }
    }
    editing.points.splice(best, 0, p);   // between line[best] and line[best + 1]
  }
  drawEditor();
});

function dist(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1]); }

$("undo").addEventListener("click", () => {
  if (!editing || !editing.history.length) return;
  editing.points = editing.history.pop();
  drawEditor();
});

$("redraw").addEventListener("click", () => {
  if (!editing) return;
  remember();
  editing.points = [];
  editing.redraw = true;
  drawEditor();
});

$("cancel").addEventListener("click", () => stopEdit());

function stopEdit() {
  editing = null;
  editLayer.clearLayers();
  $("editor").hidden = true;
  if (ways.length) drawRoute(false);
}

$("save").addEventListener("click", async () => {
  if (!editing) return;
  const { edge, points } = editing;
  const body = new FormData();
  body.append("csrf", $("csrf").value);
  body.append("waypoints", JSON.stringify(points));
  const res = await fetch(`/admin/edges/${edge.id}/waypoints`, { method: "POST", body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return showMsg(data.error || "Couldn't save. Reload the page and try again.", true);
  edge.waypoints = points.map((p) => [...p]);
  if (data.hint) edge.direction_hint = data.hint;
  stopEdit();
  await showRoute(true);   // the route and its directions, worked out again
  showMsg(`Saved. The route and its directions are updated.`);
});

$("show").addEventListener("click", () => {
  if (editing && unsaved()) return showMsg("Save or cancel the part you're fixing first.", true);
  stopEdit();
  showRoute(false);
});

function showMsg(text, isError) {
  $("msg").textContent = text;
  $("msg").className = isError ? "error" : "notice";
  $("msg").hidden = false;
}

loadPlaces();
