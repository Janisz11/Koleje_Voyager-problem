#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from datetime import date, timedelta
from collections import defaultdict

sys.path.insert(0, __file__.rsplit("src", 1)[0])
from src.config import SECONDS_PER_DAY
from src.gtfs.calendar import is_service_active


def build_graph(data: dict, travel_date: date, num_days: int = 1) -> dict:
    stops      = data["stops"]
    trips      = data["trips"]
    routes     = data["routes"]
    stop_times = data["stop_times"]
    calendar   = data["calendar"]
    cal_dates  = data["cal_dates"]

    edge_map = defaultdict(list)

    for day_offset in range(num_days):
        current_date = travel_date + timedelta(days=day_offset)
        time_offset  = day_offset * SECONDS_PER_DAY

        for trip_id, sts in stop_times.items():
            trip = trips.get(trip_id)
            if not trip:
                continue
            if not is_service_active(trip["service_id"], current_date, calendar, cal_dates):
                continue

            route     = routes.get(trip["route_id"], {})
            line_name = route.get("short") or route.get("long", "?")

            for i in range(len(sts) - 1):
                frm = sts[i]
                to  = sts[i + 1]
                if frm["pickup"] == 1:
                    continue

                edge_map[frm["stop_id"]].append({
                    "to":       to["stop_id"],
                    "dep":      frm["dep"] + time_offset,
                    "arr":      to["arr"] + time_offset,
                    "trip_id":  f"{trip_id}_d{day_offset}" if day_offset > 0 else trip_id,
                    "line":     line_name,
                    "route_id": trip["route_id"],
                    "block_id": trip.get("block_id", ""),
                    "transfer": False,
                    "day":      day_offset,
                })

    _add_transfer_edges(edge_map, stops)

    print(f"  Krawędzie grafu: {sum(len(v) for v in edge_map.values()):>6}", file=sys.stderr)
    return dict(edge_map)


def _add_transfer_edges(edge_map: dict, stops: dict) -> None:
    parent_to_children = defaultdict(list)
    for sid, stop in stops.items():
        parent = stop["parent"]
        if parent:
            parent_to_children[parent].append(sid)

    for parent, children in parent_to_children.items():
        all_nodes = ([parent] if parent in stops else []) + children

        for a in all_nodes:
            for b in all_nodes:
                if a != b:
                    edge_map[a].append({
                        "to":       b,
                        "dep":      -1,
                        "arr":      -1,
                        "trip_id":  None,
                        "line":     None,
                        "route_id": None,
                        "transfer": True,
                    })


def find_stop(name: str, stops: dict) -> list[str]:
    nl = name.lower().strip()

    exact = [sid for sid, s in stops.items() if s["name"].lower() == nl]
    if exact:
        return exact

    główny_name = nl + " główny"
    główny_match = [sid for sid, s in stops.items() if s["name"].lower() == główny_name]
    if główny_match:
        return główny_match

    prefix = [sid for sid, s in stops.items() if s["name"].lower().startswith(nl)]
    if prefix:
        główny_in_prefix = [sid for sid in prefix
                           if "główny" in stops[sid]["name"].lower()]
        if główny_in_prefix:
            return główny_in_prefix
        return prefix

    contains = [sid for sid, s in stops.items() if nl in s["name"].lower()]
    if contains:
        główny_in_contains = [sid for sid in contains
                             if "główny" in stops[sid]["name"].lower()]
        if główny_in_contains:
            return główny_in_contains
        return contains

    return []


def station_group(stop_id: str, stops: dict) -> list[str]:
    stop = stops.get(stop_id)
    if not stop:
        return [stop_id]

    parent = stop["parent"]
    if parent:
        siblings = [sid for sid, s in stops.items()
                    if s["parent"] == parent or sid == parent]
        return list(set(siblings + [stop_id]))

    children = [sid for sid, s in stops.items() if s["parent"] == stop_id]
    return [stop_id] + children if children else [stop_id]
