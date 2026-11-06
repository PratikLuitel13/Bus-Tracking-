// Bus tracker backend: C++17, cpp-httplib (HTTP) + SQLite (storage) + custom data structures.
#include "httplib.h"
#include <sqlite3.h>
#include <thread>
#include <mutex>
#include <deque>
#include <queue>
#include <sstream>
#include <iostream>
#include <iomanip>
#include <cmath>
#include <random>
#include "ds.h"
using namespace std;

const double SIM = 10;  // simulation speed-up so movement is visible
struct Stop { int id; string name; double lat, lon; };
struct Bus { int id=0; string plate; int route=0; double base=30, frac=0, lat=0, lon=0, speed=30; int seg=0; deque<double> hist; };

vector<Stop> stops;
vector<vector<int>> routes;                 // route id -> ordered stop ids (loop)
vector<vector<pair<int,double>>> adj;       // graph: stop -> (stop, km)
Trie trie;
HashTable<Bus> buses;
mutex mu;
sqlite3* db;

double hav(const Stop& a, const Stop& b) {
    const double R = 6371, t = 3.14159265358979 / 180;
    double dl = (b.lat-a.lat)*t, dn = (b.lon-a.lon)*t;
    double h = sin(dl/2)*sin(dl/2) + cos(a.lat*t)*cos(b.lat*t)*sin(dn/2)*sin(dn/2);
    return 2 * R * asin(sqrt(h));
}
double segLen(const vector<int>& r, int k) { return hav(stops[r[k]], stops[r[(k+1) % r.size()]]); }
double avgSpeed(const Bus& b) { double s = 0; for (double v : b.hist) s += v; return b.hist.empty() ? b.base : s / b.hist.size(); }
string esc(const string& s) { string o; for (char c : s) { if (c=='"' || c=='\\') o += '\\'; o += c; } return o; }

// ETA in minutes: distance along the route to the stop / moving-average speed
double eta(const Bus& b, int stop) {
    const auto& r = routes[b.route]; int m = r.size(), j = -1;
    for (int i = 0; i < m; i++) if (r[i] == stop) { j = i; break; }
    if (j < 0) return -1;
    double d = (1 - b.frac) * segLen(r, b.seg);
    for (int k = (b.seg + 1) % m; k != j; k = (k + 1) % m) d += segLen(r, k);
    return d / avgSpeed(b) * 60 / SIM;
}

void sql(const string& q, function<void(char**)> f) {
    auto cb = [](void* u, int, char** v, char**) { (*(function<void(char**)>*)u)(v); return 0; };
    char* e = nullptr;
    if (sqlite3_exec(db, q.c_str(), cb, &f, &e)) { cerr << "SQL: " << e << "\n"; sqlite3_free(e); }
}

void loadData() {
    sql("SELECT id,name,lat,lon FROM stops ORDER BY id", [](char** v) {
        stops.push_back({atoi(v[0]), v[1], stod(v[2]), stod(v[3])}); trie.insert(v[1], atoi(v[0])); });
    adj.resize(stops.size());
    sql("SELECT route_id,stop_id FROM route_stops ORDER BY route_id,seq", [](char** v) {
        size_t r = atoi(v[0]); if (routes.size() <= r) routes.resize(r + 1); routes[r].push_back(atoi(v[1])); });
    for (auto& r : routes) for (size_t i = 0; i < r.size(); i++) {
        int a = r[i], b = r[(i+1) % r.size()]; double d = hav(stops[a], stops[b]);
        auto hasEdge = [](int u, int v) {
            for (auto& e : adj[u]) if (e.first == v) return true;
            return false;
        };
        if (!hasEdge(a, b)) adj[a].push_back({b, d});
        if (!hasEdge(b, a)) adj[b].push_back({a, d});
    }
    sql("SELECT id,plate,route_id,base_speed FROM buses", [](char** v) {
        Bus b; b.id = atoi(v[0]); b.plate = v[1]; b.route = atoi(v[2]); b.base = b.speed = stod(v[3]);
        const Stop& s = stops[routes[b.route][0]]; b.lat = s.lat; b.lon = s.lon; buses.put(b.id, b); });
}

pair<double, vector<int>> runBFS(int src, int dst) {
    if (src == dst) return {0.0, {src}};
    int n = stops.size();
    vector<bool> vis(n, false);
    vector<int> prev(n, -1);
    queue<int> q;
    q.push(src);
    vis[src] = true;
    bool found = false;
    while (!q.empty()) {
        int u = q.front(); q.pop();
        if (u == dst) { found = true; break; }
        for (auto& e : adj[u]) {
            int v = e.first;
            if (!vis[v]) {
                vis[v] = true;
                prev[v] = u;
                q.push(v);
            }
        }
    }
    if (!found && prev[dst] == -1) return {-1.0, {}};
    vector<int> path;
    for (int v = dst; v != -1; v = prev[v]) path.push_back(v);
    reverse(path.begin(), path.end());
    double km = 0;
    for (size_t i = 0; i + 1 < path.size(); i++) {
        for (auto& e : adj[path[i]]) {
            if (e.first == path[i+1]) { km += e.second; break; }
        }
    }
    return {km, path};
}

bool dfsVisit(int u, int dst, vector<bool>& vis, vector<int>& path) {
    vis[u] = true;
    if (u == dst) { path.push_back(u); return true; }
    for (auto& e : adj[u]) {
        int v = e.first;
        if (!vis[v]) {
            if (dfsVisit(v, dst, vis, path)) {
                path.push_back(u);
                return true;
            }
        }
    }
    return false;
}

pair<double, vector<int>> runDFS(int src, int dst) {
    if (src == dst) return {0.0, {src}};
    int n = stops.size();
    vector<bool> vis(n, false);
    vector<int> path;
    if (!dfsVisit(src, dst, vis, path)) return {-1.0, {}};
    reverse(path.begin(), path.end());
    double km = 0;
    for (size_t i = 0; i + 1 < path.size(); i++) {
        for (auto& e : adj[path[i]]) {
            if (e.first == path[i+1]) { km += e.second; break; }
        }
    }
    return {km, path};
}

void simulate() {
    mt19937 g(42); uniform_real_distribution<double> jit(-6, 6); int tick = 0;
    for (;;) {
        this_thread::sleep_for(chrono::seconds(1));
        lock_guard<mutex> L(mu); ostringstream log;
        buses.each([&](int, Bus& b) {
            b.speed = max(10.0, b.base + jit(g));
            b.hist.push_back(b.speed); if (b.hist.size() > 5) b.hist.pop_front();
            const auto& r = routes[b.route]; double d = b.speed / 3600 * SIM;
            while (d > 0) {
                double len = segLen(r, b.seg), left = (1 - b.frac) * len;
                if (d >= left) { d -= left; b.seg = (b.seg + 1) % r.size(); b.frac = 0; }
                else { b.frac += d / len; d = 0; }
            }
            const Stop &a = stops[r[b.seg]], &c = stops[r[(b.seg + 1) % r.size()]];
            b.lat = a.lat + (c.lat - a.lat) * b.frac; b.lon = a.lon + (c.lon - a.lon) * b.frac;
            log << "INSERT INTO position_log(bus_id,lat,lon,speed) VALUES(" << b.id << "," << b.lat << "," << b.lon << "," << b.speed << ");";
        });
        if (++tick % 10 == 0) sql(log.str(), [](char**) {});   // persist every 10 s
    }
}

string busJson(const Bus& b) {
    ostringstream o; o << fixed << setprecision(6);
    o << "{\"id\":" << b.id << ",\"plate\":\"" << esc(b.plate) << "\",\"route\":" << b.route
      << ",\"lat\":" << b.lat << ",\"lon\":" << b.lon << ",\"speed\":" << setprecision(1) << avgSpeed(b) << "}";
    return o.str();
}

#define H [&](const httplib::Request& req, httplib::Response& res)
int main() {
    if (sqlite3_open("bus.db", &db)) { cerr << "Cannot open bus.db\n"; return 1; }
    loadData(); thread(simulate).detach();
    httplib::Server svr;
    svr.set_mount_point("/", "./frontend");

    svr.Get("/api/stops", H {                       // Trie autocomplete: ?q=prefix
        string q = req.get_param_value("q"); vector<int> ids;
        if (q.empty()) for (auto& s : stops) ids.push_back(s.id); else ids = trie.prefix(q);
        ostringstream o; o << fixed << setprecision(6) << "[";
        for (size_t i = 0; i < ids.size(); i++) { auto& s = stops[ids[i]];
            o << (i ? "," : "") << "{\"id\":" << s.id << ",\"name\":\"" << esc(s.name) << "\",\"lat\":" << s.lat << ",\"lon\":" << s.lon << "}"; }
        o << "]"; res.set_content(o.str(), "application/json"); });

    svr.Get("/api/routes", H {
        ostringstream o; o << fixed << setprecision(6) << "[";
        bool first = true;
        for (size_t r = 0; r < routes.size(); r++) { if (routes[r].empty()) continue;
            o << (first ? "" : ",") << "{\"id\":" << r << ",\"stops\":["; first = false;
            for (size_t i = 0; i < routes[r].size(); i++) { auto& s = stops[routes[r][i]];
                o << (i ? "," : "") << "{\"lat\":" << s.lat << ",\"lon\":" << s.lon << "}"; }
            o << "]}"; }
        o << "]"; res.set_content(o.str(), "application/json"); });

    svr.Get("/api/buses", H {
        lock_guard<mutex> L(mu); ostringstream o; o << "["; bool first = true;
        buses.each([&](int, Bus& b) { o << (first ? "" : ",") << busJson(b); first = false; });
        o << "]"; res.set_content(o.str(), "application/json"); });

    svr.Get("/api/nearest", H {                     // k-d tree nearest bus: ?lat=&lon=
        double lat = stod(req.get_param_value("lat")), lon = stod(req.get_param_value("lon"));
        lock_guard<mutex> L(mu); vector<Pt> pts;
        buses.each([&](int, Bus& b) { pts.push_back({b.lat, b.lon, b.id}); });
        KDTree kd; kd.build(pts); int id = kd.nearest(lat, lon);
        if (id < 0) { res.set_content("null", "application/json"); return; }
        Bus* b = buses.find(id); double km = hav({0,"",lat,lon}, {0,"",b->lat,b->lon});
        string j = busJson(*b); j.insert(j.size() - 1, ",\"km\":" + to_string(km));
        res.set_content(j, "application/json"); });

    svr.Get("/api/arrivals", H {                    // min-heap of ETAs: ?stop=id
        int s = stoi(req.get_param_value("stop")); lock_guard<mutex> L(mu);
        MinHeap<pair<double,int>> h;
        buses.each([&](int, Bus& b) { double e = eta(b, s); if (e >= 0) h.push({e, b.id}); });
        ostringstream o; o << fixed << setprecision(1) << "["; bool first = true;
        while (!h.empty()) { auto [e, id] = h.pop(); Bus* b = buses.find(id);
            o << (first ? "" : ",") << "{\"bus\":" << id << ",\"plate\":\"" << esc(b->plate) << "\",\"route\":" << b->route << ",\"eta\":" << e << "}"; first = false; }
        o << "]"; res.set_content(o.str(), "application/json"); });

    svr.Get("/api/path", H {                        // Path search: ?from=&to=&algo=dijkstra|bfs|dfs
        int s = stoi(req.get_param_value("from")), t = stoi(req.get_param_value("to")), n = stops.size();
        string algo = req.get_param_value("algo");
        if (algo.empty()) algo = "dijkstra";

        double km = 0; vector<int> path;
        if (algo == "bfs") {
            auto res = runBFS(s, t);
            if (res.first < 0) { res.set_content("null", "application/json"); return; }
            km = res.first; path = res.second;
        } else if (algo == "dfs") {
            auto res = runDFS(s, t);
            if (res.first < 0) { res.set_content("null", "application/json"); return; }
            km = res.first; path = res.second;
        } else {
            algo = "dijkstra";
            vector<double> d(n, 1e18); vector<int> p(n, -1); MinHeap<pair<double,int>> h;
            d[s] = 0; h.push({0, s});
            while (!h.empty()) { auto [du, u] = h.pop(); if (du > d[u]) continue;
                for (auto& [v, w] : adj[u]) if (d[u] + w < d[v]) { d[v] = d[u] + w; p[v] = u; h.push({d[v], v}); } }
            if (d[t] > 1e17) { res.set_content("null", "application/json"); return; }
            for (int v = t; v != -1; v = p[v]) path.push_back(v); reverse(path.begin(), path.end());
            km = d[t];
        }

        ostringstream o; o << fixed << setprecision(2)
          << "{\"algo\":\"" << esc(algo) << "\",\"km\":" << km << ",\"hops\":" << (path.empty() ? 0 : (int)path.size() - 1)
          << ",\"stops\":[";
        for (size_t i = 0; i < path.size(); i++) o << (i ? "," : "") << "\"" << esc(stops[path[i]].name) << "\"";
        o << "]}"; res.set_content(o.str(), "application/json"); });

    cout << "Running on http://localhost:8080\n"; svr.listen("0.0.0.0", 8080);
}
