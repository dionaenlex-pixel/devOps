"""AnimoNav: walking directions around the De La Salle Lipa campus."""

import datetime
import functools
import json
import os
import secrets
import time

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash

from database import db
from routing.bagchecks import check_label, checks_for_step
from database.campus_data import BAG_CHECKS
from routing.directions import build_directions
from routing.hints import hints_for_edge, sentences

STATUSES = ["available", "blocked", "closed", "under_construction"]
MAX_DISTANCE_FROM_CAMPUS_M = 400  # farther than this, "Use my location" is ignored
MAP_W, MAP_H = 2000, 1006         # size of static/campus-map.webp in pixels
MAX_WAYPOINTS = 200
MAX_LOGIN_TRIES = 3               # wrong passwords in a row before an account is locked
LOCK_SECONDS = 24 * 60 * 60       # how long it stays locked
PH_TIME = datetime.timezone(datetime.timedelta(hours=8))

UI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "UI-UX")
app = Flask(__name__, template_folder=os.path.join(UI_DIR, "templates"),
            static_folder=os.path.join(UI_DIR, "static"),
            instance_path=os.path.join(db.BASE_DIR, "instance"))


def load_secret_key():
    """Use ANIMONAV_SECRET_KEY if set, otherwise keep a random key in instance/."""
    key = os.environ.get("ANIMONAV_SECRET_KEY")
    if key:
        return key
    os.makedirs(app.instance_path, exist_ok=True)
    path = os.path.join(app.instance_path, "secret_key")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(32))
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


app.config["SECRET_KEY"] = load_secret_key()
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


@app.url_defaults
def static_version(endpoint, values):
    """Add the file's last-changed time to static URLs (style.css?v=1793264968), so
    browsers fetch the new file after an update instead of an old cached copy."""
    if endpoint == "static" and "filename" in values:
        path = os.path.join(app.static_folder, values["filename"])
        if os.path.exists(path):
            values["v"] = int(os.path.getmtime(path))


def get_db():
    if "db" not in g:
        if not os.path.exists(db.DB_PATH):
            abort(500, "The database doesn't exist yet. Run: python seed.py")
        g.db = db.connect()
    return g.db


@app.teardown_appcontext
def close_db(_error):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# ---------- Public pages and API ----------

@app.route("/")
def index():
    return render_template("index.html")


def list_buildings(conn):
    """One entry per building, with its entrances. A building's id is its lowest
    entrance id, and routes accept any entrance id, so that id stands for the building."""
    buildings = {}
    for r in conn.execute("SELECT * FROM nodes WHERE category != 'Junction' ORDER BY id"):
        # Walkway junctions are only for routes to pass through, not places to pick
        if r["building"] not in buildings:
            buildings[r["building"]] = {"id": r["id"], "name": r["building"],
                                        "category": r["category"],
                                        "description": r["description"], "entrances": []}
        buildings[r["building"]]["entrances"].append(
            {k: r[k] for k in ("id", "name", "entrance", "map_x", "map_y")})
    return sorted(buildings.values(), key=lambda b: (b["category"], b["name"]))


@app.route("/api/locations")
def api_locations():
    return jsonify(list_buildings(get_db()))


@app.route("/api/bag-checks")
def api_bag_checks():
    """The bag checks marked on the campus map (the gates have one too)."""
    return jsonify([{"name": check_label(c), "map_x": c["x"], "map_y": c["y"]} for c in BAG_CHECKS])


@app.route("/api/route")
def api_route():
    start = request.args.get("from", type=int)
    goal = request.args.get("to", type=int)
    graph = db.load_graph(get_db())
    if start not in graph.nodes or goal not in graph.nodes:
        return jsonify(error="Choose a starting point and a destination from the list."), 400

    # ?parts=1 (the admin Fix a route page): one step per pathway, junctions included
    route = build_directions(graph, start, goal, merge_junctions=request.args.get("parts") != "1")
    if route is None:
        return jsonify(error="No open pathway connects these two places right now. "
                             "Some paths may be blocked or under construction."), 404
    return jsonify(route)


@app.route("/api/nearest")
def api_nearest():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return jsonify(error="Missing lat or lon."), 400
    graph = db.load_graph(get_db())
    node, distance = graph.nearest_node(lat, lon)
    if distance > MAX_DISTANCE_FROM_CAMPUS_M:
        return jsonify(on_campus=False)
    building_id = min(graph.entrances(node["id"]))  # same id as in /api/locations
    return jsonify(on_campus=True, id=building_id, name=node["building"],
                   distance_m=round(distance))


# ---------- Admin ----------

def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf():
    if request.method == "POST":
        token = request.form.get("csrf")
        if not token or token != session.get("csrf"):
            abort(400, "The form expired. Go back, reload the page, and try again.")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        conn = get_db()
        db.add_login_lock_columns(conn)
        user = conn.execute("SELECT * FROM users WHERE username = ?",
                            (request.form.get("username", ""),)).fetchone()
        now = time.time()
        locked = user and user["locked_until"] and user["locked_until"] > now
        if locked:
            flash(locked_message(user["locked_until"]))
        elif user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            conn.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = ?", (user["id"],))
            conn.commit()
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            next_url = request.args.get("next", "")
            return redirect(next_url if next_url.startswith("/admin") else url_for("admin"))
        elif user:
            # A lock that has run out starts the count again
            tries = (0 if user["locked_until"] else user["failed_logins"]) + 1
            if tries >= MAX_LOGIN_TRIES:
                conn.execute("UPDATE users SET failed_logins = 0, locked_until = ? WHERE id = ?",
                             (now + LOCK_SECONDS, user["id"]))
                flash("Wrong password. " + locked_message(now + LOCK_SECONDS))
            else:
                conn.execute("UPDATE users SET failed_logins = ?, locked_until = NULL WHERE id = ?",
                             (tries, user["id"]))
                left = MAX_LOGIN_TRIES - tries
                flash(f"Wrong username or password. {left} {'try' if left == 1 else 'tries'} left "
                      "before this account is locked for 24 hours.")
            conn.commit()
        else:
            flash("Wrong username or password.")
    return render_template("admin_login.html")


def locked_message(until):
    when = datetime.datetime.fromtimestamp(until, PH_TIME).strftime("%b %d, %I:%M %p").replace(" 0", " ")
    return (f"This account is locked after {MAX_LOGIN_TRIES} wrong passwords. "
            f"You can log in again on {when} (Philippine time).")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@login_required
def admin():
    conn = get_db()
    edges = conn.execute("""
        SELECT e.*, a.name AS from_name, b.name AS to_name,
               a.building AS from_building, b.building AS to_building
        FROM edges e
        JOIN nodes a ON a.id = e.from_node
        JOIN nodes b ON b.id = e.to_node
        ORDER BY e.id
    """).fetchall()
    nodes = conn.execute("SELECT id, name FROM nodes ORDER BY name").fetchall()
    # Buildings with more than one entrance get an entrance picker on their pathways
    entrances = {}
    for b in list_buildings(conn):
        if len(b["entrances"]) > 1:
            entrances[b["name"]] = b["entrances"]
    # Bag checks each pathway passes: (walking forwards, walking backwards)
    places = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM nodes")}
    bag = {}
    for e in edges:
        a, b = places[e["from_node"]], places[e["to_node"]]
        line = [[a["map_x"], a["map_y"]], *json.loads(e["waypoints"] or "[]"), [b["map_x"], b["map_y"]]]
        bag[e["id"]] = (checks_for_step(a, b, line, e["id"]),
                        [] if e["one_way"] else checks_for_step(b, a, line[::-1], e["id"]))
    return render_template("admin.html", groups=group_pathways(edges), nodes=nodes,
                           bag=bag, check_label=check_label,
                           statuses=STATUSES, base_ids=db.base_edge_ids(), entrances=entrances)


def group_pathways(edges):
    """Put pathways between the same two buildings together, like the trace page.

    Returns [(heading, [pathways])] in order of each group's first pathway id;
    the heading is None for a pair of buildings with only one pathway.
    """
    groups = {}  # "A ↔ B" -> its pathways
    for e in edges:
        key = " ↔ ".join(sorted([e["from_building"], e["to_building"]]))
        groups.setdefault(key, []).append(e)
    return [(f"{key} · {len(group)} ways" if len(group) > 1 else None, group)
            for key, group in groups.items()]


def read_edge_form(form):
    """Validate the pathway fields shared by the add and update forms."""
    try:
        distance = float(form.get("distance_m", ""))
    except ValueError:
        distance = 0
    if distance <= 0:
        return None, "Distance must be a number greater than 0."
    status = form.get("status", "available")
    if status not in STATUSES:
        return None, "Unknown status."
    hint = form.get("direction_hint", "").strip()
    if not hint:
        return None, "Direction hint can't be empty."
    return {
        "distance_m": distance,
        "status": status,
        "direction_hint": hint,
        "reverse_hint": form.get("reverse_hint", "").strip() or None,
        "one_way": 1 if form.get("one_way") else 0,
    }, None


@app.route("/admin/edges/<int:edge_id>", methods=["POST"])
@login_required
def admin_update_edge(edge_id):
    data, error = read_edge_form(request.form)
    if error:
        flash(f"Edge {edge_id} not saved: {error}")
        return redirect(url_for("admin"))
    conn = get_db()
    edge = conn.execute("SELECT from_node, to_node FROM edges WHERE id = ?", (edge_id,)).fetchone()
    if edge is None:
        flash(f"Edge {edge_id} doesn't exist.")
        return redirect(url_for("admin"))

    # An end can only move to another entrance of the same building
    ends = []
    for field in ("from_node", "to_node"):
        new_id = request.form.get(field, edge[field], type=int)
        if new_id != edge[field] and building_of(conn, new_id) != building_of(conn, edge[field]):
            flash(f"Edge {edge_id} not saved: an end can only move to another entrance of the same building.")
            return redirect(url_for("admin") + f"#edge-{edge_id}")
        ends.append(new_id)
    if ends[0] == ends[1]:
        flash(f"Edge {edge_id} not saved: both ends are the same entrance.")
        return redirect(url_for("admin") + f"#edge-{edge_id}")

    conn.execute("""
        UPDATE edges SET from_node = ?, to_node = ?, distance_m = ?, status = ?,
                         direction_hint = ?, reverse_hint = ?, one_way = ?
        WHERE id = ?
    """, (ends[0], ends[1], data["distance_m"], data["status"], data["direction_hint"],
          data["reverse_hint"], data["one_way"], edge_id))
    conn.commit()
    if edge_id in db.base_edge_ids():
        db.write_entrances_file(conn)  # keeps a measured pathway's new entrance
    else:
        db.write_extra_edges_file(conn)
    flash(f"Edge {edge_id} saved.")
    return redirect(url_for("admin") + f"#edge-{edge_id}")


def building_of(conn, node_id):
    row = conn.execute("SELECT building FROM nodes WHERE id = ?", (node_id,)).fetchone()
    return row["building"] if row else None


@app.route("/admin/edges/<int:edge_id>/delete", methods=["POST"])
@login_required
def admin_delete_edge(edge_id):
    if edge_id in db.base_edge_ids():
        flash(f"Edge {edge_id} is one of the measured pathways. Set it to blocked or closed instead.")
        return redirect(url_for("admin") + f"#edge-{edge_id}")
    conn = get_db()
    cur = conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
    conn.commit()
    db.write_extra_edges_file(conn)
    db.write_waypoints_file(conn)
    flash(f"Pathway {edge_id} deleted." if cur.rowcount else f"Edge {edge_id} doesn't exist.")
    return redirect(url_for("admin"))


@app.route("/admin/edges", methods=["POST"])
@login_required
def admin_add_edge():
    data, error = read_edge_form(request.form)
    from_node = request.form.get("from_node", type=int)
    to_node = request.form.get("to_node", type=int)
    conn = get_db()
    ids = {r["id"] for r in conn.execute("SELECT id FROM nodes")}
    if not error and (from_node not in ids or to_node not in ids or from_node == to_node):
        error = "Pick two different locations."
    if error:
        flash(f"Pathway not added: {error}")
        return redirect(url_for("admin"))
    cur = conn.execute("""
        INSERT INTO edges (from_node, to_node, distance_m, status, direction_hint,
                           reverse_hint, one_way)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (from_node, to_node, data["distance_m"], data["status"], data["direction_hint"],
          data["reverse_hint"], data["one_way"]))
    conn.commit()
    db.write_extra_edges_file(conn)
    flash(f"Pathway {cur.lastrowid} added. Now trace it on the map.")
    return redirect(url_for("admin_trace", edge=cur.lastrowid))


@app.route("/admin/trace")
@login_required
def admin_trace():
    nodes, edges = map_data(get_db())
    return render_template("admin_trace.html", nodes=nodes, edges=edges,
                           selected=request.args.get("edge", type=int))


@app.route("/admin/routes")
@login_required
def admin_routes():
    """Fix a route: show the route between two places and edit its lines on the map."""
    nodes, edges = map_data(get_db())
    return render_template("admin_routes.html", nodes=nodes, edges=edges)


def map_data(conn):
    """Every location's pin and every pathway's traced line, for the map editing pages."""
    nodes = [dict(r) for r in conn.execute("SELECT id, name, map_x, map_y FROM nodes")]
    edges = []
    for r in conn.execute("""
        SELECT e.id, e.from_node, e.to_node, e.distance_m, e.waypoints, e.direction_hint,
               a.name AS from_name, b.name AS to_name,
               a.building AS from_building, b.building AS to_building
        FROM edges e
        JOIN nodes a ON a.id = e.from_node
        JOIN nodes b ON b.id = e.to_node
        ORDER BY e.id
    """):
        edge = dict(r)
        edge["waypoints"] = json.loads(edge["waypoints"] or "[]")
        edges.append(edge)
    return nodes, edges


@app.route("/admin/edges/<int:edge_id>/waypoints", methods=["POST"])
@login_required
def admin_save_waypoints(edge_id):
    try:
        points = json.loads(request.form.get("waypoints", ""))
        valid = (isinstance(points, list) and len(points) <= MAX_WAYPOINTS and all(
            isinstance(p, list) and len(p) == 2
            and all(isinstance(v, (int, float)) for v in p)
            and 0 <= p[0] <= MAP_W and 0 <= p[1] <= MAP_H
            for p in points))
    except ValueError:
        valid = False
    if not valid:
        return jsonify(error=f"Waypoints must be up to {MAX_WAYPOINTS} [x, y] points on the map."), 400

    conn = get_db()
    cur = conn.execute("UPDATE edges SET waypoints = ? WHERE id = ?",
                       (json.dumps([[round(x), round(y)] for x, y in points]), edge_id))
    conn.commit()
    if not cur.rowcount:
        return jsonify(error=f"Edge {edge_id} doesn't exist."), 404
    hint = rewrite_hints(conn, edge_id)
    db.write_waypoints_file(conn)
    if edge_id in db.base_edge_ids():
        db.write_entrances_file(conn)   # keeps the measured pathway's new hints
    else:
        db.write_extra_edges_file(conn)
    return jsonify(ok=True, count=len(points), hint=hint)


def kept_note(hint):
    """What to keep from a pathway's old hint when it's rewritten from a new trace: its
    "This way…" landmark note, or the whole hint if an admin typed it themselves."""
    if not hint or hint.startswith(("Head ", "You pass", "Go out", "Walk to")) or "direction hint" in hint:
        return next((s.strip() + "." for s in sentences(hint) if s.startswith("This way ")), None) \
            if hint else None
    return hint if hint.endswith(".") else hint + "."


def rewrite_hints(conn, edge_id):
    """Write a pathway's hints again from its traced line (hints.py), keeping its note."""
    edge = dict(conn.execute("SELECT * FROM edges WHERE id = ?", (edge_id,)).fetchone())
    edge["waypoints"] = json.loads(edge["waypoints"] or "[]")
    places = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM nodes")}
    there, back = hints_for_edge(edge, places, kept_note(edge["direction_hint"]))
    conn.execute("UPDATE edges SET direction_hint = ?, reverse_hint = ? WHERE id = ?",
                 (there, None if edge["one_way"] else back, edge_id))
    conn.commit()
    return there


@app.route("/admin/nodes/<int:node_id>/position", methods=["POST"])
@login_required
def admin_move_pin(node_id):
    x = request.form.get("x", type=float)
    y = request.form.get("y", type=float)
    if x is None or y is None or not (0 <= x <= MAP_W and 0 <= y <= MAP_H):
        return jsonify(error="Drop the pin inside the map."), 400
    conn = get_db()
    cur = conn.execute("UPDATE nodes SET map_x = ?, map_y = ? WHERE id = ?",
                       (round(x), round(y), node_id))
    conn.commit()
    if not cur.rowcount:
        return jsonify(error=f"Location {node_id} doesn't exist."), 404
    db.write_positions_file(conn)
    db.write_entrances_file(conn)  # added entrances keep their pin there too
    return jsonify(ok=True)


@app.route("/admin/entrances")
@login_required
def admin_entrances():
    buildings = list_buildings(get_db())
    return render_template("admin_entrances.html", buildings=buildings,
                           selected=request.args.get("building", ""))


def location_name(building, entrance):
    """'Mabini Hall – Back Entrance', or just the building if it has no entrance name."""
    return f"{building} – {entrance}" if entrance else building


@app.route("/admin/entrances/<int:node_id>/rename", methods=["POST"])
@login_required
def admin_rename_entrance(node_id):
    conn = get_db()
    node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    if node is None:
        flash(f"Location {node_id} doesn't exist.")
        return redirect(url_for("admin_entrances"))
    back = url_for("admin_entrances", building=node["building"])
    label = request.form.get("entrance", "").strip() or None
    others = conn.execute("SELECT entrance FROM nodes WHERE building = ? AND id != ?",
                          (node["building"], node_id)).fetchall()
    if label and any((r["entrance"] or "").lower() == label.lower() for r in others):
        flash(f"{node['building']} already has an entrance called {label}.")
        return redirect(back)
    conn.execute("UPDATE nodes SET entrance = ?, name = ? WHERE id = ?",
                 (label, location_name(node["building"], label), node_id))
    conn.commit()
    db.write_entrances_file(conn)
    flash(f"Renamed {node['name']} to {location_name(node['building'], label)}.")
    return redirect(back)


@app.route("/admin/buildings/rename", methods=["POST"])
@login_required
def admin_rename_building():
    old = request.form.get("old_building", "")
    new = request.form.get("building", "").strip()
    conn = get_db()
    nodes = conn.execute("SELECT * FROM nodes WHERE building = ?", (old,)).fetchall()
    taken = conn.execute("SELECT 1 FROM nodes WHERE building = ?", (new,)).fetchone()
    if not nodes:
        flash("Pick a building from the list.")
        return redirect(url_for("admin_entrances"))
    if not new or (taken and new != old):
        flash(f"Building not renamed: {'give it a name' if not new else f'{new} already exists'}.")
        return redirect(url_for("admin_entrances", building=old))
    for n in nodes:
        conn.execute("UPDATE nodes SET building = ?, name = ? WHERE id = ?",
                     (new, location_name(new, n["entrance"]), n["id"]))
    conn.commit()
    db.write_entrances_file(conn)
    flash(f"Renamed {old} to {new}. Pathway hints that mention the old name aren't changed.")
    return redirect(url_for("admin_entrances", building=new))


@app.route("/admin/entrances/<int:node_id>/delete", methods=["POST"])
@login_required
def admin_delete_entrance(node_id):
    conn = get_db()
    node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    if node is None:
        flash(f"Location {node_id} doesn't exist.")
        return redirect(url_for("admin_entrances"))
    back = url_for("admin_entrances", building=node["building"])
    # Pathways would point at nothing, so they have to be moved or deleted first
    used = [str(r["id"]) for r in conn.execute(
        "SELECT id FROM edges WHERE from_node = ? OR to_node = ?", (node_id, node_id))]
    if used:
        flash(f"{node['name']} is used by pathway {', '.join(used)}. "
              "Move those pathways to another entrance or delete them first.")
        return redirect(back)
    conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
    conn.commit()
    db.write_entrances_file(conn)
    db.write_positions_file(conn)
    flash(f"Deleted {node['name']}.")
    return redirect(back)


@app.route("/admin/entrances", methods=["POST"])
@login_required
def admin_add_entrance():
    building = request.form.get("building", "")
    label = request.form.get("entrance", "").strip()
    x = request.form.get("x", type=float)
    y = request.form.get("y", type=float)
    conn = get_db()
    existing = conn.execute("SELECT * FROM nodes WHERE building = ? ORDER BY id",
                            (building,)).fetchall()
    error = None
    if not existing:
        error = "Pick a building from the list."
    elif not label:
        error = "Give the entrance a name, like Back Entrance."
    elif any((r["entrance"] or "").lower() == label.lower() for r in existing):
        error = f"{building} already has an entrance called {label}."
    elif x is None or y is None or not (0 <= x <= MAP_W and 0 <= y <= MAP_H):
        error = "Drop the pin inside the map."
    if error:
        flash(f"Entrance not added: {error}")
        return redirect(url_for("admin_entrances", building=building))

    # The new entrance shares the building's details; GPS is copied from its first entrance
    first = existing[0]
    # Never reuse a team location's id, even if that location was deleted
    max_id = conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0]
    new_id = max(max_id, *db.base_node_ids()) + 1
    conn.execute("""
        INSERT INTO nodes (id, name, building, entrance, category, latitude, longitude,
                           map_x, map_y, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (new_id, location_name(building, label), building, label, first["category"],
          first["latitude"], first["longitude"], round(x), round(y),
          f"{label} of {building}."))
    conn.commit()
    db.write_entrances_file(conn)
    flash(f"Added {label} to {building}. Now add or move pathways so they reach it.")
    return redirect(url_for("admin_entrances", building=building))


if __name__ == "__main__":
    app.run(debug=True)
