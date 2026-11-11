"""Turn a list of graph steps into step-by-step walking directions."""

import math
import re

from database.campus_data import OUTSIDE_PATHWAYS, SKIPS_BODY_SCANNER
from routing.graph import compass_direction
from routing.hints import COMPASS, lower_first, place_name, sentences, turn_words

WALKING_SPEED_M_PER_MIN = 78  # about 1.3 m/s, an average walking pace
SPIKE_ANGLE_DEG = 35          # sharper than this means "walk out and straight back"
MAX_ROUTES = 3                # the shortest route plus up to 2 other ways
MAX_DETOUR = 1.3              # other ways at most 1.3 times as long as the shortest
MAX_DETOUR_BAG_CHECK = 2.0    # ...or twice as long, for the way through a required bag check
CANDIDATES = 10               # how many next-shortest routes to look through for other ways
MAX_SHARED = 0.5              # another way runs along a way already shown for at most half its length
SAME_WALKWAY_PX = 20          # lines closer than this (about 7 m) are on the same walkway
JOIN_PX = 60                  # two traces this close (about 20 m) are joined directly
WANDER_PX = 20                # another way may wander from the destination only this much
                              # (about 7 m) more than the shortest route does...
MIN_WANDER_PX = 60            # ...but up to 60 px (about 22 m) is always fine
BACKTRACK_PX = 22             # another way may walk back over its own line at most ~8 m
MAX_LOOP = 1.2                # inside another way, the part between any two places may be
                              # at most 1.2 times the shortest way between them
STAY_INSIDE = 1.2             # between two campus places, stay on campus unless going out onto
                              # the highway is more than 1.2 times shorter
GATE = "Entrance/Exit"        # the category of the school gates


def is_spike(before, pin, after):
    """True when the line goes to the pin and comes straight back the same way."""
    v1 = (before[0] - pin[0], before[1] - pin[1])
    v2 = (after[0] - pin[0], after[1] - pin[1])
    len1, len2 = math.hypot(*v1), math.hypot(*v2)
    if len1 == 0 or len2 == 0:
        return False
    cos_angle = (v1[0] * v2[0] + v1[1] * v2[1]) / (len1 * len2)
    return cos_angle > math.cos(math.radians(SPIKE_ANGLE_DEG))


def remove_spikes(line):
    """Drop every point where the line goes out and comes straight back.

    Pins sit inside buildings, and traces often start or end a little away from
    their pins, so joining them can draw sharp out-and-back detours on the map.
    Dropping one point can leave a new spike behind, so repeat until none are left.
    The first and last points (where the route starts and ends) always stay.
    """
    line = [p for i, p in enumerate(line) if i == 0 or p != line[i - 1]]
    i = 1
    while i < len(line) - 1:
        if is_spike(line[i - 1], line[i], line[i + 1]):
            del line[i]
            i = max(1, i - 1)  # the point before may be a spike now
        else:
            i += 1
    return line


def has_loop(graph, steps, distances):
    """True when part of a route is a pointless detour: between two places on it,
    it walks more than MAX_LOOP times the shortest way between those two places
    (e.g. going round through St. Mutien Marie and the Hacienda instead of
    straight along Recto Hall). The route as a whole isn't checked, only its parts.
    `distances` caches Graph.distances_from() for each place."""
    places = [steps[0][0]] + [s[1] for s in steps]
    walked = [0.0]
    for s in steps:
        walked.append(walked[-1] + s[2]["distance_m"])
    last = len(places) - 1

    def doors(i):
        # The start and the destination count as their whole building (any entrance)
        return graph.entrances(places[i]) if i in (0, last) else [places[i]]

    for i in range(last + 1):
        for door in doors(i):
            if door not in distances:
                distances[door] = graph.distances_from(door)
        for j in range(i + 1, last + 1):
            if i == 0 and j == last:
                continue   # the whole route: that's what MAX_DETOUR is for
            shortest = min(distances[a].get(b, math.inf) for a in doors(i) for b in doors(j))
            if walked[j] - walked[i] > MAX_LOOP * shortest + 1:
                return True
    return False


def walks_back(line, limit_px=BACKTRACK_PX):
    """True when a route walks back over ground it already covered (a U-turn): more than
    `limit_px` of its line comes back within 14 px of a part walked over 40 px earlier.
    Checked every 10 px along the line."""
    pts = []
    for p, q in zip(line, line[1:]):
        n = max(1, int(math.dist(p, q) // 10))
        pts += [(p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n) for k in range(n)]
    walked, back = [0.0], 0.0
    for i in range(1, len(pts)):
        walked.append(walked[-1] + math.dist(pts[i], pts[i - 1]))
        if any(walked[i] - walked[j] > 40 and math.dist(pts[i], pts[j]) < 14 for j in range(i)):
            back += math.dist(pts[i], pts[i - 1])
            if back > limit_px:
                return True
    return False


def wander(line):
    """How far a route walks away from its destination: the most it ever gets
    farther from the end of `line` than the closest it had already been (map px,
    checked every 10 px). A route that heads the wrong way and comes back scores high."""
    goal = line[-1]
    closest, worst = math.inf, 0
    for (ax, ay), (bx, by) in zip(line, line[1:] + [goal]):
        n = max(1, int(math.dist((ax, ay), (bx, by)) // 10))
        for k in range(n):
            d = math.dist((ax + (bx - ax) * k / n, ay + (by - ay) * k / n), goal)
            closest = min(closest, d)
            worst = max(worst, d - closest)
    return worst


TURN_BACK_RE = re.compile(r"(^|\. )Turn back and head")


def turns_back(route):
    """True when a route turns back on itself at a place along the way, e.g. walking
    up to the Capilla only to head back down the way it came. Fine for the shortest
    route if that's the only way, but not offered as another way."""
    return any(TURN_BACK_RE.search(s["text"]) for s in route["steps"][1:])


SHORT_LAST_STEP_M = 15
LAST_TURN_RE = re.compile(
    r"^(Turn sharp (?:left|right)|Turn back) and head (\w+) for about (\d+) m, until you reach ([^.]+)\.")


def short_last_turn(text):
    """'Turn sharp right and head northeast for about 10 m, until you reach Gregorio Zara Hall.'
    reads oddly for the last few metres, so say where the destination is instead:
    'Turn sharp right. Gregorio Zara Hall is about 10 m ahead, to the northeast.'"""
    m = LAST_TURN_RE.match(text)
    if not m or int(m.group(3)) > SHORT_LAST_STEP_M:
        return text
    turn, way, metres, place = m.groups()
    return f"{turn}. {capitalize(place)} is about {metres} m ahead, to the {way}." + text[m.end():]


WAY_RE = re.compile(r"\b(Head|walk) (northeast|northwest|southeast|southwest|north|south|east|west)\b")


def last_direction(text):
    """The compass direction a step's directions end with ('…walk west for…' -> 'west')."""
    found = WAY_RE.findall(text)
    return found[-1][1] if found else None


def continue_from(previous_way, text):
    """Start a step from where the last one left off: 'Head west…' becomes
    'Continue west…' when you're already walking west, or 'Turn left and head
    south…' when the direction changes."""
    m = re.match(r"Head (\w+)", text)
    if not previous_way or not m:
        return text
    way = m.group(1)
    if way == previous_way:
        return f"Continue {way}" + text[m.end():]
    turn = turn_words(COMPASS.index(previous_way) * 45, COMPASS.index(way) * 45)
    return f"{turn[0].upper() + turn[1:]} and head {way}" + text[m.end():]


def traces_meet(point, next_step):
    """True when `point` (the end of one traced pathway) is within JOIN_PX of where
    the next step's trace starts, walking in the next step's direction."""
    _, _, edge, forward = next_step
    points = edge.get("waypoints") or []
    if not points:
        return False
    first = points[0] if forward else points[-1]
    return math.dist(point, first) <= JOIN_PX


def entrance_text(graph, node, verb):
    """'Enter Mabini Hall through its back entrance.', or None for a one-entrance place."""
    if len(graph.entrances(node["id"])) < 2:
        return None
    entrance = lower_first(node["entrance"] or "main entrance")
    return f"{verb} {place_name(node['building'])} through its {entrance}."


def bag_check_text(checks):
    """'You pass through the body scanner near Mabini Hall.' for each bag check on a step,
    or 'Senior high students going east pass through the bag check at Recto Hall.'"""
    return " ".join(f"{c['who'][0].upper() + c['who'][1:]} pass through the {c['name']}." if c.get("who")
                    else f"You pass through the {c['name']}." for c in checks)


def step_note(step):
    """What sets a step apart, for labels: the pathway's own note
    ('goes through the parking lot'), else the required bag check it goes through
    ('through the body scanner near Mabini Hall'), else None."""
    for s in sentences(step["text"]):
        if s.startswith("This way "):
            return s[len("This way "):]
    if step.get("required_check"):
        return f"through the {step['required_check']}"
    return None


def capitalize(text):
    return text[0].upper() + text[1:] if text else text


def through_required_check(edge, forward):
    """True for a step through a bag check marked "offer" (the body scanner):
    one people are required to go through, so a way through it is always offered."""
    return any(c.get("offer") for c in edge.get("bag_checks", {}).get(forward, []))


def uses_required_check(steps):
    return any(through_required_check(s[2], s[3]) for s in steps)


def skips_body_scanner(steps):
    """True when a route takes a way that skips the body scanner (SKIPS_BODY_SCANNER)."""
    return any(s[2]["id"] in SKIPS_BODY_SCANNER and s[3] for s in steps)


def distance_to_line(p, line):
    """Pixels from point p to the nearest part of `line`."""
    best = math.inf
    for (ax, ay), (bx, by) in zip(line, line[1:]):
        length2 = (bx - ax) ** 2 + (by - ay) ** 2
        t = 0 if length2 == 0 else max(0, min(1, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / length2))
        best = min(best, math.dist(p, (ax + t * (bx - ax), ay + t * (by - ay))))
    return best


def shared_part(line, other):
    """How much of `line` (0 to 1) runs along `other` on the map, checked every 10 px.
    Compares the drawn lines, so two ways down the same walkway count as the same
    even when they are made of different pathways."""
    points = []
    for (ax, ay), (bx, by) in zip(line, line[1:]):
        n = max(1, int(math.dist((ax, ay), (bx, by)) // 10))
        points += [(ax + (bx - ax) * k / n, ay + (by - ay) * k / n) for k in range(n)]
    if not points:
        return 1
    return sum(distance_to_line(p, other) <= SAME_WALKWAY_PX for p in points) / len(points)


def build_directions(graph, start, goal, merge_junctions=True):
    """Find routes between the buildings of `start` and `goal` and describe them.

    Any entrance of the start building can be used, and each route ends at an
    entrance of the destination building. The shortest route is returned, with
    up to MAX_ROUTES - 1 other ways in "alternatives": the next shortest routes
    that aren't near-copies of a way already picked (at most MAX_SHARED of
    their line runs along it on the map), don't head the wrong way (they wander
    from the destination at most WANDER_PX more than the shortest does), have
    no pointless loop inside (see has_loop) and aren't longer than MAX_DETOUR
    times the shortest. If the shortest route takes a way that skips the body
    scanner (the parking lot way), the best way through the scanner is always
    one of the others (if it isn't longer than MAX_DETOUR_BAG_CHECK times the
    shortest), for people who have to go through it. Between two places that
    aren't gates, the route stays on campus unless going out onto the highway is
    more than STAY_INSIDE times shorter (and then no way goes out onto it).
    Returns None when no available path connects the two places.
    """
    starts, goals = graph.entrances(start), graph.entrances(goal)
    routes = graph.k_shortest_paths(starts, goals, CANDIDATES)
    if not routes:
        return None
    # Don't walk out one gate and back in another just to save a few metres
    if (GATE not in (graph.nodes[start].get("category"), graph.nodes[goal].get("category"))
            and any(s[2]["id"] in OUTSIDE_PATHWAYS for s in routes[0][1])):
        inside = graph.shortest_path_between(starts, goals, skip_edges=OUTSIDE_PATHWAYS)
        if inside and inside[0] <= routes[0][0] * STAY_INSIDE:
            routes = [inside] + [r for r in routes
                                 if not any(s[2]["id"] in OUTSIDE_PATHWAYS for s in r[1])]
    shortest = routes[0][0]
    chosen = [describe_route(graph, *routes[0], start, goal)]
    allowed_wander = max(MIN_WANDER_PX, wander(chosen[0]["line"]) + WANDER_PX)
    distances = {}   # Dijkstra from each place, shared by the loop checks below
    for total, steps in routes[1:]:
        if len(chosen) == MAX_ROUTES or total > shortest * MAX_DETOUR:
            break
        if has_loop(graph, steps, distances):
            continue   # goes round somewhere it could walk straight
        route = describe_route(graph, total, steps, start, goal)
        # Not a near-copy of a way already picked, not heading the wrong way, no U-turn
        if (all(shared_part(route["line"], r["line"]) <= MAX_SHARED for r in chosen)
                and wander(route["line"]) <= allowed_wander and not walks_back(route["line"])
                and not turns_back(route)):
            chosen.append(route)

    if skips_body_scanner(routes[0][1]) and not any(uses_required_check(r["_steps"]) for r in chosen):
        through = graph.shortest_path_using(starts, goals, through_required_check)
        if through and through[0] <= shortest * MAX_DETOUR_BAG_CHECK:
            route = describe_route(graph, *through, start, goal)
            # Not if it heads the wrong way. (No loop check: going the longer way through
            # the scanner instead of the parking lot is the whole point of this way.)
            if wander(route["line"]) <= allowed_wander:
                if len(chosen) == MAX_ROUTES:
                    chosen.pop()   # it takes the place of the last other way
                chosen.append(route)
                chosen[1:] = sorted(chosen[1:], key=lambda r: r["total_m"])

    for r in chosen:
        del r["_steps"]
    best = chosen[0]
    best["alternatives"] = chosen[1:]
    # Routes through the same places differ in a pathway, so add what that step does
    shown = [best]
    for route in best["alternatives"]:
        if any(r["via"] == route["via"] for r in shown):
            used = {s["text"] for r in shown for s in r["steps"]}
            different = next((s for s in route["steps"] if s["text"] not in used), None)
            note = (different and step_note(different)) or "by a different pathway"
            route["via"] = f"{route['via']} · {note}" if route["via"].startswith("via ") else capitalize(note)
        shown.append(route)
    if merge_junctions:
        for r in shown:
            r["steps"] = merge_junction_steps(graph, r)
    return best


def merge_junction_steps(graph, route):
    """Join each step that ends at a walkway junction onto the next step, so every
    step ends at a place people know. Junctions are only corners where pathways meet:
    "until you reach the G. Zara Road Junction" means nothing to someone walking.
    The joined step keeps every pathway it covers in "edge_ids"."""
    ends = [graph.nodes[p["id"]] for p in route["path"][1:]]   # where each step ends
    merged, carry = [], None
    for step, end in zip(route["steps"], ends):
        step = dict(step, edge_ids=[step["edge_id"]])
        if carry:
            step["text"] = f"{carry['text']} {step['text']}"
            step["distance_m"] = round(carry["distance_m"] + step["distance_m"], 1)
            step["bag_checks"] = carry["bag_checks"] + step["bag_checks"]
            step["required_check"] = carry["required_check"] or step["required_check"]
            step["edge_ids"] = carry["edge_ids"] + step["edge_ids"]
            step["edge_id"] = carry["edge_id"]
            step["from"] = carry["from"]
            carry = None
        if end.get("category") == "Junction" and step is not None and end is not ends[-1]:
            step["text"] = step["text"].replace(f", until you reach {place_name(end['building'])}", "")
            carry = step
        else:
            merged.append(step)
    if carry:
        merged.append(carry)
    return merged


def describe_route(graph, total, steps, start, goal):
    """Step-by-step directions and the map line for one route."""
    if steps:
        start, goal = steps[0][0], steps[-1][1]  # the entrances actually used

    first, last = graph.nodes[start], graph.nodes[goal]
    path = [first] + [graph.nodes[to_id] for _, to_id, _, _ in steps]
    line = [[first["map_x"], first["map_y"]]]  # map pixels for drawing the route
    instructions = []
    seen_checks = set()
    last_way = None   # the compass direction the previous step ended walking in
    for i, (from_id, to_id, edge, forward) in enumerate(steps):
        a, b = graph.nodes[from_id], graph.nodes[to_id]
        # Traced waypoints run from from_node to to_node, so flip them when walking backwards
        points = edge.get("waypoints") or []
        line.extend(points if forward else list(reversed(points)))
        # Pins sit inside buildings. When this pathway's trace and the next one's meet
        # (within JOIN_PX), go straight from one walkway to the next instead of drawing
        # into the building and back out. If they don't meet, go through the pin:
        # joining them directly would cut straight across buildings.
        if not (points and i + 1 < len(steps) and traces_meet(line[-1], steps[i + 1])):
            line.append([b["map_x"], b["map_y"]])
        if forward:
            text = edge["direction_hint"]
        elif edge.get("reverse_hint"):
            text = edge["reverse_hint"]
        else:
            # The stored hint describes the opposite direction, so make a simple one
            way = compass_direction(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
            text = f"Walk {way} from {place_name(a['building'])} to {place_name(b['building'])}."
        # Carry on from the step before: "Continue west…" or "Turn left and head south…"
        next_way = last_way
        last_way = last_direction(text)
        if i > 0:
            text = continue_from(next_way, text)
        # The destination isn't something you "pass": you walk with it beside you, then go in
        goal_name = place_name(last["building"])
        text = text.replace(f"passing {goal_name} on your", f"with {goal_name} on your")
        if i == len(steps) - 1:
            text = short_last_turn(text)
        already_outside = i > 0 and steps[i - 1][2]["id"] in OUTSIDE_PATHWAYS
        if edge["id"] in OUTSIDE_PATHWAYS and a.get("category") == "Entrance/Exit" and not already_outside:
            text = f"Go out through {place_name(a['building'])}. {text}"
        checks = edge.get("bag_checks", {}).get(forward, [])
        if i < len(steps) - 1:
            # Only going into a building is checked ("arrive"), not walking past it
            checks = [c for c in checks if c["kind"] != "arrive"]
        if i > 0 and steps[i - 1][2]["id"] not in OUTSIDE_PATHWAYS:
            # A gate's check is at the street: walking through the gate area from
            # inside campus (e.g. through the College Lobby) isn't coming in
            checks = [c for c in checks if c["kind"] != "gate"]
        # Each bag check is mentioned once per route, the first time you reach it
        checks = [c for c in checks if c["name"] not in seen_checks]
        seen_checks.update(c["name"] for c in checks)
        # Checks where you come in (gates, the Side Gate) are said first, the rest after
        at_start = [c for c in checks if c["kind"] in ("gate", "leave")]
        later = [c for c in checks if c["kind"] not in ("gate", "leave")]
        if at_start:
            text = bag_check_text(at_start) + " " + text
        if later:
            text += " " + bag_check_text(later)
        instructions.append({
            "edge_id": edge["id"],   # so the admin trace page can open this pathway
            "from": a["name"],
            "to": b["name"],
            "distance_m": round(edge["distance_m"], 1),
            "text": text,
            "bag_checks": [c["name"] for c in checks],
            "required_check": next((c["name"] for c in checks if c.get("offer")), None),
            "everyone_checked": any(not c.get("who") for c in checks),
        })

    # A short label to tell routes apart: the places passed, or the pathway's note
    passed = []
    for n in path[1:-1]:
        if n.get("category") == "Junction":
            continue   # walkway junctions aren't places people know by name
        if n["building"] not in passed and n["building"] not in (first["building"], last["building"]):
            passed.append(n["building"])
    if passed:
        via = "via " + ", ".join(place_name(p) for p in passed)
    else:
        via = capitalize((step_note(instructions[0]) if instructions else None) or "direct pathway")

    return {
        "from": first["building"],
        "to": last["building"],
        "via": via,
        # Tagged "Bag check" when everyone on this route goes through one
        "bag_check": any([s.pop("everyone_checked") for s in instructions]),
        "leave": entrance_text(graph, first, "Leave") if steps else None,
        "arrive": entrance_text(graph, last, "Enter") or f"Arrive at {place_name(last['building'])}.",
        "total_m": round(total, 1),
        "minutes": max(1, round(total / WALKING_SPEED_M_PER_MIN)),
        "path": [{"id": n["id"], "name": n["name"]} for n in path],
        "line": remove_spikes(line),
        "steps": instructions,
        "_steps": steps,   # for build_directions; removed before the route is sent
    }
