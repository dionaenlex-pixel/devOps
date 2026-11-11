"""DLSL campus data collected by Team 7.

NODES: (id, name, category, latitude, longitude, description)
EDGES: (id, from_id, to_id, distance_m, one_way, direction_hint)
MAP_POSITIONS: node id -> (x, y) pixel position on static/campus-map.webp
               (2000 x 1006, x from the left edge, y from the top edge)
ENTRANCES: node id -> (building, entrance) for buildings with more than one
           entrance. Every other location is a building with one entrance,
           named after itself.
REVERSE_HINTS: edge id -> hint for walking a two-way pathway backwards
               (to_id -> from_id). Hints were written from the traced lines
               with hints.py, plus the team's landmark notes.
BAG_CHECKS: the bag checks marked on the team's campus map (see bagchecks.py).
            Every school gate also has a bag check for people coming in.

IDs run from 1 with no gaps. (They were renumbered: in the team's first Google
Doc, location 10 and edge 22 were skipped, so ids after those are one lower here.)
Locations 31-34 are extra entrances; their pins and GPS points are placeholders.
"""

# Pathways outside the gates, along J.P. Laurel Highway: walking them isn't entering campus
OUTSIDE_PATHWAYS = {20, 51}

# Buildings routes may walk through, in one door and out another: the College Lobby passage
# through Claro M. Recto Hall and BB Hall. Other buildings are walked around.
WALK_THROUGH = {"Claro M. Recto Hall", "BB Hall (St. Br. Benilde)"}

# Pathways that skip the body scanner, walked from_id -> to_id (the parking lot way,
# "for those who don't need bag check"). When the shortest route uses one, the way
# through the body scanner is offered too.
SKIPS_BODY_SCANNER = {49, 88}   # 88 is the part of 49 from Diokno to the G. Zara road junction

# x, y: the red circle on the campus map (pixels). Who is checked:
#   "pass":   walking past the spot (within `radius` px) heading one of `heading`
#   "arrive": going into one of `places` (only when it's where the route ends)
#   "leave":  coming from one of `places` into the school (not to a gate or another of `places`)
#   "gate":   coming in from the street through the gate in `places` (not going out)
# who:   only these people are checked (e.g. senior high students); everyone if left out
# offer: if the shortest route skips it, a way through it is always offered too
BAG_CHECKS = [
    {"name": "bag check at the Main Gate entrance", "x": 1324, "y": 906,
     "kind": "gate", "places": ["Main Gate / College Lobby"]},
    {"name": "bag check by the Sports Complex parking", "x": 535, "y": 595,
     "kind": "pass", "radius": 35, "heading": ["south"]},
    {"name": "bag check at CBEAM Hall", "x": 541, "y": 657,
     "kind": "arrive", "places": ["CBEAM Hall"]},
    {"name": "body scanner near Mabini Hall", "x": 848, "y": 703,
     "kind": "pass", "radius": 35, "heading": ["west", "northwest", "southwest"], "offer": True},
    {"name": "bag check at Recto Hall's north end", "x": 1200, "y": 633,
     "who": "senior high students going east",
     "kind": "pass", "radius": 30, "heading": ["east", "northeast", "southeast"]},
    {"name": "bag check at Recto Hall's south end", "x": 1272, "y": 866,
     "who": "senior high students going east",
     "kind": "pass", "radius": 30, "heading": ["east", "northeast", "southeast"]},
    {"name": "bag check by the Side Gate", "x": 1533, "y": 703,
     "kind": "leave", "places": ["Side Gate", "Feldgrau Pay Parking"]},
]

ENTRANCES = {
    17: ("Mabini Hall", "Front Entrance"),
    31: ("Mabini Hall", "Back Entrance"),
    32: ("Mabini Hall", "Ramp Entrance"),
    25: ("BB Hall (St. Br. Benilde)", "Main Entrance"),
    33: ("BB Hall (St. Br. Benilde)", "Exit facing Jaime Hilario Hall"),
    6: ("Claro M. Recto Hall", "South Entrance"),
    34: ("Claro M. Recto Hall", "North Entrance"),
}

MAP_POSITIONS = {
    1: (1335, 935), 2: (1235, 912), 3: (623, 955), 4: (1795, 705), 5: (800, 405),
    6: (1268, 770), 7: (1238, 555), 8: (1080, 575), 9: (940, 715), 10: (920, 582),
    11: (905, 495), 12: (1035, 355), 13: (745, 535), 14: (685, 625), 15: (712, 690),
    16: (615, 690), 17: (722, 790), 18: (480, 700), 19: (360, 810), 20: (335, 505),
    21: (390, 190), 22: (1450, 400), 23: (1590, 465), 24: (1470, 610), 25: (1630, 600),
    26: (1435, 695), 27: (1430, 750), 28: (1432, 797), 29: (1425, 860), 30: (1665, 815),
    31: (695, 815), 32: (725, 755), 33: (1560, 575), 34: (1285, 730),
}

NODES = [
    (1, "Main Gate / College Lobby", "Entrance/Exit", 13.941592423967222, 121.14771924968586,
     "The main entrance to De La Salle Lipa along J.P. Laurel Highway."),
    (2, "Chez Entrance", "Entrance/Exit", 13.9415126900429, 121.14724684545959,
     "Entrance point along J.P. Laurel Highway, west of the Main Gate."),
    (3, "CBEAM Gate", "Entrance/Exit", 13.94147150075672, 121.14543341391347,
     "Entrance/Exit access point near the CBEAM area."),
    (4, "Side Gate", "Entrance/Exit", 13.942182304545769, 121.14936929373435,
     "Alternate eastern campus entrance along San Lorenzo St."),
    (5, "De La Salle Brothers' Novitiate", "Religious", 13.943177023259006, 121.14615515106979,
     "Formation house of the De La Salle Brothers (FSC), where new members begin their religious "
     "life, with a memorial cloister and burial site for departed Brothers. Reached by the road "
     "past Gregorio Zara Hall."),
    (6, "Claro M. Recto Hall – South Entrance", "Building", 13.94206110199869, 121.14758981355624,
     "Academic building and administrative facility."),
    (7, "Capilla", "Church", 13.942676305098367, 121.14752419455179,
     "Sacred chapel space located at the heart of the campus."),
    (8, "SENTRUM", "Gymnasium", 13.942456468128354, 121.14692200199816,
     "Cultural and sports hub multi-purpose covered gymnasium."),
    (9, "Chez Rafael", "Canteen", 13.942327610367833, 121.14662897066104,
     "Hotel, café, and canteen facility."),
    (10, "Diokno Hall", "Building", 13.942529357336486, 121.1464640148061,
     "Administrative building."),
    (11, "College LRC", "Library", 13.942846945747341, 121.14645462707392,
     "Primary Learning Resource Center and library facility."),
    (12, "Gen. M. Malvar", "Building", 13.94335391582777, 121.1467470899481,
     "Campus facility located north of SENTRUM."),
    (13, "Gregorio Zara Hall", "Building", 13.942819089834156, 121.14582149107501,
     "IT building equipped with computer laboratories."),
    (14, "Noli Me Tangere Hall", "Building", 13.942289385859198, 121.14566382014789,
     "SHS academic building."),
    (15, "El Filibusterismo Hall", "Building", 13.942538788295868, 121.14558725878683,
     "SHS academic twin facility."),
    (16, "Student Center", "Canteen", 13.942326906595301, 121.14536970322352,
     "Student activities office and food center."),
    (17, "Mabini Hall – Front Entrance", "Building", 13.942020854904024, 121.14602919218942,
     "Multi-purpose building housing Nursing and CITE."),
    (18, "CBEAM Hall", "Building", 13.942349713314687, 121.14501115347248,
     "Dedicated facility for Business and Accountancy programs."),
    (19, "Brother's House", "Building", 13.941822967710735, 121.14456395129778,
     "Residence facility for the De La Salle Brothers."),
    (20, "Sports Complex", "Gymnasium", 13.94278835345918, 121.14442450362782,
     "Major multi-purpose indoor gymnasium complex."),
    (21, "Retreat Complex", "Recreational", 13.944097560543211, 121.14451233544794,
     "Formation center with chapel, mess halls, and cabanas."),
    (22, "Oval", "Field", 13.942953221270878, 121.14804449919853,
     "Expansive outdoor track and athletic field."),
    (23, "St. Br. Jaime Hilario Hall", "Building", 13.94284371618488, 121.1482636823111,
     "JHS academic facility."),
    (24, "Senten (A, B, C)", "Covered Courts", 13.94256539125418, 121.1481538539294,
     "Academic and activity building cluster."),
    (25, "BB Hall – Main Entrance", "Canteen", 13.942462351729262, 121.14855533767134,
     "Campus canteen."),
    (26, "St. Mutien Marie Hall", "Building", 13.942303033334866, 121.14811681571796,
     "SHS academic building."),
    (27, "Hacienda", "Building", 13.942130229753827, 121.14791841821348,
     "Campus facility between St. Mutien Marie and St. Br. Miguel."),
    (28, "St. Br. Miguel Hall", "Building", 13.9419376770397, 121.14788535196273,
     "SHS campus operations building."),
    (29, "Br. Vernon Mabile Hall", "Building", 13.941696545764392, 121.14808904910896,
     "Historic campus building near the main entrance."),
    (30, "Feldgrau Pay Parking", "Parking", 13.941839617384002, 121.14895587639086,
     "Designated paid vehicle parking area."),
    (31, "Mabini Hall – Back Entrance", "Building", 13.94199, 121.14595,
     "Back entrance, used from CBEAM Hall, the Student Center side and the CBEAM Gate."),
    (32, "Mabini Hall – Ramp Entrance", "Building", 13.94210, 121.14600,
     "Ramp entrance between Noli and Fili Hall."),
    (33, "BB Hall – Exit facing Jaime Hilario Hall", "Canteen", 13.94253, 121.14852,
     "BB Hall exit facing St. Br. Jaime Hilario Hall."),
    (34, "Claro M. Recto Hall – North Entrance", "Building", 13.94215, 121.14762,
     "North end, near St. Mutien Marie Hall and the Capilla."),
]

EDGES = [
    (1, 1, 6, 57.43, 0, "Head north for about 35 m, until you reach Claro M. Recto Hall at its south entrance."),
    (2, 1, 8, 150.52, 0, "Head northwest for about 100 m. Turn left and walk west for about 50 m, until you reach SENTRUM at its main entrance. This way follows the main walkway."),
    (3, 6, 8, 108.11, 0, "Head west for about 110 m, until you reach SENTRUM at its main entrance. This way crosses the parking area."),
    (4, 8, 7, 86.81, 0, "Head east for about 85 m, until you reach the Capilla."),
    (5, 10, 8, 77.60, 0, "Head east for about 35 m, passing Chez Rafael on your right. Bear right and walk southeast for about 20 m. Bear left and walk east for about 25 m, until you reach SENTRUM at its main entrance."),
    (6, 10, 13, 190.70, 1, "Head west for about 25 m. Bear left and walk southwest for about 25 m. Bear right and walk west for about 45 m, passing Mabini Hall on your left. Turn right and walk north for about 60 m, passing El Filibusterismo Hall on your left. Turn right and walk northeast for about 30 m, until you reach Gregorio Zara Hall."),
    (7, 9, 1, 235.75, 0, "Head east for about 95 m, passing SENTRUM on your left. Turn right and walk southeast for about 140 m, until you reach the Main Gate / College Lobby. This way passes the parking area."),
    (8, 18, 16, 40.46, 0, "Head southeast for about 40 m, until you reach the Student Center."),
    (9, 18, 31, 100.85, 0, "Head southeast for about 50 m. Turn right and walk southwest for about 50 m, until you reach Mabini Hall at its back entrances."),
    (10, 15, 14, 45.90, 0, "Head northwest for about 45 m, until you reach Noli Me Tangere Hall. This way uses the connecting corridor between the two halls."),
    (11, 16, 32, 66.69, 0, "Head east for about 30 m. Turn right and walk south for about 40 m, passing El Filibusterismo Hall on your left, until you reach Mabini Hall at its ramp entrance. This way uses the ramp between Noli and Fili Hall."),
    (12, 34, 7, 65.97, 0, "Head northeast for about 65 m, until you reach the Capilla. This way follows the paved path."),
    (13, 34, 26, 36.51, 0, "Head east for about 45 m. Turn left and walk north for about 20 m. Turn right and walk east for about 50 m, until you reach St. Mutien Marie Hall."),
    (14, 8, 9, 66.81, 0, "Head west for about 65 m, until you reach Chez Rafael at its main entrances. This way crosses the courtyard."),
    (15, 10, 9, 22.01, 0, "Head southeast for about 25 m, until you reach Chez Rafael at its main entrances. This way crosses the pedestrian walkway."),
    (16, 18, 20, 109.52, 0, "Head north for about 70 m. Bear left and walk northwest for about 40 m, until you reach the Sports Complex."),
    (17, 26, 25, 97.46, 0, "Head east for about 55 m. Turn left and walk north for about 25 m. Turn right and walk east for about 20 m, until you reach BB Hall (St. Br. Benilde) at its main entrance."),
    (18, 33, 23, 46.56, 0, "Head northwest for about 20 m. Bear right and walk north for about 25 m, until you reach St. Br. Jaime Hilario Hall."),
    (19, 7, 22, 153.47, 0, "Head southwest for about 35 m. Turn sharp left and walk east for about 120 m, until you reach the Oval. This way passes Senten."),
    (20, 1, 2, 46.70, 0, "Head west for about 45 m, until you reach the Chez Entrance."),
    (21, 2, 9, 107.24, 0, "Head north for about 40 m. Turn left and walk west for about 50 m. Turn right and walk north for about 20 m, until you reach Chez Rafael at its back entrance."),
    (22, 9, 17, 88.25, 0, "Head west for about 65 m. Turn left and walk southeast for about 25 m, until you reach Mabini Hall at its front entrance."),
    (23, 1, 29, 25.43, 0, "Head east for about 60 m, until you reach Br. Vernon Mabile Hall. This way goes through the College Lobby."),
    (24, 29, 28, 20.55, 0, "Head north for about 50 m, until you reach St. Br. Miguel Hall. This way goes through the connection between the two buildings."),
    (25, 28, 6, 49.26, 0, "Head west for about 65 m, until you reach Claro M. Recto Hall at its south entrance."),
    (26, 28, 27, 39.76, 0, "Head north for about 70 m, until you reach the Hacienda."),
    (27, 27, 26, 16.92, 0, "Head north for about 45 m, until you reach St. Mutien Marie Hall. This way goes through the connection between the two buildings."),
    (28, 29, 30, 132.09, 0, "Head north for about 20 m. Turn right and walk east for about 20 m. Turn left and walk north for about 55 m, passing St. Mutien Marie Hall on your left. Turn right and walk southeast for about 35 m, until you reach Feldgrau Pay Parking at its school entrance. This way goes around the buildings."),
    (29, 30, 4, 69.56, 0, "Head east for about 70 m, until you reach the Side Gate."),
    (30, 4, 25, 113.50, 0, "Head north for about 115 m, until you reach BB Hall (St. Br. Benilde) at its main entrance."),
    (31, 24, 26, 55.17, 0, "Head east for about 35 m. Turn right and walk south for about 20 m, until you reach St. Mutien Marie Hall."),
    (32, 24, 25, 43.39, 0, "Head east for about 30 m. Turn left and walk north for about 25 m, until you reach BB Hall (St. Br. Benilde) at its main entrance. This way follows the covered walkway south of Senten."),
    (33, 24, 7, 112.26, 0, "Head west for about 100 m, until you reach the Capilla. This way follows the covered walkway south of Senten."),
    (34, 23, 22, 30.04, 0, "Head west for about 30 m, until you reach the Oval."),
    (35, 10, 11, 37.03, 0, "Head north for about 35 m, until you reach the College LRC."),
    (36, 11, 12, 157.82, 0, "Head east for about 25 m, passing Chez Rafael on your right. Turn left and walk north for about 135 m, until you reach Gen. M. Malvar."),
    (37, 8, 12, 122.16, 0, "Head west for about 30 m. Turn right and walk north for about 95 m, passing the College LRC on your left, until you reach Gen. M. Malvar. This way crosses the parking area."),
    (38, 11, 5, 158.24, 0, "Head southwest for about 45 m. Turn right and walk north for about 110 m, passing Diokno Hall on your right, until you reach the De La Salle Brothers' Novitiate."),
    (39, 5, 20, 258.28, 0, "Head south for about 55 m. Bear right and walk west for about 130 m, passing Gregorio Zara Hall on your right. Turn right and walk northwest for about 30 m. Bear left and walk west for about 45 m, until you reach the Sports Complex. This way follows the north road."),
    (40, 20, 21, 180.77, 0, "Head northeast for about 65 m. Turn left and walk north for about 115 m, until you reach the Retreat Complex. This way follows the road."),
    (41, 13, 14, 57.13, 0, "Head west for about 30 m. Turn left and walk south for about 30 m, until you reach Noli Me Tangere Hall."),
    (42, 14, 16, 31.16, 0, "Head southwest for about 30 m, passing El Filibusterismo Hall on your left, until you reach the Student Center."),
    (43, 15, 32, 80.97, 0, "Head north for about 80 m, until you reach Mabini Hall at its ramp entrance."),
    (44, 16, 3, 104.25, 0, "Head southeast for about 25 m. Bear right and walk south for about 80 m, until you reach the CBEAM Gate. This way follows the road."),
    (45, 3, 31, 31.65, 0, "Head northeast for about 30 m, until you reach Mabini Hall at its back entrances."),
    (46, 3, 19, 121.88, 0, "Head west for about 120 m, until you reach the Brother's House."),
    (47, 19, 18, 123.55, 0, "Head east for about 125 m, until you reach CBEAM Hall at its CBEAM entrance 2."),
    (48, 13, 10, 118.09, 1, "Head southeast for about 60 m. Bear left and walk east for about 55 m, until you reach Diokno Hall. This way crosses the parking lot."),
]

REVERSE_HINTS = {
    1: "Head south for about 35 m, until you reach the Main Gate / College Lobby.",
    2: "Head east for about 50 m. Turn right and walk southeast for about 100 m, until you reach the Main Gate / College Lobby. This way follows the main walkway.",
    3: "Head east for about 110 m, until you reach Claro M. Recto Hall at its north entrance. This way crosses the parking area.",
    4: "Head west for about 85 m, until you reach SENTRUM at its main entrance.",
    5: "Head west for about 25 m. Bear right and walk northwest for about 20 m, passing Chez Rafael on your left. Bear left and walk west for about 35 m, until you reach Diokno Hall.",
    7: "Head northwest for about 140 m. Turn left and walk west for about 95 m, passing SENTRUM on your right, until you reach Chez Rafael at its main entrances. This way passes the parking area.",
    8: "Head northwest for about 40 m, until you reach CBEAM Hall.",
    9: "Head northeast for about 50 m. Turn left and walk northwest for about 50 m, until you reach CBEAM Hall.",
    10: "Head southeast for about 45 m, until you reach El Filibusterismo Hall. This way uses the connecting corridor between the two halls.",
    11: "Head north for about 40 m, passing El Filibusterismo Hall on your right. Turn left and walk west for about 30 m, until you reach the Student Center. This way uses the ramp between Noli and Fili Hall.",
    12: "Head southwest for about 65 m, until you reach Claro M. Recto Hall at its north entrance. This way follows the paved path.",
    13: "Head west for about 50 m. Turn left and walk south for about 20 m. Turn right and walk west for about 45 m, until you reach Claro M. Recto Hall at its north entrance.",
    14: "Head east for about 65 m, until you reach SENTRUM at its main entrance. This way crosses the courtyard.",
    15: "Head northwest for about 25 m, until you reach Diokno Hall. This way crosses the pedestrian walkway.",
    16: "Head southeast for about 40 m. Bear right and walk south for about 70 m, until you reach CBEAM Hall.",
    17: "Head west for about 20 m. Turn left and walk south for about 25 m. Turn right and walk west for about 55 m, until you reach St. Mutien Marie Hall.",
    18: "Head south for about 25 m. Bear left and walk southeast for about 20 m, until you reach BB Hall (St. Br. Benilde) at its exit facing Jaime Hilario Hall.",
    19: "Head west for about 120 m. Turn sharp right and walk northeast for about 35 m, until you reach the Capilla. This way passes Senten.",
    20: "Head east for about 45 m, until you reach the Main Gate / College Lobby.",
    21: "Head south for about 20 m. Turn left and walk east for about 50 m. Turn right and walk south for about 40 m, until you reach the Chez Entrance.",
    22: "Head northwest for about 25 m. Turn right and walk east for about 65 m, until you reach Chez Rafael at its main entrances.",
    23: "Head west for about 60 m, until you reach the Main Gate / College Lobby. This way goes through the College Lobby.",
    24: "Head south for about 50 m, until you reach Br. Vernon Mabile Hall. This way goes through the connection between the two buildings.",
    25: "Head east for about 65 m, until you reach St. Br. Miguel Hall.",
    26: "Head south for about 70 m, until you reach St. Br. Miguel Hall.",
    27: "Head south for about 45 m, until you reach the Hacienda. This way goes through the connection between the two buildings.",
    28: "Head northwest for about 35 m. Turn left and walk south for about 55 m, passing St. Mutien Marie Hall on your right. Turn right and walk west for about 20 m. Turn left and walk south for about 20 m, until you reach Br. Vernon Mabile Hall. This way goes around the buildings.",
    29: "Head west for about 70 m, until you reach Feldgrau Pay Parking at its school entrance.",
    30: "Head south for about 115 m, until you reach the Side Gate.",
    31: "Head north for about 20 m. Turn left and walk west for about 35 m, until you reach Senten (A, B, C).",
    32: "Head south for about 25 m. Turn right and walk west for about 30 m, until you reach the Senten Walkway Junction. This way follows the covered walkway south of Senten.",
    33: "Head east for about 100 m, until you reach the Senten Walkway Junction. This way follows the covered walkway south of Senten.",
    34: "Head east for about 30 m, until you reach St. Br. Jaime Hilario Hall.",
    35: "Head south for about 35 m, until you reach Diokno Hall.",
    36: "Head south for about 135 m. Turn right and walk west for about 25 m, passing Chez Rafael on your left, until you reach the College LRC.",
    37: "Head south for about 95 m, passing the College LRC on your right. Turn left and walk east for about 30 m, until you reach SENTRUM at its main entrance. This way crosses the parking area.",
    38: "Head south for about 110 m, passing Diokno Hall on your left. Turn left and walk northeast for about 45 m, until you reach the College LRC.",
    39: "Head east for about 45 m. Bear right and walk southeast for about 30 m. Turn left and walk east for about 130 m, passing Gregorio Zara Hall on your left. Bear left and walk north for about 55 m, until you reach the De La Salle Brothers' Novitiate. This way follows the north road.",
    40: "Head south for about 115 m. Turn right and walk southwest for about 65 m, until you reach the Sports Complex. This way follows the road.",
    41: "Head north for about 30 m. Turn right and walk east for about 30 m, until you reach Gregorio Zara Hall.",
    42: "Head northeast for about 30 m, passing El Filibusterismo Hall on your right, until you reach Noli Me Tangere Hall.",
    43: "Head south for about 80 m, until you reach El Filibusterismo Hall.",
    44: "Head north for about 80 m. Bear left and walk northwest for about 25 m, until you reach the Student Center. This way follows the road.",
    45: "Head southwest for about 30 m, until you reach the CBEAM Gate.",
    46: "Head east for about 120 m, until you reach the CBEAM Gate.",
    47: "Head west for about 125 m, until you reach the Brother's House.",
}
