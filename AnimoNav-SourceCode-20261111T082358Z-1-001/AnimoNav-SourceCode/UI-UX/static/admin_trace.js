// Admin tool: click along a walkway on the campus map to save its waypoints.

const $ = (id) => document.getElementById(id);
const map = createCampusMap("map");
showBagChecks(map);
const nodeById = Object.fromEntries(TRACE_NODES.map((n) => [n.id, n]));
const edgeSel = $("edge");
let edge = null;    // the pathway being traced
let points = [];    // its waypoints, [x, y] map pixels
let saved = true;
let warnedUnsaved = false;
const layer = L.layerGroup().addTo(map);

// Every location as a faint dot, for orientation
const dots = {};
for (const n of TRACE_NODES) {
  dots[n.id] = L.circleMarker(toLatLng(n.map_x, n.map_y), { radius: 4, color: "#fff", weight: 1, fillColor: "#33524a", fillOpacity: 0.6 })
    .bindTooltip(n.name).addTo(map);
}

// The start and end pins can be dragged onto the walkway or entrance
function endPin(node, cls, title) {
  const pin = L.marker(toLatLng(node.map_x, node.map_y), {
    draggable: true,
    icon: L.divIcon({ className: `trace-pin ${cls}`, iconSize: [20, 20] }),
  }).bindTooltip(`${title}: ${node.name} (drag to move)`);
  pin.on("dragend", () => movePin(node, toPixel(pin.getLatLng())));
  return pin;
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
    dots[node.id].setLatLng(toLatLng(x, y));
    showMsg(`Moved the ${node.name} pin. Routes through it use the new spot.`);
  }
  draw();
}

// Pathways between the same two buildings are one entry in the dropdown, and
// each of their ways gets a button. Each way is still its own pathway (its own
// distance, status, one-way and line).
const groups = [];   // [{ name, ways: [pathways] }], in order of each group's first pathway
const groupOf = {};  // pathway id -> its group
const byPair = new Map();
for (const e of TRACE_EDGES) {
  const key = [e.from_building, e.to_building].sort().join("|");
  if (!byPair.has(key)) {
    byPair.set(key, { ways: [] });
    groups.push(byPair.get(key));
  }
  byPair.get(key).ways.push(e);
  groupOf[e.id] = byPair.get(key);
}
for (const g of groups) {
  const first = g.ways[0];
  const bothDirections = g.ways.some((e) => e.from_building !== first.from_building);
  g.name = `${first.from_building} ${bothDirections ? "↔" : "→"} ${first.to_building}`;
}

const tick = (e) => (e.waypoints.length ? "✓" : "○");

function fillList() {
  edgeSel.innerHTML = "";
  groups.forEach((g, i) => {
    const done = g.ways.every((e) => e.waypoints.length) ? "✓" : "○";
    const count = g.ways.length > 1 ? ` · ${g.ways.length} ways` : "";
    edgeSel.append(new Option(`${done} ${g.name}${count}`, i));
  });
  const done = TRACE_EDGES.filter((e) => e.waypoints.length).length;
  $("progress").textContent = `${done} of ${TRACE_EDGES.length} traced`;
}

// One button per way between the picked places (none when there's only one way)
function fillWays() {
  const ways = groupOf[edge.id].ways;
  const box = $("ways");
  box.hidden = ways.length < 2;
  box.innerHTML = "";
  for (const e of ways) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "route-option" + (e === edge ? " chosen" : "");
    b.title = e.direction_hint;
    b.append(Object.assign(document.createElement("strong"),
      { textContent: `${tick(e)} Pathway ${e.id} · ${Math.round(e.distance_m)} m` }));
    b.append(Object.assign(document.createElement("small"),
      { textContent: `${e.from_name} → ${e.to_name}` }));
    b.addEventListener("click", () => pick(e.id));
    box.append(b);
  }
}

function pick(id) {
  if (!saved && !warnedUnsaved) {
    showMsg("You have unsaved points. Press Save first, or switch again to discard them.", true);
    warnedUnsaved = true;
    edgeSel.value = groups.indexOf(groupOf[edge.id]);
    return;
  }
  warnedUnsaved = false;
  $("msg").hidden = true;
  $("hint-text").textContent = TRACE_EDGES.find((e) => e.id === Number(id)).direction_hint;
  $("edit-link").href = `/admin#edge-${id}`;
  edge = TRACE_EDGES.find((e) => e.id === Number(id));
  points = edge.waypoints.map((p) => [...p]);
  saved = true;
  edgeSel.value = groups.indexOf(groupOf[edge.id]);
  fillWays();
  draw();
  // Show every way between the two places
  const all = groupOf[edge.id].ways.flatMap((e) => lineOf(e, e.waypoints));
  map.fitBounds(L.latLngBounds(all.map(([x, y]) => toLatLng(x, y))), { padding: [80, 80], maxZoom: 1 });
}

// A pathway's line in map pixels: start pin, traced points, end pin
function lineOf(e, waypoints) {
  const a = nodeById[e.from_node], b = nodeById[e.to_node];
  return [[a.map_x, a.map_y], ...waypoints, [b.map_x, b.map_y]];
}

function draw() {
  layer.clearLayers();
  // The other ways between the same places, dashed (click one to trace it)
  for (const other of groupOf[edge.id].ways) {
    if (other === edge) continue;
    L.polyline(lineOf(other, other.waypoints).map(([x, y]) => toLatLng(x, y)),
      { color: "#5b6b62", weight: 4, opacity: 0.6, dashArray: "8 8" })
      .bindTooltip(`Pathway ${other.id} · ${Math.round(other.distance_m)} m (click to trace)`)
      .on("click", (ev) => { L.DomEvent.stopPropagation(ev); pick(other.id); })   // not a new point
      .addTo(layer);
  }
  const a = nodeById[edge.from_node], b = nodeById[edge.to_node];
  const line = lineOf(edge, points).map(([x, y]) => toLatLng(x, y));
  L.polyline(line, { color: "#0b6b3a", weight: 5, opacity: 0.85 }).addTo(layer);
  points.forEach(([x, y], i) => {
    L.circleMarker(toLatLng(x, y), { radius: 5, color: "#0b6b3a", weight: 2, fillColor: "#fff", fillOpacity: 1 })
      .bindTooltip(`Point ${i + 1}`).addTo(layer);
  });
  endPin(a, "pin-start", "Start").addTo(layer);
  endPin(b, "pin-end", "End").addTo(layer);
  $("status").textContent = `${points.length} point${points.length === 1 ? "" : "s"}${saved ? "" : " · not saved"} · measured ${edge.distance_m} m`;
}

function showMsg(text, isError) {
  $("msg").textContent = text;
  $("msg").className = isError ? "error" : "notice";
  $("msg").hidden = false;
}

map.on("click", (e) => {
  const [x, y] = toPixel(e.latlng);
  if (x < 0 || y < 0 || x > MAP_W || y > MAP_H) return;
  points.push([x, y]);
  saved = false;
  draw();
});

$("undo").addEventListener("click", () => { points.pop(); saved = false; draw(); });
// Retrace: clear the old line and start again from the green pin
$("clear").addEventListener("click", () => {
  points = [];
  saved = false;
  draw();
  showMsg("Retracing: click along the walkway from the green pin to the red pin, then press Save.");
});
edgeSel.addEventListener("change", () => {
  const ways = groups[edgeSel.value].ways;
  pick((ways.find((e) => !e.waypoints.length) || ways[0]).id);   // an untraced way first
});

$("save").addEventListener("click", async () => {
  const body = new FormData();
  body.append("csrf", $("csrf").value);
  body.append("waypoints", JSON.stringify(points));
  const res = await fetch(`/admin/edges/${edge.id}/waypoints`, { method: "POST", body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return showMsg(data.error || "Couldn't save. Reload the page and try again.", true);
  edge.waypoints = points.map((p) => [...p]);
  saved = true;
  fillList();
  edgeSel.value = groups.indexOf(groupOf[edge.id]);
  fillWays();
  draw();
  if (data.hint) {
    edge.direction_hint = data.hint;
    $("hint-text").textContent = data.hint;
  }
  showMsg(`Saved pathway ${edge.id} with ${points.length} points. Its directions were rewritten from the new line.`);
});

$("next").addEventListener("click", () => {
  const start = TRACE_EDGES.indexOf(edge);
  const rest = [...TRACE_EDGES.slice(start + 1), ...TRACE_EDGES.slice(0, start + 1)];
  const nextEdge = rest.find((e) => !e.waypoints.length);
  if (nextEdge) pick(nextEdge.id);
  else showMsg("Every pathway is traced.");
});

fillList();
const requested = TRACE_EDGES.find((e) => e.id === TRACE_SELECTED);
pick((requested || TRACE_EDGES.find((e) => !e.waypoints.length) || TRACE_EDGES[0]).id);
