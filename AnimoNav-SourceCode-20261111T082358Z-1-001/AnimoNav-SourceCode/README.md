# AnimoNav: walking directions around De La Salle Lipa

Team 7 · Data Structures and Algorithms final project
Python 3.13 + Flask (backend), SQLite (database), HTML/CSS/JavaScript + Leaflet (UI)

Live site: https://animonav.pythonanywhere.com

## Folders

| Folder | What's in it |
|---|---|
| `UI-UX/templates/` | The HTML pages: the map page (`index.html`) and the admin pages |
| `UI-UX/static/` | The page scripts, the styles, and the campus map image |
| `Backend-DB/app.py` | The web server: the pages, the JSON API (`/api/route`, `/api/locations`) and the admin actions |
| `Backend-DB/routing/` | **Routing module.** `graph.py`: the campus graph (adjacency list), Dijkstra's algorithm with a priority queue, and the next-shortest routes. `directions.py`: picks the routes to show and writes step-by-step directions. `hints.py`: turns a traced line into words ("Head west for about 60 m…"). `bagchecks.py`: works out which bag checks each step passes. |
| `Backend-DB/database/` | **Database module.** `schema.sql`: the tables. `campus_data.py`: the 30 places and the pathways the team measured. The `.json` files: traced walkways, moved pins, added pathways and entrances. `db.py`: opens the database and loads the graph. `seed.py` / `rebuild_db.py` / `add_admin.py`: set up the database and the admin accounts. |
| `Backend-DB/tests/` | Automated tests (64) |

## Run it

Needs Python 3.13. From the `Backend-DB` folder:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r ../requirements.txt
python -m database.seed
python app.py
```

`database.seed` asks for an admin password. Then open http://127.0.0.1:5000, and http://127.0.0.1:5000/admin for the admin pages (username `admin`).

After 3 wrong passwords in a row, that admin account is locked for 24 hours; the other accounts still work. `python -m database.add_admin --unlock USERNAME` unlocks it early.

Run the tests (also from `Backend-DB`):

```
python -m unittest discover tests
```

Installed packages (`.venv`), caches and the generated database (`database/instance/`) aren't included; the commands above recreate them.
