#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GTFS_DIR = os.path.join(PROJECT_ROOT, "google_transit")

MAX_SPEED_MPS = 44.4

TRANSFER_COST_MULTIPLIER = 10_000_000

TABU_MAX_NO_IMPROVE_RATIO = 0.25

TABU_STEP_LIMIT_MULTIPLIER = 30

TABU_MIN_STEPS = 200

SECONDS_PER_DAY = 86400

DEFAULT_NUM_DAYS = 3
