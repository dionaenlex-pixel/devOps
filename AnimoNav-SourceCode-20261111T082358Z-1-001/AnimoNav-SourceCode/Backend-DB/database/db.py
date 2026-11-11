"""SQLite helpers: open the database and load the campus graph from it."""

import json
import math
import os
import sqlite3

from routing.bagchecks import mark_bag_checks
from routing.graph import Graph
from routing.hints import lower_first, place_name

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ANIMONAV_DB", os.path.join(BASE_DIR, "instance", "animonav.db"))
# Traced walkways are also kept in this file, so they survive `python seed.py`
# and can be shared through Git like the rest of the campus data.
WAYPOINTS_PATH = os.environ.get("ANIMONAV_WAYPOINTS", os.path.join(BASE_DIR, "waypoints.json"))
# Pins moved on the trace page are kept here for the same reason.
POSITIONS_PATH = os.environ.get("ANIMONAV_POSITIONS", os.path.join(BASE_DIR, "map_positions.json"))
# Pathways added on the admin page (extra routes and shortcuts) are kept here too.
EXTRA_EDGES_PATH = os.environ.get("ANIMONAV_EXTRA_EDGES", os.path.join(BASE_DIR, "extra_edges.json"))
EXTRA_EDGE_FIELDS = ["id", "from_node", "to_node", "distance_m", "direction_hint",
                     "reverse_hint", "one_way", "status"]
# Entrances added on the admin page, and measured pathways moved to another entrance.
ENTRANCES_PATH = os.environ.get("ANIMONAV_ENTRANCES", os.path.join(BASE_DIR, "entrances.json"))
ENTRANCE_FIELDS = ["id", "name", "building", "entrance", "category", "latitude", "longitude",
                   "map_x", "map_y", "description"]


def base_edge_ids():
    """IDs of the pathways measured by the team in campus_data.py."""
    from database.campus_data import EDGES
    return {e[0] for e in EDGES}


def base_node_ids():
    """IDs of the locations in campus_data.py."""
    from database.campus_data import NODES
    return {n[0] for n in NODES}


def connect(path=None):
    """Open the database. Rows can be read like dicts: row["name"]."""
    path = path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


LOGIN_LOCK_COLUMNS = {"failed_logins": "INTEGER NOT NULL DEFAULT 0", "locked_until": "REAL"}


def add_login_lock_columns(conn):
    """Add the login-lock columns to a users table made before they existed."""
    have = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
    for column, declaration in LOGIN_LOCK_COLUMNS.items():
        if column not in have:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column} {declaration}")
    conn.commit()


def load_graph(conn):
    """Query the nodes and edges tables and build the adjacency list in memory.

    Called on every route search, so changes an admin makes (a blocked path,
    a new distance) are used right away.
    """
    graph = Graph()
    for row in conn.execute("SELECT * FROM nodes"):
        graph.add_node(dict(row))
    for row in conn.execute("SELECT * FROM edges"):
        edge = dict(row)
        edge["waypoints"] = json.loads(edge.get("waypoints") or "[]")
        graph.add_edge(edge)
    add_inside_links(graph)
    mark_bag_checks(graph)
    return graph


M_PER_PX = 0.37         # metres per map pixel (from the team's GPS points)
INSIDE_FACTOR = 1.3     # walking through a building is longer than the straight line between doors


def add_inside_links(graph):
    """Let routes go through a building from one of its doors to another (e.g. into BB Hall's
    main entrance and out of its exit facing Jaime Hilario Hall). The length is the
    straight line between the doors' pins on the map, times INSIDE_FACTOR. These links
    aren't stored: they follow the pins, so moving a door's pin updates them.
    Only buildings people really walk through (WALK_THROUGH) get them."""
    from database.campus_data import WALK_THROUGH
    for building, ids in graph.buildings.items():
        if building not in WALK_THROUGH:
            continue
        for i, a_id in enumerate(ids):
            for b_id in ids[i + 1:]:
                a, b = graph.nodes[a_id], graph.nodes[b_id]
                d = math.dist((a["map_x"], a["map_y"]), (b["map_x"], b["map_y"])) * M_PER_PX * INSIDE_FACTOR
                door = lambda n: lower_first(n["entrance"] or "main entrance")
                graph.add_edge({
                    "id": -(a_id * 1000 + b_id),   # negative: not a pathway in the database
                    "from_node": a_id, "to_node": b_id, "distance_m": round(max(d, 5), 1),
                    "status": "available", "one_way": 0, "inside": True, "waypoints": [],
                    "direction_hint": f"Go through {place_name(building)} to its {door(b)}.",
                    "reverse_hint": f"Go through {place_name(building)} to its {door(a)}.",
                })


def read_waypoints_file(path=None):
    """{edge id: [[x, y], ...]} from waypoints.json, or {} if there's no file yet."""
    path = path or WAYPOINTS_PATH
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {int(k): v for k, v in json.load(f).items()}


def read_positions_file(path=None):
    """{node id: (x, y)} for pins moved on the trace page, or {} if none moved yet."""
    path = path or POSITIONS_PATH
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {int(k): tuple(v) for k, v in json.load(f).items()}


def write_positions_file(conn, path=None):
    """Save every pin's map position from the database to map_positions.json."""
    path = path or POSITIONS_PATH
    data = {str(r["id"]): [r["map_x"], r["map_y"]]
            for r in conn.execute("SELECT id, map_x, map_y FROM nodes ORDER BY id")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def read_extra_edges_file(path=None):
    """Pathways added on the admin page, as a list of dicts, or [] if none yet."""
    path = path or EXTRA_EDGES_PATH
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_extra_edges_file(conn, path=None):
    """Save every pathway that isn't in campus_data.py to extra_edges.json."""
    path = path or EXTRA_EDGES_PATH
    base = base_edge_ids()
    cols = ", ".join(EXTRA_EDGE_FIELDS)
    rows = [dict(r) for r in conn.execute(f"SELECT {cols} FROM edges ORDER BY id")
            if r["id"] not in base]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1)


def read_entrances_file(path=None):
    """Admin changes to locations, from entrances.json:
    entrances:    entrances added on the admin page, as node dicts
    pathway_ends: {edge id: [from, to]} for measured pathways moved to another entrance
    pathway_changes: {edge id: {field: value}} for other changes to measured pathways
                  (status, distance, hints, one-way) made on the admin page
    renamed:      {node id: {"name", "building", "entrance"}} for renamed team locations
    removed:      ids of team locations deleted on the admin page
    """
    path = path or ENTRANCES_PATH
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    return {"entrances": data.get("entrances", []),
            "pathway_ends": {int(k): v for k, v in data.get("pathway_ends", {}).items()},
            "pathway_changes": {int(k): v for k, v in data.get("pathway_changes", {}).items()},
            "renamed": {int(k): v for k, v in data.get("renamed", {}).items()},
            "removed": data.get("removed", [])}


def base_node_names():
    """{node id: (name, building, entrance)} as written in campus_data.py."""
    from database.campus_data import ENTRANCES, NODES
    return {n[0]: (n[1],) + ENTRANCES.get(n[0], (n[1], None)) for n in NODES}


def write_entrances_file(conn, path=None):
    """Save every admin change to locations (see read_entrances_file) to entrances.json."""
    from database.campus_data import EDGES
    path = path or ENTRANCES_PATH
    base = base_node_names()
    rows = [dict(r) for r in conn.execute(f"SELECT {', '.join(ENTRANCE_FIELDS)} FROM nodes ORDER BY id")]
    entrances = [r for r in rows if r["id"] not in base]
    renamed = {str(r["id"]): {"name": r["name"], "building": r["building"], "entrance": r["entrance"]}
               for r in rows if r["id"] in base
               and (r["name"], r["building"], r["entrance"]) != base[r["id"]]}
    removed = sorted(set(base) - {r["id"] for r in rows})
    measured = {e[0]: [e[1], e[2]] for e in EDGES}
    ends = {}
    changes = {}
    team = base_edge_values()
    for r in conn.execute("SELECT * FROM edges ORDER BY id"):
        if r["id"] not in measured:
            continue
        if [r["from_node"], r["to_node"]] != measured[r["id"]]:
            ends[str(r["id"])] = [r["from_node"], r["to_node"]]
        # Other fields changed on the admin page (status, distance, hints, one-way)
        changed = {f: r[f] for f in PATHWAY_FIELDS if r[f] != team[r["id"]][f]}
        if changed:
            changes[str(r["id"])] = changed
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"entrances": entrances, "pathway_ends": ends, "pathway_changes": changes,
                   "renamed": renamed, "removed": removed}, f, indent=1)


PATHWAY_FIELDS = ["distance_m", "one_way", "status", "direction_hint", "reverse_hint"]


def base_edge_values():
    """{edge id: {field: value}} for the measured pathways as written in campus_data.py."""
    from database.campus_data import EDGES, REVERSE_HINTS
    return {e[0]: {"distance_m": e[3], "one_way": e[4], "status": "available",
                   "direction_hint": e[5], "reverse_hint": REVERSE_HINTS.get(e[0])} for e in EDGES}


def write_waypoints_file(conn, path=None):
    """Save every traced pathway from the database to waypoints.json."""
    path = path or WAYPOINTS_PATH
    data = {}
    for row in conn.execute("SELECT id, waypoints FROM edges ORDER BY id"):
        points = json.loads(row["waypoints"] or "[]")
        if points:
            data[str(row["id"])] = points
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
