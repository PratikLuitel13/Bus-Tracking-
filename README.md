# College Bus Tracker (C++ / SQLite / Leaflet)

Architecture: Browser (Leaflet UI) <-> REST API (C++ backend) <-> SQLite (bus.db)

| Feature | Data structure | Endpoint |
|---|---|---|
| Stop autocomplete | Trie | /api/stops?q= |
| Bus lookup by id | Hash table | /api/buses |
| Nearest bus | k-d tree | /api/nearest?lat=&lon= |
| Next arrivals at a stop | Min-heap | /api/arrivals?stop= |
| Shortest stop-to-stop path | Graph + Dijkstra (min-heap) | /api/path?from=&to=&algo=dijkstra |
| Fewest-stops route | Graph + BFS (FIFO queue) | /api/path?from=&to=&algo=bfs |
| Deep path exploration | Graph + DFS (LIFO stack / recursion) | /api/path?from=&to=&algo=dfs |
| Multi-algorithm comparison | Dijkstra vs BFS vs DFS | /api/path?from=&to=&algo=compare |
| Network reachability tree | Graph BFS / DFS traversal | /api/traverse?stop=&algo= |
| Smoothed speed for ETA | Sliding window (deque) | used in ETA |

## Quick Start (Easiest Way to Run)

### Option 1: Desktop Shortcut (1-Click)
- Double-click the **Campus Bus Tracker** shortcut on your **Windows Desktop**.
- The server starts automatically and immediately opens `http://localhost:8080` in your default browser.
*(If you ever need to recreate the desktop shortcut, double-click `Create Desktop Shortcut.bat`)*

### Option 2: Batch Launcher
- Double-click **`Run Bus Tracker.bat`** (or `run.bat`) in the folder.
- Python is detected automatically, any stuck port is safely cleared, and your browser opens.

### Option 3: Silent Background Mode
- Double-click **`Run Bus Tracker (Silent).vbs`** to launch without keeping any command prompt window open.

### Stopping the Tracker
- Double-click **`Stop Bus Tracker.bat`** (or `stop.bat`) anytime to cleanly stop the server and free port 8080.
- Or simply press **`Q`** or `Ctrl+C` in the running server console.

---

## Interactive Console Controls
When the server console is open, you can press:
- **`[Enter]`** or **`[B]`** — Re-open the app in your web browser
- **`[R]`** — Reload database, buses, and routes
- **`[Q]`** — Safely stop server and exit

---

## Architecture & Advanced Setup (C++ Backend)
Architecture: Browser (Leaflet UI) <-> REST API (Python or C++ backend) <-> SQLite (bus.db)

1. Download `httplib.h` from github.com/yhirose/cpp-httplib into `third_party/`.
2. Install SQLite dev files (Linux: `sudo apt install libsqlite3-dev`; Windows: MSYS2 `pacman -S mingw-w64-x86_64-sqlite3`).
3. Create the database: `sqlite3 bus.db < db/schema.sql`
4. Build: `g++ -std=c++17 -O2 -pthread -Ithird_party backend/main.cpp -lsqlite3 -lws2_32 -o bustracker`
5. Run `./bustracker` and open http://localhost:8080

## Customise
Edit stops, routes, and buses in `db/schema.sql` (stop ids must be 0..n-1), then recreate `bus.db` or restart the server.
