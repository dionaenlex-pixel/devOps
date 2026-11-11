"""Which steps of a route go through a bag check.

The bag checks are data (BAG_CHECKS in campus_data.py), so nobody has to tick
pathways by hand. Each time the graph is loaded, every pathway is checked in
both directions against them, using its traced line on the map, so the result
stays right when pins are moved or pathways are traced again.
"""

import math

from database.campus_data import BAG_CHECKS, OUTSIDE_PATHWAYS
from routing.hints import compass, heading, place_name

GATE = "Entrance/Exit"   # the category of the school gates


def closest_heading(spot, line):
    """(distance in px, compass heading, how far along the line) where `line`
    passes closest to `spot`. "How far along" is in px from the start of the line."""
    best = (math.inf, None, 0)
    walked = 0
    for (ax, ay), (bx, by) in zip(line, line[1:]):
        length2 = (bx - ax) ** 2 + (by - ay) ** 2
        if length2 == 0:
            continue
        t = max(0, min(1, ((spot[0] - ax) * (bx - ax) + (spot[1] - ay) * (by - ay)) / length2))
        d = math.dist(spot, (ax + t * (bx - ax), ay + t * (by - ay)))
        if d < best[0]:
            best = (d, compass(heading(bx - ax, by - ay)), walked + t * math.sqrt(length2))
        walked += math.sqrt(length2)
    return best


def checks_for_step(a, b, line, edge_id=None):
    """The bag checks passed walking from location a to location b along `line`
    (pathway `edge_id`), in the order you reach them. Each is a dict from
    BAG_CHECKS (name, kind, and maybe who / offer); a gate's check has kind "gate"."""
    found = []   # (when you reach it, check): at the start, along the way, or on arrival
    leave_places = {p for c in BAG_CHECKS if c["kind"] == "leave" for p in c["places"]}
    gate_checks = {p: c for c in BAG_CHECKS if c["kind"] == "gate" for p in c["places"]}
    # Coming in through a school gate (the Side Gate's check is one of BAG_CHECKS);
    # walking along the highway outside the gates isn't coming in
    if (a.get("category") == GATE and edge_id not in OUTSIDE_PATHWAYS
            and a["building"] not in leave_places):
        found.append((-1, gate_checks.get(a["building"]) or
                      {"name": f"bag check at {place_name(a['building'])}", "kind": "gate"}))
    for c in BAG_CHECKS:
        if c["kind"] == "gate":
            continue
        if c["kind"] == "pass":
            d, way, along = closest_heading((c["x"], c["y"]), line)
            if d <= c["radius"] and way in c["heading"]:
                found.append((along, c))
        elif c["kind"] == "arrive":
            if b["building"] in c["places"] and a["building"] not in c["places"]:
                found.append((math.inf, c))
        else:  # "leave": coming in from a gate or a parking area
            if (a["building"] in c["places"] and b["building"] not in c["places"]
                    and b.get("category") != GATE):
                found.append((-1, c))
    checks = []
    for _, c in sorted(found, key=lambda f: f[0]):
        if c["name"] not in [x["name"] for x in checks]:
            checks.append(c)
    return checks


def check_label(c):
    """'body scanner near Mabini Hall', or 'bag check at Recto Hall (senior high students going east)'."""
    return f"{c['name']} ({c['who']})" if c.get("who") else c["name"]


def mark_bag_checks(graph):
    """Give every pathway edge["bag_checks"] = {True: [...], False: [...]}:
    the bag checks passed walking it forwards (from_node -> to_node) and backwards."""
    edges = {id(e): e for links in graph.adj.values() for _, _, e, _ in links}
    for edge in edges.values():
        if edge.get("inside"):   # going through a building between its own doors
            edge["bag_checks"] = {True: [], False: []}
            continue
        a, b = graph.nodes[edge["from_node"]], graph.nodes[edge["to_node"]]
        line = [[a["map_x"], a["map_y"]], *(edge.get("waypoints") or []), [b["map_x"], b["map_y"]]]
        edge["bag_checks"] = {True: checks_for_step(a, b, line, edge["id"]),
                              False: checks_for_step(b, a, line[::-1], edge["id"])}
