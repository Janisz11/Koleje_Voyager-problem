#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI dla Pathfindera (Zadanie 1)
================================
Wyszukiwanie połączeń kolejowych w danych GTFS.

Użycie:
    python -m src.cli.pathfinder_cli <A> <B> <kryterium> <czas>
    python -m src.cli.pathfinder_cli --dijkstra <A> <B> <kryterium> <czas>
    python -m src.cli.pathfinder_cli --json <A> <B> <kryterium> <czas>

Argumenty:
    A          - nazwa przystanku startowego (np. "Wrocław Główny")
    B          - nazwa przystanku docelowego (np. "Jelenia Góra")
    kryterium  - 't' = minimalizacja czasu, 'p' = minimalizacja przesiadek
    czas       - data i godzina w formacie "YYYY-MM-DD HH:MM"

Flagi:
    --dijkstra  użyj Dijkstry zamiast A*
    --json      wypisz stdout jako JSON (dla serwera)

Przykład:
    python -m src.cli.pathfinder_cli "Wrocław Główny" "Jelenia Góra" t "2026-03-09 08:00"
    python -m src.cli.pathfinder_cli --dijkstra "Wrocław Główny" "Legnica" t "2026-03-09 08:00"
"""

import sys
import os
import json
import time
from datetime import datetime


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.gtfs import load_gtfs, build_graph, find_stop, station_group
from src.algorithms import dijkstra, astar, reconstruct_path
from src.utils import sec_to_hhmm, format_duration


def print_results(path: list, stops: dict, criterion: str,
                  total_time_sec: int, transfers: int, calc_time: float,
                  json_mode: bool = False):
    dur_str = format_duration(total_time_sec)

    max_time = max((step["arr"] for step in path if not step.get("transfer")), default=0)
    is_multiday = max_time >= 86400

    
    steps = []
    for step in path:
        if step.get("transfer"):
            continue
        from_name = stops.get(step["from_id"], {}).get("name", step["from_id"])
        to_name   = stops.get(step["to_id"],   {}).get("name", step["to_id"])
        steps.append({
            "from": from_name,
            "to":   to_name,
            "line": step["line"] or "",
            "dep":  sec_to_hhmm(step["dep"], show_day=is_multiday),
            "arr":  sec_to_hhmm(step["arr"], show_day=is_multiday),
        })

    if json_mode:
        print(json.dumps(steps, ensure_ascii=False))
    else:
        w = 35
        print(f"{'PRZYSTANEK OD':<{w}} {'PRZYSTANEK DO':<{w}} {'LINIA':<8} {'ODJAZD':<7} PRZYJAZD")
        print("─" * (w * 2 + 27))
        for s in steps:
            print(f"{s['from']:<{w}} {s['to']:<{w}} {s['line']:<8} {s['dep']:<7} {s['arr']}")
        print("─" * (w * 2 + 27))
        print(f"Łączny czas podróży: {dur_str}  |  Przesiadki: {transfers}")

    crit_val = f"Czas: {dur_str}" if criterion == "t" else f"Przesiadki: {transfers}"
    print(f"Kryterium: {crit_val}", file=sys.stderr)
    print(f"Czas obliczen: {calc_time:.4f}s", file=sys.stderr)


def _run(use_dijkstra: bool = False):
    json_mode = "--json" in sys.argv
    raw_args  = [a for a in sys.argv[1:] if a not in ("--json", "--dijkstra")]

    if len(raw_args) < 4:
        print(__doc__)
        sys.exit(1)

    stop_a_name = raw_args[0]
    stop_b_name = raw_args[1]
    criterion   = raw_args[2].lower().strip()
    time_str    = raw_args[3]

    if criterion not in ("t", "p"):
        print("Kryterium musi być 't' (czas) lub 'p' (przesiadki).", file=sys.stderr)
        sys.exit(1)

    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        print("Format czasu: 'YYYY-MM-DD HH:MM', np. '2026-03-09 08:00'", file=sys.stderr)
        sys.exit(1)

    travel_date = dt.date()
    start_sec   = dt.hour * 3600 + dt.minute * 60

    data  = load_gtfs()
    stops = data["stops"]

    a_ids = find_stop(stop_a_name, stops)
    b_ids = find_stop(stop_b_name, stops)
    if not a_ids:
        print(f"Nie znaleziono przystanku: '{stop_a_name}'", file=sys.stderr)
        sys.exit(1)
    if not b_ids:
        print(f"Nie znaleziono przystanku: '{stop_b_name}'", file=sys.stderr)
        sys.exit(1)

    start_ids = list({sid for aid in a_ids for sid in station_group(aid, stops)})
    end_ids   = set(sid for bid in b_ids for sid in station_group(bid, stops))

    print(f"\nTrasa:     {stops[a_ids[0]]['name']} → {stops[b_ids[0]]['name']}", file=sys.stderr)
    print(f"Kryterium: {'czas' if criterion == 't' else 'przesiadki'}", file=sys.stderr)
    print(f"Odjazd:    {dt.strftime('%Y-%m-%d %H:%M')}", file=sys.stderr)

    edge_map = build_graph(data, travel_date, num_days=2)

    t0 = time.perf_counter()
    if use_dijkstra:
        result    = dijkstra(start_ids, end_ids, start_sec, edge_map, criterion)
        algo_name = "Dijkstra"
    elif criterion == "t":
        result    = astar(start_ids, end_ids, start_sec, edge_map, "t", stops)
        algo_name = "A* (kryterium: czas)"
    else:
        result    = astar(start_ids, end_ids, start_sec, edge_map, "p", stops)
        algo_name = "A* (kryterium: przesiadki)"
    calc_time = time.perf_counter() - t0

    print(f"Algorytm:  {algo_name}", file=sys.stderr)

    if result is None:
        print("\nBrak połączenia w wybranym dniu i godzinie.", file=sys.stderr)
        sys.exit(1)

    dist, prev, best_end = result
    path = reconstruct_path(prev, set(start_ids), best_end)

    if not path:
        print("Nie udało się odtworzyć ścieżki.", file=sys.stderr)
        sys.exit(1)

    end_dist   = dist[best_end]
    total_time = end_dist[0] - start_sec
    transfers  = end_dist[1]

    print_results(path, stops, criterion, total_time, transfers, calc_time, json_mode)


def main():
    _run(use_dijkstra=False)


def run_dijkstra_only():
    _run(use_dijkstra=True)


if __name__ == "__main__":
    if "--dijkstra" in sys.argv:
        run_dijkstra_only()
    else:
        main()
