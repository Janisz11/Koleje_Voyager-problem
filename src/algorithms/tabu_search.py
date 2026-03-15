#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import math
import random

sys.path.insert(0, __file__.rsplit("src", 1)[0])
from src.config import TABU_MIN_STEPS, TABU_STEP_LIMIT_MULTIPLIER, TABU_MAX_NO_IMPROVE_RATIO

MULTISTART_RESTARTS = 3  


def tour_cost_matrix(tour: list[int], cost_matrix: list) -> float:
    return sum(cost_matrix[tour[k]][tour[k + 1]] for k in range(len(tour) - 1))


def nearest_neighbour_init(n_stops: int, cost_matrix: list) -> list:
    visited    = [False] * n_stops
    tour       = [0]
    visited[0] = True

    for _ in range(n_stops - 1):
        cur       = tour[-1]
        best_next = -1
        best_cost = float("inf")

        for j in range(n_stops):
            if not visited[j] and cost_matrix[cur][j] < best_cost:
                best_cost = cost_matrix[cur][j]
                best_next = j

        if best_next == -1:
            best_next = next(j for j in range(n_stops) if not visited[j])

        tour.append(best_next)
        visited[best_next] = True

    tour.append(0)
    return tour


def random_init(n_stops: int) -> list:
   
    inner = list(range(1, n_stops))
    random.shuffle(inner)
    return [0] + inner + [0]


def tabu_search_core(n_stops: int, cost_matrix: list,
                     tabu_tenure: int | None,
                     use_aspiration: bool = False,
                     use_sampling: bool = False,
                     init_tour: list = None) -> list:
    step_limit = max(TABU_MIN_STEPS, TABU_STEP_LIMIT_MULTIPLIER * n_stops)

    inner      = list(range(1, n_stops))
    full_pairs = len(inner) * (len(inner) - 1) // 2

    if use_sampling:
        op_limit = min(full_pairs, max(20, 4 * n_stops))
    else:
        op_limit = full_pairs

    
    current = init_tour[:] if init_tour is not None else nearest_neighbour_init(n_stops, cost_matrix)
    best    = current[:]
    best_c  = tour_cost_matrix(best, cost_matrix)

    tabu: list[tuple] = []

    no_improve     = 0
    max_no_improve = max(50, int(step_limit * TABU_MAX_NO_IMPROVE_RATIO))

    for k in range(step_limit):
        all_pairs = [(inner[a], inner[b])
                     for a in range(len(inner))
                     for b in range(a + 1, len(inner))]

        if use_sampling and len(all_pairs) > op_limit:
            pairs = random.sample(all_pairs, op_limit)
        else:
            pairs = all_pairs

        best_move      = None
        best_move_cost = float("inf")

        for (pos_a, pos_b) in pairs:
            new_tour = current[:pos_a] + current[pos_a:pos_b + 1][::-1] + current[pos_b + 1:]
            new_cost = tour_cost_matrix(new_tour, cost_matrix)

            move    = (min(pos_a, pos_b), max(pos_a, pos_b))
            in_tabu = move in tabu

            if in_tabu:
                if use_aspiration and new_cost < best_c:
                    pass
                else:
                    continue

            if new_cost < best_move_cost:
                best_move_cost = new_cost
                best_move      = (pos_a, pos_b, new_tour, new_cost)

        if best_move is None:
            break

        pos_a, pos_b, new_tour, new_cost = best_move
        current = new_tour

        move = (min(pos_a, pos_b), max(pos_a, pos_b))
        tabu.append(move)

        if tabu_tenure is not None and len(tabu) > tabu_tenure:
            tabu.pop(0)

        if new_cost < best_c:
            best       = current[:]
            best_c     = new_cost
            no_improve = 0
            print(f"  k={k:4d} | optimum: {best_c:.0f}", file=sys.stderr)
        else:
            no_improve += 1
            if no_improve >= max_no_improve:
                print(f"  k={k:4d} | brak poprawy od {max_no_improve} kroków – stop",
                      file=sys.stderr)
                break

    return best, best_c


def tabu_search_multistart(n_stops: int, cost_matrix: list,
                           tabu_tenure: int | None,
                           use_aspiration: bool = False,
                           use_sampling: bool = False) -> list:
   
    global_best      = None
    global_best_cost = float("inf")

    for i in range(MULTISTART_RESTARTS):
        if i == 0:
            init = nearest_neighbour_init(n_stops, cost_matrix)
            label = "nearest-neighbour"
        else:
            init = random_init(n_stops)
            label = f"losowy restart #{i}"

        print(f"\n  [Multi-start {i+1}/{MULTISTART_RESTARTS}] init={label}", file=sys.stderr)

        tour, cost = tabu_search_core(
            n_stops, cost_matrix, tabu_tenure,
            use_aspiration=use_aspiration,
            use_sampling=use_sampling,
            init_tour=init
        )

        print(f"  → koszt: {cost:.0f}", file=sys.stderr)

        if cost < global_best_cost:
            global_best_cost = cost
            global_best      = tour[:]

    print(f"\n  Najlepszy multi-start: {global_best_cost:.0f}", file=sys.stderr)
    return global_best


def tabu_search_unlimited(n_stops: int, cost_matrix: list,
                          use_aspiration: bool = False,
                          use_sampling: bool = False) -> list:
    return tabu_search_multistart(n_stops, cost_matrix,
                                  tabu_tenure=None,
                                  use_aspiration=use_aspiration,
                                  use_sampling=use_sampling)


def tabu_search_variable_tenure(n_stops: int, cost_matrix: list, L_size: int,
                                use_aspiration: bool = False,
                                use_sampling: bool = False) -> list:
    tenure = max(5, math.ceil(L_size / 2))
    print(f"  Zmienny tenure: max(5, ceil({L_size}/2)) = {tenure}", file=sys.stderr)
    return tabu_search_multistart(n_stops, cost_matrix,
                                  tabu_tenure=tenure,
                                  use_aspiration=use_aspiration,
                                  use_sampling=use_sampling)