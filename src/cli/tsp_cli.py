#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI dla TSP Solvera (Zadanie 2)
===============================


Użycie:
    python -m src.cli.tsp_cli <A> <L> <kryterium> <czas>
    python -m src.cli.tsp_cli --2a <A> <L> <kryterium> <czas>

Flagi:
    --2a    Tabu Search bez ograniczania T
    --2b    Tabu Search ze zmiennym T (domyślne)
    --2c    Włącz kryterium aspiracji
    --2d    Włącz próbkowanie sąsiedztwa

Przykład:
    python -m src.cli.tsp_cli "Wrocław" "Legnica;Jelcz" t "2026-03-10 08:00"
    python -m src.cli.tsp_cli --2a --2c "Wrocław" "Legnica;Jelcz" t "2026-03-10 08:00"
"""

import sys
import os
import time
import math
from datetime import datetime
from itertools import permutations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.config import DEFAULT_NUM_DAYS
from src.gtfs import load_gtfs, build_graph, find_stop, station_group
from src.algorithms import (
    astar, reconstruct_path,
    tour_cost_matrix, tabu_search_unlimited, tabu_search_variable_tenure
)
from src.utils import sec_to_hhmm, format_duration
from src.cli.pathfinder_cli import print_results

MATRIX_ITERATIONS = 2


def compute_cost_matrix(nodes: list[str], edge_map: dict, stops: dict,
                        criterion: str, start_sec: int) -> tuple:
    n   = len(nodes)
    INF = float("inf")

    cost     = [[INF] * n for _ in range(n)]
    path_mat = [[[]  ] * n for _ in range(n)]
    xfer_mat = [[0   ] * n for _ in range(n)]
    arr_mat  = [[INF ] * n for _ in range(n)]

    print(f"Obliczanie macierzy {n}×{n} (optymistyczna)...", file=sys.stderr)

    for i in range(n):
        cost[i][i]     = 0
        arr_mat[i][i]  = start_sec
        xfer_mat[i][i] = 0

        start_ids = station_group(nodes[i], stops)
        for j in range(n):
            if i == j:
                continue

            end_ids = set(station_group(nodes[j], stops))
            result  = astar(start_ids, end_ids, start_sec, edge_map, criterion, stops)
            if result is None:
                print(f"  ✗ {stops[nodes[i]]['name']} → {stops[nodes[j]]['name']}: brak",
                      file=sys.stderr)
                continue

            dist_map, prev_map, best_end = result
            d = dist_map[best_end]

            arr_time = d[0]
            n_xfers  = d[1]

            cost[i][j]     = arr_time if criterion == "t" else n_xfers * 10_000_000 + arr_time
            arr_mat[i][j]  = arr_time
            xfer_mat[i][j] = n_xfers
            path_mat[i][j] = reconstruct_path(prev_map, set(start_ids), best_end)

        print(f"  [{i+1}/{n}] {stops[nodes[i]]['name']}", file=sys.stderr)

    return cost, path_mat, xfer_mat, arr_mat


def compute_cost_matrix_chained(nodes: list[str], edge_map: dict, stops: dict,
                                criterion: str, start_sec: int,
                                tour_order: list) -> tuple:
    n   = len(nodes)
    INF = float("inf")

    cost     = [[INF] * n for _ in range(n)]
    path_mat = [[[]  ] * n for _ in range(n)]
    xfer_mat = [[0   ] * n for _ in range(n)]
    arr_mat  = [[INF ] * n for _ in range(n)]

    node_times = {tour_order[0]: start_sec}
    cur_time   = start_sec

    for k in range(len(tour_order) - 1):
        i = tour_order[k]
        j = tour_order[k + 1]

        start_ids = station_group(nodes[i], stops)
        end_ids   = set(station_group(nodes[j], stops))
        result    = astar(start_ids, end_ids, cur_time, edge_map, criterion, stops)

        if result is None:
            break

        dist_map, _, best_end = result
        cur_time      = dist_map[best_end][0]
        node_times[j] = cur_time

    print(f"Obliczanie macierzy {n}×{n} (łańcuchowa)...", file=sys.stderr)

    for i in range(n):
        cost[i][i]     = 0
        t_start        = node_times.get(i, start_sec)
        arr_mat[i][i]  = t_start
        xfer_mat[i][i] = 0

        start_ids = station_group(nodes[i], stops)

        for j in range(n):
            if i == j:
                continue

            end_ids = set(station_group(nodes[j], stops))
            result  = astar(start_ids, end_ids, t_start, edge_map, criterion, stops)
            if result is None:
                continue

            dist_map, prev_map, best_end = result
            d = dist_map[best_end]

            arr_time = d[0]
            n_xfers  = d[1]

            cost[i][j]     = arr_time if criterion == "t" else n_xfers * 10_000_000 + arr_time
            arr_mat[i][j]  = arr_time
            xfer_mat[i][j] = n_xfers
            path_mat[i][j] = reconstruct_path(prev_map, set(start_ids), best_end)

        print(f"  [{i+1}/{n}] {stops[nodes[i]]['name']}", file=sys.stderr)

    return cost, path_mat, xfer_mat, arr_mat


def check_direct_connections(nodes: list[str], edge_map: dict, stops: dict,
                             criterion: str, start_sec: int) -> dict:
    n      = len(nodes)
    direct = {}

    print("Sprawdzanie bezpośrednich połączeń...", file=sys.stderr)

    for i in range(n):
        start_ids = set(station_group(nodes[i], stops))
        for j in range(n):
            if i == j:
                continue

            end_ids   = set(station_group(nodes[j], stops))
            best_arr  = float("inf")
            best_trip = None

            for sid in start_ids:
                for edge in edge_map.get(sid, []):
                    if edge["transfer"] or edge["dep"] < start_sec:
                        continue

                    trip    = edge["trip_id"]
                    curr    = edge["to"]
                    arr     = edge["arr"]
                    visited = {sid}

                    while curr not in end_ids and curr not in visited:
                        visited.add(curr)
                        found = False
                        for e2 in edge_map.get(curr, []):
                            if e2["trip_id"] == trip and not e2["transfer"]:
                                curr  = e2["to"]
                                arr   = e2["arr"]
                                found = True
                                break
                        if not found:
                            break

                    if curr in end_ids and arr < best_arr:
                        best_arr  = arr
                        best_trip = trip

            if best_trip is not None:
                direct[(i, j)] = best_arr
                print(f"  Bezpośrednie [{stops[nodes[i]]['name']} → "
                      f"{stops[nodes[j]]['name']}]: {sec_to_hhmm(best_arr)}",
                      file=sys.stderr)

    return direct


def find_continuation(prev_trip: str, start_ids: set, end_ids: set,
                      edge_map: dict, cur_time: int) -> list | None:
    if prev_trip is None:
        return None

    for sid in start_ids:
        queue   = [(sid, cur_time, [])]
        visited = set()

        while queue:
            curr, t, path = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)

            for edge in edge_map.get(curr, []):
                if edge["transfer"] or edge["trip_id"] != prev_trip:
                    continue
                if edge["dep"] < t:
                    continue

                new_path = path + [{
                    "from_id":  curr,
                    "to_id":    edge["to"],
                    "line":     edge.get("line"),
                    "dep":      edge["dep"],
                    "arr":      edge["arr"],
                    "trip_id":  edge["trip_id"],
                    "transfer": False,
                }]

                if edge["to"] in end_ids:
                    return new_path

                queue.append((edge["to"], edge["arr"], new_path))

    return None



def evaluate_tour(tour: list[int], nodes: list[str], edge_map: dict,
                  stops: dict, criterion: str, start_sec: int) -> tuple:
    total_xfers    = 0
    all_steps      = []
    cur_time       = start_sec
    prev_last_trip = None

    for k in range(len(tour) - 1):
        i = tour[k]
        j = tour[k + 1]

        start_ids = set(station_group(nodes[i], stops))
        end_ids   = set(station_group(nodes[j], stops))

        continuation = find_continuation(prev_last_trip, start_ids, end_ids,
                                         edge_map, cur_time)

        if continuation:
            from_name = stops.get(nodes[i], {}).get("name", nodes[i])
            to_name   = stops.get(nodes[j], {}).get("name", nodes[j])
            print(f"  ✓ Kontynuacja kursu {prev_last_trip}: "
                  f"{from_name} → {to_name}", file=sys.stderr)
            all_steps.extend(continuation)
            cur_time       = continuation[-1]["arr"]
            prev_last_trip = continuation[-1]["trip_id"]
        else:
            result = astar(list(start_ids), end_ids, cur_time,
                           edge_map, criterion, stops)
            if result is None:
                from_name = stops[nodes[i]]['name']
                to_name   = stops[nodes[j]]['name']
                print(f"  ✗ Brak połączenia: {from_name} → {to_name} "
                      f"(czas: {sec_to_hhmm(cur_time, show_day=True)})",
                      file=sys.stderr)
                return float("inf"), 0, [], cur_time

            dist_map, prev_map, best_end = result
            d = dist_map[best_end]

            arr_time  = d[0]
            seg_xfers = d[1]
            path = reconstruct_path(prev_map, set(start_ids), best_end)

            first_trip = next(
                (s["trip_id"] for s in path if not s.get("transfer")), None
            )
            last_trip = next(
                (s["trip_id"] for s in reversed(path) if not s.get("transfer")),
                prev_last_trip
            )

            from_name = stops.get(nodes[i], {}).get("name", nodes[i])
            to_name   = stops.get(nodes[j], {}).get("name", nodes[j])
            print(f"  [odcinek {k}] A*={seg_xfers} | {from_name} → {to_name}", file=sys.stderr)

            if prev_last_trip is not None and first_trip is not None \
                    and first_trip != prev_last_trip:
                seg_xfers += 1
                print(f"  ⇄ Przesiadka graniczna [{k}]: {from_name} → {to_name} "
                      f"({prev_last_trip[:20]} → {first_trip[:20]})",
                      file=sys.stderr)
            else:
                if prev_last_trip is not None:
                    print(f"  ✓ Brak przesiadki granicznej [{k}]: {from_name} → {to_name}",
                          file=sys.stderr)

            print(f"    seg_xfers (A*+granica): {seg_xfers} | "
                  f"last_trip: {str(last_trip)[:25] if last_trip else 'None'}",
                  file=sys.stderr)

            prev_last_trip = last_trip
            cur_time       = arr_time
            total_xfers   += seg_xfers
            all_steps.extend(path)

    print(f"\n  Przesiadki wg algorytmu: {total_xfers}", file=sys.stderr)

    final_xfers = total_xfers

    final_arrival = cur_time
    total_cost    = (final_arrival - start_sec) if criterion == "t" \
                    else final_xfers * 10_000_000 + (final_arrival - start_sec)

    return total_cost, final_xfers, all_steps, final_arrival


def run_tabu(n, cost_matrix, L_size, use_2a, use_aspiration, use_sampling):
    if use_2a:
        return tabu_search_unlimited(n, cost_matrix,
                                     use_aspiration=use_aspiration,
                                     use_sampling=use_sampling)
    else:
        return tabu_search_variable_tenure(n, cost_matrix, L_size,
                                           use_aspiration=use_aspiration,
                                           use_sampling=use_sampling)


def main():
    json_mode      = "--json" in sys.argv
    use_2a         = "--2a" in sys.argv
    use_2b         = "--2b" in sys.argv or not use_2a
    use_aspiration = "--2c" in sys.argv
    use_sampling   = "--2d" in sys.argv

    raw_args = [a for a in sys.argv[1:]
                if a not in ("--json", "--2a", "--2b", "--2c", "--2d")]

    if len(raw_args) < 4:
        print(__doc__)
        sys.exit(1)

    stop_a_name = raw_args[0]
    stops_l_str = raw_args[1]
    criterion   = raw_args[2].lower().strip()
    time_str    = raw_args[3]

    if criterion not in ("t", "p"):
        print("Kryterium: 't' (czas) lub 'p' (przesiadki)", file=sys.stderr)
        sys.exit(1)

    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        print("Format czasu: 'YYYY-MM-DD HH:MM'", file=sys.stderr)
        sys.exit(1)

    travel_date = dt.date()
    start_sec   = dt.hour * 3600 + dt.minute * 60

    visit_names = [s.strip() for s in stops_l_str.split(";") if s.strip()]
    all_names   = [stop_a_name] + visit_names

    data  = load_gtfs()
    stops = data["stops"]

    node_ids = []
    for name in all_names:
        found = find_stop(name, stops)
        if not found:
            print(f"Nie znaleziono przystanku: '{name}'", file=sys.stderr)
            sys.exit(1)
        node_ids.append(found[0])

    n      = len(node_ids)
    L_size = len(visit_names)

    print(f"\nTSP: {n} węzłów (start + {L_size} do odwiedzenia + powrót)",
          file=sys.stderr)
    for i, nid in enumerate(node_ids):
        marker = "[START]" if i == 0 else f"[{i}]"
        print(f"  {marker} {stops[nid]['name']}", file=sys.stderr)

    print(f"\nBudowanie grafu dla {DEFAULT_NUM_DAYS} dni...", file=sys.stderr)
    edge_map = build_graph(data, travel_date, num_days=DEFAULT_NUM_DAYS)

    t0 = time.perf_counter()

    active_mods = []
    if use_2a: active_mods.append("2a")
    if use_2b and not use_2a: active_mods.append("2b")
    if use_aspiration: active_mods.append("2c")
    if use_sampling: active_mods.append("2d")

    cost_matrix, path_mat, xfer_mat, arr_mat = compute_cost_matrix(
        node_ids, edge_map, stops, criterion, start_sec
    )

    direct = check_direct_connections(node_ids, edge_map, stops,
                                      criterion, start_sec)
    for (i, j), direct_cost in direct.items():
        if direct_cost < cost_matrix[i][j]:
            cost_matrix[i][j] = direct_cost

    if n <= 2:
        print(f"\nBrute-force ({math.factorial(n-1)} permutacji)...",
              file=sys.stderr)
        best_tour = None
        best_cost = float("inf")
        for perm in permutations(range(1, n)):
            tour = [0] + list(perm) + [0]
            c = tour_cost_matrix(tour, cost_matrix)
            if c < best_cost:
                best_cost = c
                best_tour = tour[:]
        algo_name = f"Brute-force (n={n})"
    else:
        print(f"\nTabu Search (zadanie {'+'.join(active_mods)})...",
              file=sys.stderr)
        best_tour = run_tabu(n, cost_matrix, L_size, use_2a,
                             use_aspiration, use_sampling)
        algo_name = f"Tabu Search ({'+'.join(active_mods)})"

    for iteration in range(MATRIX_ITERATIONS):
        print(f"\nIteracja {iteration+1}/{MATRIX_ITERATIONS} "
              f"— przeliczanie macierzy z łańcuchowaniem...", file=sys.stderr)

        cost_matrix, path_mat, xfer_mat, arr_mat = compute_cost_matrix_chained(
            node_ids, edge_map, stops, criterion, start_sec, best_tour
        )

        for (i, j), direct_cost in direct.items():
            if direct_cost < cost_matrix[i][j]:
                cost_matrix[i][j] = direct_cost

        prev_tour = best_tour[:]

        if n <= 4:
            new_best = None
            new_cost = float("inf")
            for perm in permutations(range(1, n)):
                tour = [0] + list(perm) + [0]
                c = tour_cost_matrix(tour, cost_matrix)
                if c < new_cost:
                    new_cost = c
                    new_best = tour[:]
            best_tour = new_best
        else:
            best_tour = run_tabu(n, cost_matrix, L_size, use_2a,
                                 use_aspiration, use_sampling)

        if best_tour == prev_tour:
            print(f"  Kolejność stabilna po iteracji {iteration+1} — stop",
                  file=sys.stderr)
            break

    tour_names = [stops[node_ids[i]]["name"] for i in best_tour]
    print(f"\nNajlepsza trasa (macierz): " + " → ".join(tour_names),
          file=sys.stderr)

    print("\nObliczanie finalnej trasy z łańcuchowaniem czasów...",
          file=sys.stderr)
    real_cost, total_xfers, all_steps, final_arrival = evaluate_tour(
        best_tour, node_ids, edge_map, stops, criterion, start_sec
    )

    calc_time = time.perf_counter() - t0

    if not all_steps:
        print("Nie udało się wyznaczyć trasy.", file=sys.stderr)
        sys.exit(1)

    total_time = final_arrival - start_sec
    dur_str    = format_duration(total_time)
    crit_val   = f"Czas: {dur_str}" if criterion == "t" \
                 else f"Przesiadki: {total_xfers}"

    print(f"\nKryterium: {crit_val}", file=sys.stderr)
    print(f"Czas obliczen: {calc_time:.4f}s", file=sys.stderr)
    print(f"Algorytm: {algo_name}", file=sys.stderr)
    print(f"Najlepsza trasa: {' → '.join(tour_names)}", file=sys.stderr)

    print_results(all_steps, stops, criterion, total_time, total_xfers,
                  calc_time, json_mode)


if __name__ == "__main__":
    main()