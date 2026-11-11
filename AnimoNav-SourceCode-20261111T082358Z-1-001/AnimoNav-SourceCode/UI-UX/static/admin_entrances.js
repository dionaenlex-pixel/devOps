// Admin tool: add an entrance to a building by dropping a pin on the campus map.

const $ = (id) => document.getElementById(id);
const map = createCampusMap("map");
const buildingSel = $("building");
const layer = L.layerGroup().addTo(map);
const gateLayer = L.layerGroup().addTo(map);
let building = null;
let newPin = null;   // the red pin for the entrance being added

// Every entrance of every building as a faint dot, for orientation
const dots = {};
for (const b of ENTRANCE_BUILDINGS) {
  for (const e of b.entrances) {
    dots[e.id] = L.circleMarker(toLatLng(e.map_x, e.map_y), { radius: 4, color: "#fff", weight: 1, fillColor: "#33524a", fillOpacity: 0.6 })
      .bindTooltip(e.name).addTo(map);
  }
}

function pin(x, y, cls, title) {
  return L.marker(toLatLng(x, y), {
    draggable: true,
    icon: L.divIcon({ className: `trace-pin ${cls}`, iconSize: [20, 20] }),
  }).bindTooltip(title).addTo(layer);
}

// Existing entrances are moved with the same endpoint as the trace page pins
async function moveEntrance(e, [x, y]) {
  const body = new FormData();
  body.append("csrf", $("csrf").value);
  body.append("x", x);
  body.append("y", y);
  const res = await fetch(`/admin/nodes/${e.id}/position`, { method: "POST", body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return showMsg(data.error || "Couldn't move the pin. Reload the page and try again.", true);
  e.map_x = x;
  e.map_y = y;
  dots[e.id].setLatLng(toLatLng(x, y));
  showMsg(`Moved the ${e.name} pin.`);
}

// Gates (orange) and every other building's entrances (blue) as pins that can be
// dragged, whatever building is picked
function drawGates() {
  gateLayer.clearLayers();
  for (const b of ENTRANCE_BUILDINGS) {
    if (b === building) continue;  // the picked building's pins are already green
    const isGate = b.category === "Entrance/Exit";
    if (!$(isGate ? "show-gates" : "show-entrances").checked) continue;
    for (const e of b.entrances) {
      const p = L.marker(toLatLng(e.map_x, e.map_y), {
        draggable: true,
        icon: L.divIcon({ className: `trace-pin ${isGate ? "pin-gate" : "pin-any"}`, iconSize: [16, 16] }),
      }).bindTooltip(`${e.name} (drag to move)`).addTo(gateLayer);
      p.on("dragend", () => moveEntrance(e, toPixel(p.getLatLng())));
    }
  }
}

function setNewSpot([x, y]) {
  $("x").value = x;
  $("y").value = y;
  newPin.setLatLng(toLatLng(x, y));
}

// A small POST form, like the ones on the pathways page
function postForm(action, fields, buttonText, buttonClass) {
  const form = document.createElement("form");
  form.method = "post";
  form.action = action;
  form.className = "inline-form";
  const inputs = { csrf: $("csrf").value, ...fields };
  for (const [name, value] of Object.entries(inputs)) {
    form.append(Object.assign(document.createElement("input"), { type: "hidden", name, value }));
  }
  form.append(Object.assign(document.createElement("button"),
    { type: "submit", className: buttonClass, textContent: buttonText }));
  return form;
}

// The building's entrances, each with Rename and Delete
function listEntrances() {
  $("manage").hidden = false;
  $("old-building").value = building.name;
  $("building-name").value = building.name;
  const list = $("entrance-list");
  list.innerHTML = "";
  for (const e of building.entrances) {
    const li = document.createElement("li");
    const rename = postForm(`/admin/entrances/${e.id}/rename`, {}, "Rename", "secondary");
    const input = Object.assign(document.createElement("input"), {
      name: "entrance", value: e.entrance || "", placeholder: "No entrance name",
    });
    input.setAttribute("aria-label", `New name for ${e.name}`);
    rename.prepend(input);

    const del = postForm(`/admin/entrances/${e.id}/delete`, {}, "Delete", "danger");
    del.addEventListener("submit", (ev) => {
      if (!confirm(`Delete ${e.name}?`)) ev.preventDefault();
    });
    li.append(rename, del);
    list.append(li);
  }
}

function pick(name) {
  building = ENTRANCE_BUILDINGS.find((b) => b.name === name) || null;
  buildingSel.value = name;
  layer.clearLayers();
  newPin = null;
  $("x").value = $("y").value = "";
  $("manage").hidden = true;
  drawGates();
  if (!building) return;  // nothing picked yet

  for (const e of building.entrances) {
    const p = pin(e.map_x, e.map_y, "pin-start", `${e.name} (drag to move)`);
    p.on("dragend", () => moveEntrance(e, toPixel(p.getLatLng())));
  }
  const first = building.entrances[0];
  newPin = pin(first.map_x + 30, first.map_y + 30, "pin-end", "New entrance (drag to place)");
  newPin.on("dragend", () => setNewSpot(toPixel(newPin.getLatLng())));
  setNewSpot([first.map_x + 30, first.map_y + 30]);
  listEntrances();
  map.setView(toLatLng(first.map_x, first.map_y), 0);
}

function showMsg(text, isError) {
  $("msg").textContent = text;
  $("msg").className = isError ? "error" : "notice";
  $("msg").hidden = false;
}

map.on("click", (e) => {
  if (!newPin) return showMsg("Choose a building first.", true);
  const [x, y] = toPixel(e.latlng);
  if (x < 0 || y < 0 || x > MAP_W || y > MAP_H) return;
  setNewSpot([x, y]);
});
buildingSel.addEventListener("change", () => pick(buildingSel.value));
$("show-gates").addEventListener("change", drawGates);
$("show-entrances").addEventListener("change", drawGates);

for (const b of ENTRANCE_BUILDINGS) buildingSel.append(new Option(b.name, b.name));
pick(ENTRANCE_SELECTED);  // empty until the admin picks a building
