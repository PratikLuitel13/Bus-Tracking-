// Custom data structures used by the tracker
#pragma once
#include <vector>
#include <string>
#include <algorithm>
#include <functional>
#include <cctype>

// Binary min-heap: O(log n) push/pop. Used for Dijkstra and "next bus to arrive".
template<class T, class Cmp = std::less<T>>
class MinHeap {
    std::vector<T> a; Cmp cmp;
public:
    bool empty() const { return a.empty(); }
    void push(T v) {
        a.push_back(v); size_t i = a.size() - 1;
        while (i && cmp(a[i], a[(i-1)/2])) { std::swap(a[i], a[(i-1)/2]); i = (i-1)/2; }
    }
    T pop() {
        T top = a[0]; a[0] = a.back(); a.pop_back();
        size_t i = 0, n = a.size();
        for (;;) {
            size_t l = 2*i+1, r = l+1, m = i;
            if (l < n && cmp(a[l], a[m])) m = l;
            if (r < n && cmp(a[r], a[m])) m = r;
            if (m == i) break;
            std::swap(a[i], a[m]); i = m;
        }
        return top;
    }
};

// Hash table (separate chaining, int keys, auto-resize): O(1) average bus lookup/update.
template<class V>
class HashTable {
    std::vector<std::vector<std::pair<int,V>>> b; size_t n = 0;
    void grow() {
        std::vector<std::vector<std::pair<int,V>>> nb(b.size() * 2);
        for (auto& bk : b) for (auto& kv : bk) nb[(size_t)kv.first % nb.size()].push_back(kv);
        b.swap(nb);
    }
public:
    HashTable() : b(16) {}
    V* find(int k) { for (auto& kv : b[(size_t)k % b.size()]) if (kv.first == k) return &kv.second; return nullptr; }
    void put(int k, V v) {
        if (V* p = find(k)) { *p = v; return; }
        if (n >= b.size() * 3 / 4) grow();
        b[(size_t)k % b.size()].push_back({k, v}); n++;
    }
    template<class F> void each(F f) { for (auto& bk : b) for (auto& kv : bk) f(kv.first, kv.second); }
};

// Trie: O(L) prefix search for stop-name autocomplete.
class Trie {
    struct N { N* c[128] = {}; std::vector<int> ids; };
    N* root = new N;
    void collect(N* n, std::vector<int>& o) {
        for (int id : n->ids) o.push_back(id);
        for (N* ch : n->c) if (ch && o.size() < 10) collect(ch, o);
    }
public:
    void insert(const std::string& s, int id) {
        N* n = root;
        for (char ch : s) { unsigned char u = std::tolower(ch) & 127; if (!n->c[u]) n->c[u] = new N; n = n->c[u]; }
        n->ids.push_back(id);
    }
    std::vector<int> prefix(const std::string& p) {
        N* n = root;
        for (char ch : p) { unsigned char u = std::tolower(ch) & 127; if (!n->c[u]) return {}; n = n->c[u]; }
        std::vector<int> o; collect(n, o); return o;
    }
};

// 2-D k-d tree: O(log n) average nearest-neighbour (vs O(n) linear scan).
struct Pt { double x, y; int id; };
class KDTree {
    std::vector<Pt> p;
    void rec(int l, int r, int d) {
        if (r - l <= 0) return;
        int m = (l + r) / 2;
        std::nth_element(p.begin()+l, p.begin()+m, p.begin()+r,
            [d](const Pt& a, const Pt& b) { return d ? a.y < b.y : a.x < b.x; });
        rec(l, m, d^1); rec(m+1, r, d^1);
    }
    void nn(int l, int r, int d, double qx, double qy, int& best, double& bd) const {
        if (r - l <= 0) return;
        int m = (l + r) / 2;
        double dx = p[m].x - qx, dy = p[m].y - qy, dd = dx*dx + dy*dy;
        if (dd < bd) { bd = dd; best = m; }
        double diff = d ? qy - p[m].y : qx - p[m].x;
        if (diff < 0) { nn(l, m, d^1, qx, qy, best, bd); if (diff*diff < bd) nn(m+1, r, d^1, qx, qy, best, bd); }
        else          { nn(m+1, r, d^1, qx, qy, best, bd); if (diff*diff < bd) nn(l, m, d^1, qx, qy, best, bd); }
    }
public:
    void build(std::vector<Pt> pts) { p = std::move(pts); rec(0, (int)p.size(), 0); }
    int nearest(double x, double y) const {
        int b = -1; double bd = 1e300; nn(0, (int)p.size(), 0, x, y, b, bd);
        return b < 0 ? -1 : p[b].id;
    }
};
