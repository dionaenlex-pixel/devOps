"""Write direction hints from a pathway's traced line on the campus map.

The campus map has north at the top (checked against the team's GPS points:
"up" on the map is within 2 degrees of north), so compass directions come
straight from the map pixels. Places whose pins sit close beside the line
are named as landmarks ("passing Noli Me Tangere Hall on your left").
"""

import math
import re

COMPASS = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]
SMOOTH_PX = 12       # tracing wobbles smaller than this (about 4 m) are smoothed away
MIN_LEG_M = 15       # legs shorter than this are folded into the next one
STRAIGHT_DEG = 30    # smaller changes of direction count as going straight
LANDMARK_PX = 80     # a pin this close beside the line (about 30 m) is a landmark
PIN_GAP_PX = 60      # a trace ending farther than this (about 22 m) from its pin...
PX_PER_M = 2.7       # (the campus map is about 2.7 px per metre)
SHORT_TRACE = 0.2    # ...and covering under a fifth of the measured distance is unfinished

def simplify(line, tolerance=SMOOTH_PX):
    """Ramer-Douglas-Peucker: keep only the points that bend the line by more than `tolerance`."""
    if len(line) < 3:
        return line
    (x1, y1), (x2, y2) = line[0], line[-1]
    length = math.hypot(x2 - x1, y2 - y1) or 1
    # The point farthest from the straight line between the two ends
    far, far_i = -1, 0
    for i, (x, y) in enumerate(line[1:-1], start=1):
        d = abs((x2 - x1) * (y1 - y) - (x1 - x) * (y2 - y1)) / length
        if d > far:
            far, far_i = d, i
    if far <= tolerance:
        return [line[0], line[-1]]
    return simplify(line[:far_i + 1], tolerance)[:-1] + simplify(line[far_i:], tolerance)


SENTENCE_END = re.compile(r"(?<!\b[A-Z])\.\s+")   # not after an initial, as in "J.P. Laurel"


def sentences(text):
    """Split directions into sentences, without the final full stops."""
    return SENTENCE_END.split(text.strip().rstrip("."))


def heading(dx, dy):
    """Compass bearing in degrees (0 = north, 90 = east) of a move on the map."""
    return math.degrees(math.atan2(dx, -dy)) % 360  # map y grows downwards


def compass(deg):
    return COMPASS[round(deg / 45) % 8]


def turn_words(before, after):
    """'turn left', 'bear right', ... for a change of bearing."""
    change = (after - before + 540) % 360 - 180   # -180..180, positive = clockwise = right
    side = "right" if change > 0 else "left"
    if abs(change) < 60:
        return f"bear {side}"
    if abs(change) < 135:
        return f"turn {side}"
    if abs(change) < 170:
        return f"turn sharp {side}"
    return "turn back"


def legs_of(line, min_px):
    """Split a line into straight legs, as [dx, dy] vectors in map pixels.

    The line is smoothed first, legs shorter than min_px are folded into the
    next leg, and legs going almost the same way are joined, so only real
    turns are left.
    """
    points = simplify(line)
    legs = [[x2 - x1, y2 - y1] for (x1, y1), (x2, y2) in zip(points, points[1:]) if (x1, y1) != (x2, y2)]

    # 1. Fold short wiggles into the next leg (or the last one, at the end)
    long_legs = []
    carry = [0, 0]
    for dx, dy in legs:
        dx, dy = dx + carry[0], dy + carry[1]
        if math.hypot(dx, dy) < min_px:
            carry = [dx, dy]
        else:
            long_legs.append([dx, dy])
            carry = [0, 0]
    if not long_legs:
        return [carry]
    long_legs[-1] = [long_legs[-1][0] + carry[0], long_legs[-1][1] + carry[1]]

    # 2. Join legs that go (almost) the same way
    joined = [long_legs[0]]
    for dx, dy in long_legs[1:]:
        before, now = heading(*joined[-1]), heading(dx, dy)
        if abs((now - before + 540) % 360 - 180) < STRAIGHT_DEG or compass(now) == compass(before):
            joined[-1] = [joined[-1][0] + dx, joined[-1][1] + dy]
        else:
            joined.append([dx, dy])
    return joined


def landmark_beside(start, leg, places):
    """The closest place whose pin sits beside this leg, and on which side."""
    length2 = leg[0] ** 2 + leg[1] ** 2
    best = None
    for p in places:
        if p.get("category") == "Junction":
            continue   # walkway corners mean nothing to someone walking past
        px, py = p["map_x"] - start[0], p["map_y"] - start[1]
        t = (px * leg[0] + py * leg[1]) / length2   # how far along the leg, 0..1
        if not 0.15 < t < 0.85:
            continue
        cross = leg[0] * py - leg[1] * px            # > 0: on the right (map y points down)
        dist = abs(cross) / math.sqrt(length2)
        if dist <= LANDMARK_PX and (best is None or dist < best[0]):
            best = (dist, p["building"], "right" if cross > 0 else "left")
    return best and best[1:]


def write_hint(line, distance_m, destination, places, legs=None):
    """A hint for walking along `line` (map pixels, from its first point to its last).

    distance_m: the measured length; the traced line only sets the proportions.
    destination: what to call the end, e.g. "Mabini Hall at its back entrance".
    places: location dicts (building, map_x, map_y) that can be landmarks.
    legs: the line's straight legs, if already worked out (see hints_for_edge).
    """
    if legs is None:
        traced = sum(math.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in zip(line, line[1:])) or 1
        legs = legs_of(line, MIN_LEG_M * traced / distance_m)
    traced = sum(math.hypot(*leg) for leg in legs) or 1
    sentences = []
    point = list(line[0])
    named = set()
    prev = None
    for i, leg in enumerate(legs):
        bearing = heading(*leg)
        metres = max(5, round(distance_m * math.hypot(*leg) / traced / 5) * 5)
        if prev is None:
            text = f"Head {compass(bearing)} for about {metres} m"
        else:
            text = f"{turn_words(prev, bearing).capitalize()} and walk {compass(bearing)} for about {metres} m"
        mark = landmark_beside(point, leg, places)
        if mark and mark[0] not in named:
            named.add(mark[0])
            text += f", passing {place_name(mark[0])} on your {mark[1]}"
        if i == len(legs) - 1:
            text += f", until you reach {destination}"
        sentences.append(text + ".")
        point = [point[0] + leg[0], point[1] + leg[1]]
        prev = bearing
    return " ".join(sentences)


THE_WORDS = ("Gate", "Entrance", "Complex", "Center", "LRC", "House", "Lobby", "Junction", "Novitiate")  # "the CBEAM Gate"
THE_PLACES = ("Capilla", "Oval", "Hacienda")


def place_name(name):
    """A place's name as it reads in a sentence: 'the Capilla', 'the CBEAM Gate', 'Mabini Hall'."""
    if name in THE_PLACES or name.split()[-1] in THE_WORDS:
        return f"the {name}"
    return name


PLAIN_WORDS = {"Main", "Back", "Front", "Side", "Rear", "Ramp", "Upper", "Lower", "Left", "Right",
               "North", "South", "East", "West", "School", "Service", "Emergency",
               "Entrance", "Entrances", "Exit", "Exits", "Door", "Doors", "Gate"}


def lower_first(text):
    """'South Entrance' -> 'south entrance', keeping names: 'Exit facing Jaime Hilario Hall'
    -> 'exit facing Jaime Hilario Hall', 'CBEAM Entrance 2' -> 'CBEAM entrance 2'."""
    return " ".join(w.lower() if w in PLAIN_WORDS else w for w in text.split())


def destination_name(node, entrance_count):
    """'Mabini Hall at its back entrance', or just the place for a one-entrance building."""
    if entrance_count > 1 and node["entrance"]:
        return f"{place_name(node['building'])} at its {lower_first(node['entrance'])}"
    return place_name(node["building"])


def hints_for_edge(edge, nodes, note=None):
    """(direction_hint, reverse_hint) from a pathway's traced line.

    nodes: {id: location dict with building, entrance, map_x, map_y}.
    note: an extra sentence for both directions, e.g. "This way crosses the courtyard."
    Bag checks aren't written into hints: directions.py adds them to each step.
    """
    a, b = nodes[edge["from_node"]], nodes[edge["to_node"]]
    # Pins sit inside buildings and traces often start a little away from them,
    # so use the traced walkway itself; pin to pin only when it isn't traced
    if len(edge["waypoints"]) >= 2:
        line = list(edge["waypoints"])
        # An unfinished trace (e.g. only the bend at a junction, 6 m of an 83 m pathway)
        # would describe just that bit, so walk the rest straight to or from the pin.
        # A full trace that stops at a building's door, away from its pin, is left alone.
        traced_px = sum(math.dist(p, q) for p, q in zip(line, line[1:]))
        if traced_px < SHORT_TRACE * edge["distance_m"] * PX_PER_M:
            if math.dist(line[0], (a["map_x"], a["map_y"])) > PIN_GAP_PX:
                line.insert(0, [a["map_x"], a["map_y"]])
            if math.dist(line[-1], (b["map_x"], b["map_y"])) > PIN_GAP_PX:
                line.append([b["map_x"], b["map_y"]])
    else:
        line = [[a["map_x"], a["map_y"]], *edge["waypoints"], [b["map_x"], b["map_y"]]]
    counts = {}
    for n in nodes.values():
        counts[n["building"]] = counts.get(n["building"], 0) + 1
    # Landmarks: one pin per other building (its first entrance)
    places, seen = [], {a["building"], b["building"]}
    for n in sorted(nodes.values(), key=lambda n: n["id"]):
        if n["building"] not in seen:
            seen.add(n["building"])
            places.append(n)
    # Work out the legs once; walking back is the same legs, last first and turned around,
    # so the two hints always describe the same turns
    traced = sum(math.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in zip(line, line[1:])) or 1
    legs = legs_of(line, MIN_LEG_M * traced / edge["distance_m"])
    back_legs = [[-dx, -dy] for dx, dy in reversed(legs)]
    there = write_hint(line, edge["distance_m"], destination_name(b, counts[b["building"]]), places, legs)
    back = write_hint(line[::-1], edge["distance_m"], destination_name(a, counts[a["building"]]),
                      places, back_legs)
    if note:
        there, back = f"{there} {note}", f"{back} {note}"
    return there, back
