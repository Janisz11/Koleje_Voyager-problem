#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import heapq

sys.path.insert(0, __file__.rsplit("src", 1)[0])
from src.config import MAX_SPEED_MPS
from src.utils.geo import haversine
from .common import relax_edge, best_end


def build_direct_stop_set(edge_map: dict) -> dict:
    
    direct = {}
    for stop_id, edges in edge_map.items():
        for edge in edges:
            if not edge["transfer"]:
                direct.setdefault(stop_id, set()).add(edge["to"])
    return direct


def heuristic_time(stop_id: str, end_stops: set, stops: dict, **_) -> float:
    s = stops.get(stop_id)
    if not s:
        return 0.0
    min_dist = min(
        haversine(s["lat"], s["lon"], stops[eid]["lat"], stops[eid]["lon"])
        for eid in end_stops if eid in stops
    )
    return min_dist / MAX_SPEED_MPS


def heuristic_transfers(stop_id: str, end_stops: set,
                        stops: dict, direct: dict) -> float:
    reachable = direct.get(stop_id, set())
    if reachable & end_stops:
        return 0.0
    return 1.0


def astar(start_ids: list, end_ids: set, start_sec: int,
          edge_map: dict, criterion: str, stops: dict) -> tuple | None:
    
    INF = float("inf")

    if criterion == "p":
        direct = build_direct_stop_set(edge_map)
        h_fun = lambda sid, ends, stops: heuristic_transfers(sid, ends, stops, direct)
    else:
        h_fun = heuristic_time

    dist = {}
    prev = {}
    pq   = []

    for sid in start_ids:
        h = h_fun(sid, end_ids, stops)
        dist[sid] = (start_sec, 0)
        heapq.heappush(pq, (start_sec + h, start_sec, start_sec, 0, sid, None, None))

    visited: set = set()
    use_visited = (criterion == "t")

    while pq:
        f, cost, cur_time, xfers, cur_id, prev_trip, prev_block = heapq.heappop(pq)

        
        old = dist.get(cur_id)
        if old is not None:
            old_cost = old[0] if criterion == "t" else old[1] * 10_000_000 + old[0]
            if cost > old_cost:
                continue

        if use_visited:
            if cur_id in visited:
                continue
            visited.add(cur_id)

        if cur_id in end_ids:
            return dist, prev, cur_id

        for edge in edge_map.get(cur_id, []):
            nid = edge["to"]
            if use_visited and nid in visited:
                continue

            result = relax_edge(edge, cur_time, xfers, prev_trip, criterion, prev_block)
            if result is None:
                continue
            new_time, new_xfers, new_cost = result

            old = dist.get(nid)
            old_cost = (old[0] if criterion == "t"
                        else old[1] * 10_000_000 + old[0]) if old else INF

            if new_cost < old_cost:
                dist[nid] = (new_time, new_xfers)
                prev[nid] = {
                    "from":     cur_id,
                    "trip_id":  edge["trip_id"],
                    "line":     edge.get("line"),
                    "dep":      cur_time if edge["transfer"] else edge["dep"],
                    "arr":      new_time,
                    "transfer": edge["transfer"],
                }
                h  = h_fun(nid, end_ids, stops)
                nf = new_cost + h
                if edge["transfer"]:
                    new_trip  = prev_trip
                    new_block = prev_block
                else:
                    new_trip  = edge["trip_id"]
                    new_block = edge.get("block_id", "")
                heapq.heappush(pq, (nf, new_cost, new_time, new_xfers, nid,
                                    new_trip, new_block))

    return best_end(dist, prev, end_ids, criterion)