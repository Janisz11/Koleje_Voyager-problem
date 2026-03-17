#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import http.server
import socketserver
import json
import os
import sys
import time
import math
import webbrowser
from urllib.parse import urlparse, parse_qs
from itertools import permutations
from datetime import datetime

PORT = 8000
FILE = "gtfs_visualizer.html"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GTFS_DIR = os.path.join(BASE_DIR, "google_transit")

os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from src.gtfs import load_gtfs, build_graph, find_stop, station_group
from src.algorithms import (
    dijkstra, astar, reconstruct_path,
    tour_cost_matrix, tabu_search_unlimited, tabu_search_variable_tenure,
)
from src.utils import sec_to_hhmm, format_duration
from src.config import DEFAULT_NUM_DAYS
from src.cli.tsp_cli import (
    compute_cost_matrix, compute_cost_matrix_chained,
    check_direct_connections, evaluate_tour, run_tabu, MATRIX_ITERATIONS,
)

_gtfs_data = None


def get_gtfs():
    global _gtfs_data
    if _gtfs_data is None:
        _gtfs_data = load_gtfs(verbose=False)
    return _gtfs_data


def handle_search(params):
    a_name    = params.get("a",    [""])[0]
    b_name    = params.get("b",    [""])[0]
    criterion = params.get("c",    ["t"])[0]
    time_str  = params.get("time", [""])[0]
    algo      = params.get("algo", ["astar"])[0]

    if not a_name or not b_name or not time_str:
        return {"ok": False, "error": "Brakujące parametry"}

    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return {"ok": False, "error": f"Nieprawidłowy format czasu: {time_str}"}

    travel_date = dt.date()
    start_sec   = dt.hour * 3600 + dt.minute * 60

    data  = get_gtfs()
    stops = data["stops"]

    a_ids = find_stop(a_name, stops)
    b_ids = find_stop(b_name, stops)

    if not a_ids:
        return {"ok": False, "error": f"Nie znaleziono przystanku: {a_name}"}
    if not b_ids:
        return {"ok": False, "error": f"Nie znaleziono przystanku: {b_name}"}

    start_ids = list({sid for aid in a_ids for sid in station_group(aid, stops)})
    end_ids   = set(sid for bid in b_ids for sid in station_group(bid, stops))

    edge_map = build_graph(data, travel_date, num_days=2)

    t0 = time.perf_counter()
    if algo == "dijkstra":
        result    = dijkstra(start_ids, end_ids, start_sec, edge_map, criterion)
        algo_name = "Dijkstra"
    else:
        result    = astar(start_ids, end_ids, start_sec, edge_map, criterion, stops)
        algo_name = f'A* (kryterium: {"czas" if criterion == "t" else "przesiadki"})'
    calc_time = time.perf_counter() - t0

    if result is None:
        return {"ok": False, "error": "Brak połączenia w wybranym terminie"}

    dist, prev, best_end = result
    path = reconstruct_path(prev, set(start_ids), best_end)

    if not path:
        return {"ok": False, "error": "Nie udało się odtworzyć ścieżki"}

    end_dist   = dist[best_end]
    total_time = end_dist[0] - start_sec
    transfers  = end_dist[1]
    is_multiday = end_dist[0] >= 86400

    steps = []
    for step in path:
        if step.get("transfer"):
            continue
        steps.append({
            "from": stops.get(step["from_id"], {}).get("name", step["from_id"]),
            "to":   stops.get(step["to_id"],   {}).get("name", step["to_id"]),
            "line": step["line"] or "",
            "dep":  sec_to_hhmm(step["dep"], show_day=is_multiday),
            "arr":  sec_to_hhmm(step["arr"], show_day=is_multiday),
        })

    dur_str  = format_duration(total_time)
    crit_val = f"Czas: {dur_str}" if criterion == "t" else f"Przesiadki: {transfers}"

    return {
        "ok": True,
        "steps": steps,
        "meta": {
            "algorithm":       algo_name,
            "criterion_value": crit_val,
            "calc_time":       f"{calc_time:.4f}s",
            "transfers":       transfers,
        },
    }


def handle_tsp(params):
    a_name    = params.get("a",    [""])[0]
    l_str     = params.get("l",    [""])[0]
    criterion = params.get("c",    ["t"])[0]
    time_str  = params.get("time", [""])[0]

    if not a_name or not l_str or not time_str:
        return {"ok": False, "error": "Brakujące parametry TSP"}

    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return {"ok": False, "error": f"Nieprawidłowy format czasu: {time_str}"}

    travel_date  = dt.date()
    start_sec    = dt.hour * 3600 + dt.minute * 60
    visit_names  = [s.strip() for s in l_str.split(";") if s.strip()]
    all_names    = [a_name] + visit_names

    data  = get_gtfs()
    stops = data["stops"]

    node_ids = []
    for name in all_names:
        found = find_stop(name, stops)
        if not found:
            return {"ok": False, "error": f"Nie znaleziono przystanku: {name}"}
        node_ids.append(found[0])

    n      = len(node_ids)
    L_size = len(visit_names)

    edge_map = build_graph(data, travel_date, num_days=DEFAULT_NUM_DAYS)

    t0 = time.perf_counter()

    cost_matrix, _, _, _ = compute_cost_matrix(
        node_ids, edge_map, stops, criterion, start_sec
    )

    direct = check_direct_connections(node_ids, edge_map, stops, criterion, start_sec)
    for (i, j), dc in direct.items():
        if dc < cost_matrix[i][j]:
            cost_matrix[i][j] = dc

    if n <= 2:
        best_tour, best_cost = None, float("inf")
        for perm in permutations(range(1, n)):
            tour = [0] + list(perm) + [0]
            c = tour_cost_matrix(tour, cost_matrix)
            if c < best_cost:
                best_cost = c
                best_tour = tour[:]
        algo_name = f"Brute-force (n={n})"
    else:
        best_tour = run_tabu(n, cost_matrix, L_size, False, False, False)
        algo_name = "Tabu Search (2b)"

    for _ in range(MATRIX_ITERATIONS):
        cost_matrix, _, _, _ = compute_cost_matrix_chained(
            node_ids, edge_map, stops, criterion, start_sec, best_tour
        )
        for (i, j), dc in direct.items():
            if dc < cost_matrix[i][j]:
                cost_matrix[i][j] = dc

        prev_tour = best_tour[:]
        if n <= 4:
            new_best, new_cost = None, float("inf")
            for perm in permutations(range(1, n)):
                tour = [0] + list(perm) + [0]
                c = tour_cost_matrix(tour, cost_matrix)
                if c < new_cost:
                    new_cost = c
                    new_best = tour[:]
            best_tour = new_best
        else:
            best_tour = run_tabu(n, cost_matrix, L_size, False, False, False)

        if best_tour == prev_tour:
            break

    tour_names = [stops[node_ids[i]]["name"] for i in best_tour]
    real_cost, total_xfers, all_steps, final_arrival = evaluate_tour(
        best_tour, node_ids, edge_map, stops, criterion, start_sec
    )
    calc_time = time.perf_counter() - t0

    if not all_steps:
        return {"ok": False, "error": "Nie udało się wyznaczyć trasy TSP"}

    total_time  = final_arrival - start_sec
    dur_str     = format_duration(total_time)
    crit_val    = f"Czas: {dur_str}" if criterion == "t" else f"Przesiadki: {total_xfers}"
    is_multiday = final_arrival >= 86400

    steps = []
    for step in all_steps:
        if step.get("transfer"):
            continue
        steps.append({
            "from": stops.get(step["from_id"], {}).get("name", step["from_id"]),
            "to":   stops.get(step["to_id"],   {}).get("name", step["to_id"]),
            "line": step["line"] or "",
            "dep":  sec_to_hhmm(step["dep"], show_day=is_multiday),
            "arr":  sec_to_hhmm(step["arr"], show_day=is_multiday),
        })

    return {
        "ok": True,
        "steps": steps,
        "meta": {
            "algorithm":       algo_name,
            "criterion_value": crit_val,
            "calc_time":       f"{calc_time:.4f}s",
            "transfers":       total_xfers,
            "tour":            " → ".join(tour_names),
        },
    }


class GTFSHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        params = parse_qs(parsed.query)

        if path == "/gtfs-list":
            files = (
                [f for f in os.listdir(GTFS_DIR) if f.endswith(".txt")]
                if os.path.isdir(GTFS_DIR) else []
            )
            self._send_json(files)

        elif path.startswith("/gtfs/"):
            filename = path[6:]
            filepath = os.path.join(GTFS_DIR, filename)
            if os.path.isfile(filepath):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                with open(filepath, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)

        elif path == "/search":
            try:
                result = handle_search(params)
            except Exception as e:
                result = {"ok": False, "error": str(e)}
            self._send_json(result)

        elif path == "/tsp":
            try:
                result = handle_tsp(params)
            except Exception as e:
                result = {"ok": False, "error": str(e)}
            self._send_json(result)

        else:
            super().do_GET()

    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # wycisz logi requestów


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


with ThreadedServer(("", PORT), GTFSHandler) as httpd:
    url = f"http://localhost:{PORT}/{FILE}"
    print(f"Serwer uruchomiony: {url}")
    webbrowser.open(url)
    httpd.serve_forever()
