#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import csv
from collections import defaultdict

sys.path.insert(0, __file__.rsplit("src", 1)[0])
from src.config import GTFS_DIR
from src.utils.time_utils import time_to_sec


def read_csv(filename: str, gtfs_dir: str = None) -> list[dict]:
    if gtfs_dir is None:
        gtfs_dir = GTFS_DIR

    path = os.path.join(gtfs_dir, filename)
    if not os.path.exists(path):
        return []

    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_gtfs(gtfs_dir: str = None, verbose: bool = True) -> dict:
    if gtfs_dir is None:
        gtfs_dir = GTFS_DIR

    if verbose:
        print("Wczytywanie danych GTFS...", file=sys.stderr)

    stops = {}
    for row in read_csv("stops.txt", gtfs_dir):
        try:
            stops[row["stop_id"]] = {
                "id":     row["stop_id"],
                "name":   row["stop_name"],
                "lat":    float(row["stop_lat"]),
                "lon":    float(row["stop_lon"]),
                "type":   int(row.get("location_type") or 0),
                "parent": row.get("parent_station", "").strip(),
            }
        except (ValueError, KeyError):
            continue

    routes = {}
    for row in read_csv("routes.txt", gtfs_dir):
        routes[row["route_id"]] = {
            "id":    row["route_id"],
            "short": row.get("route_short_name") or row.get("route_long_name", "?"),
            "long":  row.get("route_long_name", ""),
            "color": row.get("route_color", ""),
        }

    trips = {}
    for row in read_csv("trips.txt", gtfs_dir):
        trips[row["trip_id"]] = {
            "id":         row["trip_id"],
            "route_id":   row["route_id"],
            "service_id": row["service_id"],
            "headsign":   row.get("trip_headsign", ""),
            "block_id":   row.get("block_id", "").strip(),
        }

    stop_times = defaultdict(list)
    for row in read_csv("stop_times.txt", gtfs_dir):
        stop_times[row["trip_id"]].append({
            "stop_id": row["stop_id"],
            "arr":     time_to_sec(row["arrival_time"]),
            "dep":     time_to_sec(row["departure_time"]),
            "seq":     int(row["stop_sequence"]),
            "pickup":  int(row.get("pickup_type") or 0),
        })
    for tid in stop_times:
        stop_times[tid].sort(key=lambda x: x["seq"])

    calendar = {}
    for row in read_csv("calendar.txt", gtfs_dir):
        calendar[row["service_id"]] = {
            "days": [
                int(row["monday"]), int(row["tuesday"]), int(row["wednesday"]),
                int(row["thursday"]), int(row["friday"]),
                int(row["saturday"]), int(row["sunday"]),
            ],
            "start": row["start_date"],
            "end":   row["end_date"],
        }

    cal_dates = defaultdict(list)
    for row in read_csv("calendar_dates.txt", gtfs_dir):
        cal_dates[row["service_id"]].append({
            "date": row["date"],
            "type": int(row["exception_type"]),
        })

    if verbose:
        print(f"  Przystanki:   {len(stops):>6}", file=sys.stderr)
        print(f"  Trasy:        {len(routes):>6}", file=sys.stderr)
        print(f"  Kursy:        {len(trips):>6}", file=sys.stderr)
        print(f"  Wpisy czasów: {sum(len(v) for v in stop_times.values()):>6}", file=sys.stderr)

    return dict(
        stops=stops,
        routes=routes,
        trips=trips,
        stop_times=dict(stop_times),
        calendar=calendar,
        cal_dates=dict(cal_dates),
    )
