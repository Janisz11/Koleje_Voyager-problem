#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import heapq

from .common import relax_edge, best_end


def dijkstra(start_ids: list, end_ids: set, start_sec: int,
             edge_map: dict, criterion: str) -> tuple | None:
   
    
   
    INF = float("inf")
    dist = {}
    prev = {}

    pq = []
    for sid in start_ids:
        dist[sid] = (start_sec, 0)
        heapq.heappush(pq, (start_sec, start_sec, 0, sid, None, None))

    visited = set()

    while pq:
        cost, cur_time, xfers, cur_id, prev_trip, prev_block = heapq.heappop(pq)

        if cur_id in visited:
            continue
        visited.add(cur_id)

        if cur_id in end_ids:
            return dist, prev, cur_id

        for edge in edge_map.get(cur_id, []):
            nid = edge["to"]
            if nid in visited:
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
                if edge["transfer"]:
                    new_trip  = prev_trip
                    new_block = prev_block
                else:
                    new_trip  = edge["trip_id"]
                    new_block = edge.get("block_id", "")
                heapq.heappush(pq, (new_cost, new_time, new_xfers, nid,
                                    new_trip, new_block))

    return best_end(dist, prev, end_ids, criterion)
