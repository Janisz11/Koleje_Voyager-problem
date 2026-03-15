#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

sys.path.insert(0, __file__.rsplit("src", 1)[0])
from src.config import SECONDS_PER_DAY


def time_to_sec(t: str) -> int:
    if not t:
        return 0
    parts = t.strip().split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2]) if len(parts) > 2 else 0
    return hours * 3600 + minutes * 60 + seconds


def sec_to_hhmm(s: int, show_day: bool = False) -> str:
    if show_day:
        day = s // SECONDS_PER_DAY
        s_in_day = s % SECONDS_PER_DAY
        h = s_in_day // 3600
        m = (s_in_day % 3600) // 60
        if day > 0:
            return f"D{day+1} {h:02d}:{m:02d}"
        return f"{h:02d}:{m:02d}"
    else:
        h = s // 3600
        m = (s % 3600) // 60
        return f"{h:02d}:{m:02d}"


def format_duration(total_seconds: int) -> str:
    days = total_seconds // SECONDS_PER_DAY
    hours = (total_seconds % SECONDS_PER_DAY) // 3600
    minutes = (total_seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h {minutes}min"
    elif hours > 0:
        return f"{hours}h {minutes}min"
    else:
        return f"{minutes}min"
