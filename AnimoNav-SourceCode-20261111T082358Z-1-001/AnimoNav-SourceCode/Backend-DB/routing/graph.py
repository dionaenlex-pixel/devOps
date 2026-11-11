"""Campus graph (adjacency list) and Dijkstra's shortest-path algorithm."""

import heapq
import math


class Graph:
    def __init__(self):
        self.nodes = {}      # node id -> node dict (name, latitude, ...)
        self.adj = {}        # node id -> list of (neighbor id, distance, edge dict, forward)
        self.buildings = {}  # building name -> ids of its entrances

    def add_node(self, node):
        # A location with no building given is a building with one entrance
        node.setdefault("building", node["name"])
        node.setdefault("entrance", None)
        self.nodes[node["id"]] = node
        self.adj.setdefault(node["id"], [])
        self.buildings.setdefault(node["building"], []).append(node["id"])

    def entrances(self, node_id):
        """Every entrance of the building this location belongs to."""
        return self.buildings[self.nodes[node_id]["building"]]

    def add_edge(self, edge):
        """Add a pathway. Paths that are not available are left out of routing."""
        if edge.get("status", "available") != "available":
            return
        a, b, d = edge["from_node"], edge["to_node"], edge["distance_m"]
        # forward=True means the walk follows the edge as written (from_node -> to_node)
        self.adj[a].append((b, d, edge, True))
        if not edge.get("one_way"):
            self.adj[b].append((a, d, edge, False))

    def shortest_path(self, start, goal):
        """Dijkstra's algorithm between two locations. See shortest_path_between."""
        return self.shortest_path_between([start], [goal])

    def shortest_path_between(self, starts, goals, skip_nodes=(), skip_edges=()):
        """Dijkstra's algorithm from any of `starts` to the nearest of `goals`.

        Used for buildings with several entrances: every start entrance goes
        in the queue at distance 0, and the search stops at the first goal
        entrance taken off the queue, which is the closest one.
        skip_nodes / skip_edges (edge ids) are left out; k_shortest_paths uses them.

        Returns (total_distance, steps) where each step is
        (from_id, to_id, edge, forward), or None if no goal can be reached.
        """
        for node in [*starts, *goals]:
            if node not in self.nodes:
                raise KeyError("Unknown location")
        goals = set(goals)
        starts = [s for s in starts if s not in skip_nodes]

        dist = {s: 0.0 for s in starts}
        prev = {}  # node id -> (previous node id, edge, forward)
        visited = set()
        queue = [(0.0, s) for s in starts]
        reached = None

        while queue:
            d, node = heapq.heappop(queue)
            if node in visited:
                continue
            visited.add(node)
            if node in goals:
                reached = node
                break
            for neighbor, weight, edge, forward in self.adj[node]:
                if neighbor in skip_nodes or edge["id"] in skip_edges:
                    continue
                new_d = d + weight
                if new_d < dist.get(neighbor, math.inf):
                    dist[neighbor] = new_d
                    prev[neighbor] = (node, edge, forward)
                    heapq.heappush(queue, (new_d, neighbor))

        if reached is None:
            return None

        # Walk back from the goal to rebuild the path; start entrances have no prev
        steps = []
        node = reached
        while node in prev:
            before, edge, forward = prev[node]
            steps.append((before, node, edge, forward))
            node = before
        steps.reverse()
        return dist[reached], steps

    def distances_from(self, start):
        """Dijkstra's algorithm without a goal: {place id: shortest distance from start}
        for every place that can be reached."""
        dist = {start: 0.0}
        visited = set()
        queue = [(0.0, start)]
        while queue:
            d, node = heapq.heappop(queue)
            if node in visited:
                continue
            visited.add(node)
            for neighbor, weight, _, _ in self.adj[node]:
                if d + weight < dist.get(neighbor, math.inf):
                    dist[neighbor] = d + weight
                    heapq.heappush(queue, (d + weight, neighbor))
        return dist

    def k_shortest_paths(self, starts, goals, k):
        """Yen's algorithm: up to k shortest routes that don't visit a place twice.

        Each new route copies the start (the "root") of a route already found,
        then leaves it at a "spur" place by a pathway the found routes with that
        same root didn't take, and finishes with Dijkstra.
        Returns a list of (total_distance, steps), shortest first.
        """
        best = self.shortest_path_between(starts, goals)
        if best is None:
            return []
        found = [best]
        candidates = []  # heap of (distance, tie-breaker, steps)
        seen = {route_key(best[1])}
        counter = 0

        while len(found) < k:
            _, last = found[-1]
            for i in range(len(last)):
                root = last[:i]
                spur = last[i][0]
                # Pathways that routes sharing this root take next are off limits
                skip_edges = {steps[i][2]["id"] for _, steps in found
                              if len(steps) > i and route_key(steps[:i]) == route_key(root)}
                if i == 0:
                    # No root yet, so the route may leave by any start entrance
                    spur_starts, skip_nodes = starts, set()
                else:
                    # The root's own places are off limits (no loops), and so are
                    # the other start entrances (you'd just leave by that one)
                    spur_starts = [spur]
                    skip_nodes = {s[0] for s in root} | (set(starts) - {spur})
                result = self.shortest_path_between(spur_starts, goals, skip_nodes, skip_edges)
                if result is None:
                    continue
                steps = root + result[1]
                if route_key(steps) in seen:
                    continue
                seen.add(route_key(steps))
                counter += 1
                total = sum(s[2]["distance_m"] for s in steps)
                heapq.heappush(candidates, (total, counter, steps))
            if not candidates:
                break
            total, _, steps = heapq.heappop(candidates)
            found.append((total, steps))
        return found

    def shortest_path_using(self, starts, goals, must_use):
        """Shortest route that walks at least one step where must_use(edge, forward) is true.

        For each such step (a -> b), the route is the shortest way from a start
        to a, then the step, then the shortest way from b to a goal. Routes that
        would visit a place twice are skipped. Returns (total, steps) or None.
        """
        best = None
        for a, links in self.adj.items():
            for b, weight, edge, forward in links:
                if not must_use(edge, forward):
                    continue
                before = self.shortest_path_between(starts, [a])
                after = self.shortest_path_between([b], goals)
                if before is None or after is None:
                    continue
                steps = before[1] + [(a, b, edge, forward)] + after[1]
                places = [steps[0][0]] + [s[1] for s in steps]
                if len(places) != len(set(places)):
                    continue
                total = before[0] + weight + after[0]
                if best is None or total < best[0]:
                    best = (total, steps)
        return best

    def nearest_node(self, lat, lon):
        """The location closest to a GPS position, and its distance in meters.
        Walkway junctions are skipped: they aren't places to start from."""
        places = [n for n in self.nodes.values() if n.get("category") != "Junction"]
        best = min(places, key=lambda n: haversine(lat, lon, n["latitude"], n["longitude"]))
        return best, haversine(lat, lon, best["latitude"], best["longitude"])


def route_key(steps):
    """The pathways a route walks, in order, so two routes can be compared."""
    return tuple((s[2]["id"], s[3]) for s in steps)


def haversine(lat1, lon1, lat2, lon2):
    """Straight-line distance in meters between two GPS coordinates."""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def compass_direction(lat1, lon1, lat2, lon2):
    """Rough compass direction (north, northeast, ...) from point 1 to point 2."""
    dy = lat2 - lat1
    dx = (lon2 - lon1) * math.cos(math.radians(lat1))
    degrees = (math.degrees(math.atan2(dx, dy)) + 360) % 360
    names = ["north", "northeast", "east", "southeast",
             "south", "southwest", "west", "northwest"]
    return names[round(degrees / 45) % 8]
