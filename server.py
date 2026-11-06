"""
Campus Bus Tracker — Python backend
Mirrors the C++ backend exactly. Same REST API endpoints, same logic.
Run: python server.py
Then open: http://localhost:8080
"""
import sqlite3, math, random, heapq, threading, time, json, os, sys, signal, subprocess, webbrowser
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ─────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────

class TrieNode:
    def __init__(self):
        self.children = {}
        self.ids = []

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word, id_):
        node = self.root
        for ch in word.lower():
            node = node.children.setdefault(ch, TrieNode())
            node.ids.append(id_)

    def prefix(self, q):
        node = self.root
        for ch in q.lower():
            if ch not in node.children:
                return []
            node = node.children[ch]
        return node.ids


class KDTree:
    """2-D kd-tree storing (lat, lon, bus_id)."""
    def __init__(self, pts):
        self.tree = self._build(list(pts), 0)

    def _build(self, pts, depth):
        if not pts:
            return None
        axis = depth % 2
        pts.sort(key=lambda p: p[axis])
        mid = len(pts) // 2
        return {
            'pt': pts[mid],
            'left': self._build(pts[:mid], depth + 1),
            'right': self._build(pts[mid + 1:], depth + 1),
        }

    def nearest(self, lat, lon):
        best = [None, float('inf')]
        def search(node, depth):
            if node is None:
                return
            pt = node['pt']
            d = (pt[0] - lat)**2 + (pt[1] - lon)**2
            if d < best[1]:
                best[0] = pt[2]; best[1] = d
            axis = depth % 2
            diff = (lat if axis == 0 else lon) - pt[axis]
            near, far = (node['left'], node['right']) if diff <= 0 else (node['right'], node['left'])
            search(near, depth + 1)
            if diff**2 < best[1]:
                search(far, depth + 1)
        search(self.tree, 0)
        return best[0]


def haversine(a, b):
    R = 6371
    t = math.pi / 180
    dl = (b['lat'] - a['lat']) * t
    dn = (b['lon'] - a['lon']) * t
    h = math.sin(dl/2)**2 + math.cos(a['lat']*t)*math.cos(b['lat']*t)*math.sin(dn/2)**2
    return 2 * R * math.asin(math.sqrt(h))

# ─────────────────────────────────────────────────────────────────────
# Globals
# ─────────────────────────────────────────────────────────────────────
SIM = 10          # simulation speed-up
DB_PATH = os.path.join(os.path.dirname(__file__), 'bus.db')

stops  = []       # list of {id, name, lat, lon}
routes = {}       # route_id -> [stop_id, ...]
adj    = {}       # stop_id -> [(neighbour_id, km)]
buses  = {}       # bus_id  -> bus_dict
trie   = Trie()
lock   = threading.Lock()

# ─────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def load_data():
    con = get_db()
    # Stops
    for row in con.execute("SELECT id,name,lat,lon FROM stops ORDER BY id"):
        s = dict(row)
        stops.append(s)
        trie.insert(s['name'], s['id'])

    # Adjacency list skeleton
    for s in stops:
        adj[s['id']] = []

    # Routes
    for row in con.execute("SELECT route_id,stop_id FROM route_stops ORDER BY route_id,seq"):
        r, s = row['route_id'], row['stop_id']
        routes.setdefault(r, []).append(s)

    # Build adjacency graph (bi-directional, deduplicated)
    for sid_list in routes.values():
        n = len(sid_list)
        for i in range(n):
            a = stops[sid_list[i]]
            b = stops[sid_list[(i + 1) % n]]
            d = haversine(a, b)
            if not any(nbr == b['id'] for nbr, _ in adj[a['id']]):
                adj[a['id']].append((b['id'], d))
            if not any(nbr == a['id'] for nbr, _ in adj[b['id']]):
                adj[b['id']].append((a['id'], d))

    # Buses
    for row in con.execute("SELECT id,plate,route_id,base_speed FROM buses"):
        b = dict(row)
        r = routes[b['route_id']]
        start = stops[r[0]]
        b.update(lat=start['lat'], lon=start['lon'],
                 speed=b['base_speed'], seg=0, frac=0.0, hist=[])
        buses[b['id']] = b
    con.close()

# ─────────────────────────────────────────────────────────────────────
# Simulation
# ─────────────────────────────────────────────────────────────────────
def seg_len(r, k):
    return haversine(stops[r[k]], stops[r[(k + 1) % len(r)]])

def avg_speed(b):
    return sum(b['hist']) / len(b['hist']) if b['hist'] else b['base_speed']

def eta(b, stop_id):
    r = routes[b['route_id']]
    try:
        j = r.index(stop_id)
    except ValueError:
        return -1
    m = len(r)
    d = (1 - b['frac']) * seg_len(r, b['seg'])
    k = (b['seg'] + 1) % m
    while k != j:
        d += seg_len(r, k)
        k = (k + 1) % m
    return d / avg_speed(b) * 60 / SIM

def simulate():
    rng = random.Random(42)
    tick = 0
    con = get_db()
    while True:
        time.sleep(1)
        with lock:
            log_stmts = []
            for b in buses.values():
                b['speed'] = max(10.0, b['base_speed'] + rng.uniform(-6, 6))
                b['hist'].append(b['speed'])
                if len(b['hist']) > 5:
                    b['hist'].pop(0)
                r = routes[b['route_id']]
                d = b['speed'] / 3600 * SIM
                while d > 0:
                    slen = seg_len(r, b['seg'])
                    left = (1 - b['frac']) * slen
                    if d >= left:
                        d -= left
                        b['seg'] = (b['seg'] + 1) % len(r)
                        b['frac'] = 0.0
                    else:
                        b['frac'] += d / slen
                        d = 0
                a = stops[r[b['seg']]]
                c = stops[r[(b['seg'] + 1) % len(r)]]
                b['lat'] = a['lat'] + (c['lat'] - a['lat']) * b['frac']
                b['lon'] = a['lon'] + (c['lon'] - a['lon']) * b['frac']
                log_stmts.append(
                    (b['id'], b['lat'], b['lon'], b['speed'])
                )
            tick += 1
            if tick % 10 == 0:
                try:
                    con.executemany(
                        "INSERT INTO position_log(bus_id,lat,lon,speed) VALUES(?,?,?,?)",
                        log_stmts
                    )
                    con.commit()
                except Exception:
                    pass

# ─────────────────────────────────────────────────────────────────────
# Graph Search Algorithms: Dijkstra, BFS, DFS
# ─────────────────────────────────────────────────────────────────────

def dijkstra(src, dst):
    """
    Dijkstra's Algorithm:
    Finds the shortest distance path in a weighted graph using a Min-Heap.
    Time Complexity: O((V + E) log V).
    """
    dist = {s['id']: float('inf') for s in stops}
    prev = {s['id']: -1 for s in stops}
    dist[src] = 0
    heap = [(0, src)]
    visited_order = []
    visited_set = set()

    while heap:
        du, u = heapq.heappop(heap)
        if u in visited_set:
            continue
        visited_set.add(u)
        visited_order.append(u)
        if u == dst:
            break
        for v, w in adj.get(u, []):
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                prev[v] = u
                heapq.heappush(heap, (dist[v], v))

    if dist[dst] == float('inf'):
        return None, None, visited_order

    path = []
    v = dst
    while v != -1:
        path.append(v)
        v = prev[v]
    path.reverse()
    return dist[dst], path, visited_order


def bfs(src, dst):
    """
    Breadth-First Search (BFS):
    Explores the graph level-by-level using a FIFO queue.
    Guarantees the path with minimum number of stops/hops.
    Time Complexity: O(V + E).
    """
    if src == dst:
        return 0.0, [src], [src]

    queue = deque([src])
    visited = {src}
    prev = {src: -1}
    visited_order = []
    found = False

    while queue:
        u = queue.popleft()
        visited_order.append(u)
        if u == dst:
            found = True
            break
        for v, _w in adj.get(u, []):
            if v not in visited:
                visited.add(v)
                prev[v] = u
                queue.append(v)

    if not found and dst not in prev:
        return None, None, visited_order

    path = []
    v = dst
    while v != -1:
        path.append(v)
        v = prev[v]
    path.reverse()

    km = sum(next(w for nbr, w in adj[path[i]] if nbr == path[i+1]) for i in range(len(path)-1))
    return km, path, visited_order


def dfs(src, dst):
    """
    Depth-First Search (DFS):
    Explores as deep as possible along each branch before backtracking.
    Uses recursive backtracking / LIFO stack.
    Time Complexity: O(V + E).
    """
    if src == dst:
        return 0.0, [src], [src]

    visited = set()
    visited_order = []
    path = []

    def rec(u):
        visited.add(u)
        visited_order.append(u)
        if u == dst:
            path.append(u)
            return True
        for v, _w in adj.get(u, []):
            if v not in visited:
                if rec(v):
                    path.append(u)
                    return True
        return False

    if not rec(src):
        return None, None, visited_order

    path.reverse()
    km = sum(next(w for nbr, w in adj[path[i]] if nbr == path[i+1]) for i in range(len(path)-1))
    return km, path, visited_order


def traverse_bfs(src):
    """Returns stops grouped by hop levels and exploration order from src."""
    visited = {src: 0}
    queue = deque([src])
    levels = {}
    order = []
    while queue:
        u = queue.popleft()
        lvl = visited[u]
        levels.setdefault(lvl, []).append(u)
        order.append(u)
        for v, _w in adj.get(u, []):
            if v not in visited:
                visited[v] = lvl + 1
                queue.append(v)
    return {'levels': levels, 'order': order}


def traverse_dfs(src):
    """Returns stops visited during DFS traversal tree from src."""
    visited = set()
    order = []
    def rec(u):
        visited.add(u)
        order.append(u)
        for v, _w in adj.get(u, []):
            if v not in visited:
                rec(v)
    rec(src)
    return {'order': order}


def format_path_result(km, path, visited_order, algo):
    stop_map = {s['id']: s for s in stops}
    info = {
        'dijkstra': {
            'name': 'Dijkstra',
            'full_name': "Dijkstra's Shortest Path",
            'ds': 'Min-Heap (Priority Queue)',
            'complexity': 'O((V + E) log V)',
            'focus': 'Minimum Road Distance (km)',
            'color': '#1a73e8'
        },
        'bfs': {
            'name': 'BFS',
            'full_name': 'Breadth-First Search',
            'ds': 'Queue (FIFO)',
            'complexity': 'O(V + E)',
            'focus': 'Fewest Stops / Hops',
            'color': '#137333'
        },
        'dfs': {
            'name': 'DFS',
            'full_name': 'Depth-First Search',
            'ds': 'Stack / Recursion (LIFO)',
            'complexity': 'O(V + E)',
            'focus': 'Exhaustive Deep Exploration',
            'color': '#e37400'
        }
    }.get(algo, {
        'name': algo.upper(),
        'full_name': algo.upper(),
        'ds': 'Graph Traversal',
        'complexity': 'O(V + E)',
        'focus': 'Graph Search',
        'color': '#1a73e8'
    })

    if path is None:
        return {
            'km': 0,
            'stops': [],
            'stop_ids': [],
            'hops': 0,
            'algo': algo,
            'algo_name': info['name'],
            'full_name': info['full_name'],
            'ds': info['ds'],
            'complexity': info['complexity'],
            'focus': info['focus'],
            'color': info['color'],
            'visited_order': [stop_map[sid]['name'] for sid in visited_order if sid in stop_map],
            'visited_ids': visited_order,
            'visited_count': len(visited_order),
            'found': False
        }

    return {
        'km': round(km, 2),
        'stops': [stop_map[sid]['name'] for sid in path],
        'stop_ids': path,
        'hops': max(0, len(path) - 1),
        'algo': algo,
        'algo_name': info['name'],
        'full_name': info['full_name'],
        'ds': info['ds'],
        'complexity': info['complexity'],
        'focus': info['focus'],
        'color': info['color'],
        'visited_order': [stop_map[sid]['name'] for sid in visited_order if sid in stop_map],
        'visited_ids': visited_order,
        'visited_count': len(visited_order),
        'found': True
    }

# ─────────────────────────────────────────────────────────────────────
# HTTP Handler
# ─────────────────────────────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), 'frontend')
MIME = {
    '.html': 'text/html', '.css': 'text/css',
    '.js': 'application/javascript', '.json': 'application/json',
    '.png': 'image/png', '.ico': 'image/x-icon',
}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence default logging

    def send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        qs     = parse_qs(parsed.query)

        # ── API routes ─────────────────────────────────────────────
        if path == '/api/stops':
            q = qs.get('q', [''])[0]
            with lock:
                if q:
                    ids = trie.prefix(q)
                    seen, result = set(), []
                    for i in ids:
                        if i not in seen:
                            seen.add(i)
                            result.append(stops[i])
                else:
                    result = stops
            self.send_json(result)

        elif path == '/api/routes':
            result = []
            for rid, sids in routes.items():
                result.append({
                    'id': rid,
                    'stops': [{'lat': stops[s]['lat'], 'lon': stops[s]['lon']} for s in sids]
                })
            self.send_json(result)

        elif path == '/api/buses':
            with lock:
                result = [{
                    'id': b['id'], 'plate': b['plate'],
                    'route': b['route_id'],
                    'lat': b['lat'], 'lon': b['lon'],
                    'speed': round(avg_speed(b), 1)
                } for b in buses.values()]
            self.send_json(result)

        elif path == '/api/nearest':
            try:
                lat = float(qs['lat'][0])
                lon = float(qs['lon'][0])
            except (KeyError, ValueError):
                self.send_json(None); return
            with lock:
                pts = [(b['lat'], b['lon'], b['id']) for b in buses.values()]
                if not pts:
                    self.send_json(None); return
                kd = KDTree(pts)
                bid = kd.nearest(lat, lon)
                b = buses[bid]
                km = haversine({'lat': lat, 'lon': lon}, {'lat': b['lat'], 'lon': b['lon']})
                self.send_json({
                    'id': b['id'], 'plate': b['plate'],
                    'route': b['route_id'],
                    'lat': b['lat'], 'lon': b['lon'],
                    'speed': round(avg_speed(b), 1),
                    'km': round(km, 4)
                })

        elif path == '/api/arrivals':
            try:
                stop_id = int(qs['stop'][0])
            except (KeyError, ValueError):
                self.send_json([]); return
            with lock:
                heap = []
                for b in buses.values():
                    e = eta(b, stop_id)
                    if e >= 0:
                        heapq.heappush(heap, (e, b['id']))
                result = []
                while heap:
                    e, bid = heapq.heappop(heap)
                    b = buses[bid]
                    result.append({
                        'bus': bid, 'plate': b['plate'],
                        'route': b['route_id'],
                        'eta': round(e, 1)
                    })
            self.send_json(result)

        elif path == '/api/path':
            try:
                src = int(qs['from'][0])
                dst = int(qs['to'][0])
            except (KeyError, ValueError):
                self.send_json(None); return

            algo = qs.get('algo', ['dijkstra'])[0].lower()

            if algo == 'compare':
                d_km, d_path, d_vis = dijkstra(src, dst)
                b_km, b_path, b_vis = bfs(src, dst)
                f_km, f_path, f_vis = dfs(src, dst)
                d_res = format_path_result(d_km, d_path, d_vis, 'dijkstra')
                b_res = format_path_result(b_km, b_path, b_vis, 'bfs')
                f_res = format_path_result(f_km, f_path, f_vis, 'dfs')
                self.send_json({
                    'compare': True,
                    'dijkstra': d_res,
                    'bfs': b_res,
                    'dfs': f_res,
                    'km': d_res['km'],
                    'stops': d_res['stops'],
                    'hops': d_res['hops']
                })
            elif algo == 'bfs':
                km, res_path, visited_order = bfs(src, dst)
                self.send_json(format_path_result(km, res_path, visited_order, 'bfs'))
            elif algo == 'dfs':
                km, res_path, visited_order = dfs(src, dst)
                self.send_json(format_path_result(km, res_path, visited_order, 'dfs'))
            else:  # dijkstra default
                km, res_path, visited_order = dijkstra(src, dst)
                self.send_json(format_path_result(km, res_path, visited_order, 'dijkstra'))

        elif path == '/api/traverse':
            try:
                stop_id = int(qs['stop'][0])
            except (KeyError, ValueError):
                self.send_json(None); return
            algo = qs.get('algo', ['bfs'])[0].lower()
            stop_map = {s['id']: s for s in stops}
            if stop_id not in stop_map:
                self.send_json(None); return
            if algo == 'dfs':
                res = traverse_dfs(stop_id)
                self.send_json({
                    'algo': 'dfs',
                    'root': stop_map[stop_id],
                    'order': [stop_map[i] for i in res['order'] if i in stop_map]
                })
            else:
                res = traverse_bfs(stop_id)
                levels_formatted = {
                    str(lvl): [stop_map[i] for i in sids if i in stop_map]
                    for lvl, sids in res['levels'].items()
                }
                self.send_json({
                    'algo': 'bfs',
                    'root': stop_map[stop_id],
                    'levels': levels_formatted,
                    'order': [stop_map[i] for i in res['order'] if i in stop_map]
                })

        # ── Static files ───────────────────────────────────────────
        else:
            if path == '/':
                path = '/index.html'
            file_path = os.path.join(FRONTEND_DIR, path.lstrip('/'))
            if os.path.isfile(file_path):
                ext = os.path.splitext(file_path)[1]
                mime = MIME.get(ext, 'application/octet-stream')
                with open(file_path, 'rb') as f:
                    body = f.read()
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', len(body))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

# ─────────────────────────────────────────────────────────────────────
# Entry point & Server Management
# ─────────────────────────────────────────────────────────────────────
class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def free_port(port):
    """Detect and terminate any stale process holding the specified port on Windows."""
    try:
        out = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
        current_pid = os.getpid()
        killed_any = False
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3].upper() == "LISTENING":
                try:
                    pid = int(parts[4])
                    if pid != current_pid and pid > 0:
                        print(f"[*] Port {port} occupied by PID {pid}. Terminating stale process...")
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        killed_any = True
                except ValueError:
                    continue
        if killed_any:
            time.sleep(0.8)
        return killed_any
    except Exception:
        return False

def start_server(preferred_port=8080):
    port = preferred_port
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            server = ReusableHTTPServer(('0.0.0.0', port), Handler)
            return server, port
        except OSError as e:
            if getattr(e, 'winerror', None) == 10048 or 'Address already in use' in str(e) or '10048' in str(e):
                if attempt == 0:
                    print(f"[*] Port {port} is in use. Attempting to free it...")
                    if free_port(port):
                        continue
                print(f"[-] Port {port} is unavailable. Trying port {port + 1}...")
                port += 1
            else:
                raise
    raise RuntimeError(f"Could not bind to any port between {preferred_port} and {port}")

if __name__ == '__main__':
    try:
        if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    print("\n" + "=" * 58)
    print("           CAMPUS BUS TRACKER - STARTING UP")
    print("=" * 58)

    # Step 1 — Create DB if it doesn't exist
    if not os.path.exists(DB_PATH):
        schema = os.path.join(os.path.dirname(__file__), 'db', 'schema.sql')
        con = sqlite3.connect(DB_PATH)
        con.executescript(open(schema).read())
        con.close()
        print("[1/3] Database created (bus.db from schema.sql)")
    else:
        print("[1/3] Database ready (bus.db found)")

    # Step 2 — Load data and start simulation thread
    load_data()
    threading.Thread(target=simulate, daemon=True).start()
    print("[2/3] Simulation active (live buses on route)")

    # Step 3 — Start HTTP server with auto-port freeing
    server, port = start_server(8080)
    url = f"http://localhost:{port}"
    print(f"[3/3] HTTP Server listening on port {port}")
    print()
    print("=" * 58)
    print("   [+] CAMPUS BUS TRACKER IS LIVE AND READY!")
    print(f"   >> Local URL: {url}")
    print("=" * 58)
    print("  Controls:")
    print("   [Enter] or [B] -> Open in Web Browser")
    print("   [R]           -> Reload Database & Routes")
    print("   [Q]           -> Stop Server & Exit")
    print("=" * 58 + "\n")

    # Auto-open browser after 0.8s
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    def shutdown_signal(sig=None, frame=None):
        print("\n[*] Stopping Campus Bus Tracker...")
        try:
            threading.Thread(target=server.shutdown, daemon=True).start()
        except Exception:
            pass
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, shutdown_signal)
        signal.signal(signal.SIGTERM, shutdown_signal)
    except Exception:
        pass

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    if sys.stdin and hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
        try:
            while server_thread.is_alive():
                cmd = input().strip().lower()
                if cmd in ('q', 'quit', 'exit', 'stop'):
                    shutdown_signal()
                    break
                elif cmd in ('b', 'open', 'browser', ''):
                    print(f"[*] Opening browser: {url}")
                    webbrowser.open(url)
                elif cmd in ('r', 'restart', 'reload'):
                    print("[*] Reloading database and bus positions...")
                    with lock:
                        load_data()
                    print("[OK] Reload successful!")
                elif cmd in ('h', 'help', '?'):
                    print("  [Enter]/[B]: Open Browser | [R]: Reload Data | [Q]: Quit Server")
        except (KeyboardInterrupt, EOFError):
            shutdown_signal()
    else:
        try:
            server_thread.join()
        except KeyboardInterrupt:
            shutdown_signal()


