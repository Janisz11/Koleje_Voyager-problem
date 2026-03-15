#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

sys.path.insert(0, __file__.rsplit("src", 1)[0])
from src.config import TRANSFER_COST_MULTIPLIER


def relax_edge(edge: dict, cur_time: int, xfers: int, prev_trip_id,
               criterion: str, prev_block_id=None) -> tuple | None:

    if edge["transfer"]:
        new_time  = cur_time
        new_xfers = xfers
    else:
        if edge["dep"] < cur_time:
            return None

        new_time = edge["arr"]

        trip_changed = prev_trip_id is not None and edge["trip_id"] != prev_trip_id
        if trip_changed:
            curr_block = edge.get("block_id", "")
            block_same = curr_block and prev_block_id and curr_block == prev_block_id
            new_xfers = xfers if block_same else xfers + 1
            if new_xfers > xfers:
                print(f"DEBUG xfer: {prev_trip_id[:15]} -> {edge['trip_id'][:15]} block {prev_block_id} -> {curr_block}", file=__import__('sys').stderr)
        else:
            new_xfers = xfers

  
    if criterion == "t":
        new_cost = new_time
    else:
        
        new_cost = new_xfers * TRANSFER_COST_MULTIPLIER + new_time

    return new_time, new_xfers, new_cost


def reconstruct_path(prev: dict, start_ids: set, end_id: str) -> list:
    
    path = []
    cur  = end_id
    seen = set()

    while cur not in start_ids and cur in prev:
        if cur in seen:
            break
        seen.add(cur)

        step = prev[cur]
        path.append({
            "from_id":  step["from"],
            "to_id":    cur,
            "line":     step["line"],
            "dep":      step["dep"],
            "arr":      step["arr"],
            "trip_id":  step["trip_id"],
            "transfer": step.get("transfer", False),
        })
        cur = step["from"]

    path.reverse()
    return path


def best_end(dist: dict, prev: dict, end_ids: set, criterion: str) -> tuple | None:
   
    best_end_id = None
    best_cost   = float("inf")

    for eid in end_ids:
        if eid not in dist:
            continue
        d = dist[eid]
        c = d[0] if criterion == "t" else d[1] * TRANSFER_COST_MULTIPLIER + d[0]
        if c < best_cost:
            best_cost   = c
            best_end_id = eid

    if best_end_id is None:
        return None

    return dist, prev, best_end_id
